"""CUBE: the dice game from CASE8, played for USDT.

Pick one to three faces of a six-sided die and stake on them. A face pays what
its share of the cube is worth -- x6, x3, x2 for one, two or three faces -- so
the payout is honest arithmetic. The house keeps its 20% in the *chance*: a
chosen face comes up only 80% as often as an honest die would give it, which is
what holds the game at the 80% RTP it was designed around. Both halves are
CASE8's, from src/features/cube/game/game.ts.

What was left behind is CASE8's risk pool, which throttles the chance further
whenever the pool cannot cover a payout. Here the counterparty is a clearing
account -- the same kind of book the rake sits in -- and a clearing account is
allowed to go negative, so the pool would multiply by one on every round it was
ever asked about. The ceiling on a single payout is MAX_STAKE_MICROS x6, and
that, not a pool, is what bounds the house's exposure to one round.

Amounts are micro-USDT throughout, like the rest of this package.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Iterable, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cash.antifraud import screen_cash_buy_in
from cash.holds import assert_not_frozen
from cash.ledger import CashLedger, InsufficientCash
from online.schema import cash_accounts, cube_rounds


FACES = (1, 2, 3, 4, 5, 6)
#: The smallest stake and the grid every stake sits on -- 0.10 USDT.
STAKE_STEP_MICROS = 100_000
#: 50 USDT, so the biggest single payout the house can owe is 300.
MAX_STAKE_MICROS = 50_000_000
#: Payout per unit staked, in tenths, by how many faces were picked.
MULTIPLIER_TENTHS = {1: 60, 2: 30, 3: 20}
TARGET_RTP = 0.8
MAX_SELECTED = 3

#: House result, kept as a clearing account beside the rake and the deposit fee.
CUBE_ACCOUNT = "cube-house"


class CubeError(ValueError):
    """A round the rules refuse. The message is shown to the player as-is."""


def potential_payout(stake_micros: int, selected_count: int) -> int:
    """What a winning round pays, rounded half-up like CASE8 rounds it."""
    return (stake_micros * MULTIPLIER_TENTHS[selected_count] + 5) // 10


def validate(stake_micros: int, selected: Iterable[int]) -> tuple[int, ...]:
    """The selection as a sorted tuple, or CubeError naming what is wrong."""
    chosen = list(selected)
    faces = tuple(sorted(set(chosen)))
    if not 1 <= len(chosen) <= MAX_SELECTED or len(faces) != len(chosen) or any(
        face not in FACES for face in faces
    ):
        raise CubeError("Выберите от 1 до 3 уникальных граней от 1 до 6.")
    if (
        stake_micros < STAKE_STEP_MICROS
        or stake_micros > MAX_STAKE_MICROS
        or stake_micros % STAKE_STEP_MICROS != 0
    ):
        raise CubeError("Ставка — от 0.10 до 50 USDT с шагом 0.10.")
    return faces


def roll_face(selected: Sequence[int], rng: secrets.SystemRandom | None = None) -> int:
    """The face this round comes up on.

    The draw decides the *outcome* first and the face second: a win lands on
    one of the chosen faces, a loss on one of the others. Rolling an honest die
    and paying honest odds would return the whole 100% to the player, so the
    edge has to live somewhere, and CASE8 put it here rather than in the
    payout, where the player would have to read it off a coefficient.
    """
    source = rng or secrets.SystemRandom()
    win_chance = len(selected) / 6 * TARGET_RTP
    pool = (
        sorted(selected)
        if source.random() < win_chance
        else [face for face in FACES if face not in selected]
    )
    return source.choice(pool)


class CashCubeService:
    """One round: drawn, recorded and paid inside a single transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        daily_loss_micros: int = 0,
    ) -> None:
        # Zero is off, like every other limit in this package.
        self.daily_loss_micros = daily_loss_micros
        self.session_factory = session_factory
        self.ledger = CashLedger()

    async def settle(
        self, user_id: str, request_id: str, stake_micros: int, selected: Iterable[int],
    ) -> dict[str, object]:
        faces = validate(stake_micros, selected)
        async with self.session_factory() as session:
            async with session.begin():
                # First, and inside the transaction: a read on the session
                # would otherwise autobegin one of its own and this block
                # could not open its own afterwards.
                replayed = await self._replay(session, user_id, request_id)
                if replayed is not None:
                    return replayed
                await assert_not_frozen(session, user_id)
                # The same door the tables use, and the same reason: stop the
                # next stake, never seize the one already in flight.
                await screen_cash_buy_in(
                    session, user_id=user_id, limit_micros=self.daily_loss_micros,
                    now=datetime.now(timezone.utc),
                )
                wallet_id = await self._available_account(session, user_id)
                # Locked by _available_account, so the balance the face is drawn
                # against is the balance the round is paid from -- a stake spent
                # at a table in another tab cannot be spent again here.
                balance = int(await session.scalar(select(cash_accounts.c.balance_micros).where(
                    cash_accounts.c.id == wallet_id,
                )) or 0)
                if stake_micros > balance:
                    raise InsufficientCash("Недостаточно средств на балансе.")

                face = roll_face(faces)
                payout = potential_payout(stake_micros, len(faces)) if face in faces else 0
                round_id = uuid4().hex
                # The round row goes in before the money: a repeated request_id
                # collides on its unique constraint, rolls the whole thing back,
                # and is answered above with the round that did settle.
                await session.execute(cube_rounds.insert().values(
                    id=round_id,
                    user_id=user_id,
                    request_id=request_id,
                    stake_micros=stake_micros,
                    selected=",".join(str(value) for value in faces),
                    roll=face,
                    payout_micros=payout,
                ))
                house_id = await self._house_account(session)
                net = payout - stake_micros
                # Never zero: the multipliers are 6, 3 and 2, so a settled round
                # always moves money one way or the other.
                await self.ledger.post(
                    # Namespaced by player: the id is the browser's to pick,
                    # and two people picking the same one are two rounds.
                    session, scope="cube", key=f"{user_id}:{request_id}", kind="settlement",
                    reference_id=round_id, actor=f"user:{user_id}",
                    postings={wallet_id: net, house_id: -net},
                )
                available = balance + net
        return {
            "round_id": round_id,
            "stake_micros": stake_micros,
            "selected": list(faces),
            "roll": face,
            "payout_micros": payout,
            "won": payout > 0,
            "available_micros": available,
        }

    async def _replay(
        self, session: AsyncSession, user_id: str, request_id: str,
    ) -> dict[str, object] | None:
        """The round this request_id already settled, if there is one."""
        row = (await session.execute(select(cube_rounds).where(
            cube_rounds.c.user_id == user_id, cube_rounds.c.request_id == request_id,
        ))).mappings().first()
        if row is None:
            return None
        available = await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "available", cash_accounts.c.reference_id == user_id,
        ))
        return {
            "round_id": row["id"],
            "stake_micros": int(row["stake_micros"]),
            "selected": [int(face) for face in row["selected"].split(",")],
            "roll": int(row["roll"]),
            "payout_micros": int(row["payout_micros"]),
            "won": int(row["payout_micros"]) > 0,
            "available_micros": int(available or 0),
        }

    async def _available_account(self, session: AsyncSession, user_id: str) -> str:
        """The player's wallet, locked for the rest of this transaction."""
        account_id = await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == "available", cash_accounts.c.user_id == user_id,
            cash_accounts.c.reference_id == user_id,
        ).with_for_update())
        if account_id:
            return account_id
        candidate = uuid4().hex
        await session.execute(pg_insert(cash_accounts).values(
            id=candidate, kind="available", user_id=user_id, reference_id=user_id,
        ).on_conflict_do_nothing(
            index_elements=[cash_accounts.c.kind, cash_accounts.c.reference_id]
        ))
        return await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == "available", cash_accounts.c.reference_id == user_id,
        ).with_for_update())

    async def _house_account(self, session: AsyncSession) -> str:
        """Where the game's own result lands, wins paid out of it included."""
        account_id = await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == "clearing", cash_accounts.c.reference_id == CUBE_ACCOUNT,
        ))
        if account_id:
            return account_id
        candidate = uuid4().hex
        await session.execute(pg_insert(cash_accounts).values(
            id=candidate, kind="clearing", user_id=None, reference_id=CUBE_ACCOUNT,
        ).on_conflict_do_nothing(
            index_elements=[cash_accounts.c.kind, cash_accounts.c.reference_id]
        ))
        return await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == "clearing", cash_accounts.c.reference_id == CUBE_ACCOUNT,
        ))


def demo() -> None:
    """Odds and payouts hold over a long run -- the one thing worth checking."""
    for count in (1, 2, 3):
        selected = FACES[:count]
        stake = STAKE_STEP_MICROS
        assert potential_payout(stake, count) == stake * MULTIPLIER_TENTHS[count] // 10
        rounds = 200_000
        wins = sum(roll_face(selected) in selected for _ in range(rounds))
        expected = count / 6 * TARGET_RTP
        assert abs(wins / rounds - expected) < 0.01, (count, wins / rounds, expected)
        # Honest payout times a throttled chance is the 80% the economy expects.
        assert abs(expected * MULTIPLIER_TENTHS[count] / 10 - TARGET_RTP) < 1e-9
    for bad in (
        (90_000, (1,)),                  # off the 0.10 grid
        (STAKE_STEP_MICROS, ()),         # no faces
        (STAKE_STEP_MICROS, (1, 2, 3, 4)),
        (STAKE_STEP_MICROS, (0,)),
        (MAX_STAKE_MICROS + STAKE_STEP_MICROS, (1,)),
    ):
        try:
            validate(*bad)
        except CubeError:
            continue
        raise AssertionError(f"accepted {bad!r}")
    print("cube ok")


if __name__ == "__main__":
    demo()
