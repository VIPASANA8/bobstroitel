from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cash.ledger import CashLedger, IdempotencyConflict
from online.catalogue import CASH_USDT
from online.events import append_integrity_event
from online.schema import (
    cash_accounts, game_commands, hand_players, hands, poker_tables,
    table_runtimes, table_seats, users,
)
from online.serialization import deserialize_state, serialize_state
from poker.engine import InvalidAction, PokerEngine
from poker.models import ActionType, GameState


class CashSeatError(ValueError):
    pass


class CashRuntimeError(RuntimeError):
    pass


class CashIntegrityError(CashRuntimeError):
    pass


class CashCommandConflict(CashRuntimeError):
    pass


@dataclass(frozen=True)
class CashSeat:
    id: str
    user_id: str
    table_id: str
    seat_no: int
    cash_escrow_account_id: str
    stack_micros: int


@dataclass(frozen=True)
class CashRuntimeResult:
    revision: int
    state: GameState


class CashGameService:
    """Exact-chip CASH runtime used only behind the isolated mock-mode gate."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self.ledger = CashLedger()

    async def public_snapshot(self, table_id: str, viewer_id: str | None = None) -> dict:
        """Return the existing client contract while retaining exact server math.

        The engine stores whole chips. The browser renders big blinds, so this
        read-only projection divides by the table's whole-chip BB. Commands
        travel back as whole chips and are converted to micros before mutation.
        """
        async with self.session_factory() as session:
            table = await self._table(session, table_id, lock=False)
            seats = (await session.execute(select(table_seats).where(
                table_seats.c.table_id == table_id,
                table_seats.c.state.in_(("seated", "held", "leaving")),
            ))).mappings().all()
            names = dict((await session.execute(select(
                users.c.id, users.c.display_name,
            ).where(users.c.id.in_([row["user_id"] for row in seats])))).all()) if seats else {}
            runtime = (await session.execute(select(table_runtimes).where(
                table_runtimes.c.table_id == table_id
            ))).mappings().one_or_none()
        participant = viewer_id if any(row["user_id"] == viewer_id for row in seats) else None
        current = {
            row["seat_no"]: {
                "id": row["user_id"], "name": names.get(row["user_id"], "Player"),
                "stack": row["stack_micros"] / table["big_blind_micros"],
                "is_bot": False, "state": row["state"],
            } for row in seats
        }
        if runtime is None or not runtime["private_state_json"]:
            return {
                "phase": "waiting", "revision": 0, "occupancy": len(seats),
                "legal_actions": [], "players": {}, "action_deadline": None,
                "viewer_player_id": participant, "current_seats": current,
                "ready_seats": [], "cash_test": True,
            }
        state = deserialize_state(runtime["private_state_json"])
        public = state.to_dict(viewer_player_id=participant)
        bb_chips = table["big_blind_micros"] // table["chip_micros"]
        for player in public["players"].values():
            for field in ("stack", "street_invested", "total_invested"):
                player[field] = player[field] / bb_chips
            player.pop("difficulty", None)
        for field in ("pot", "current_bet", "min_raise_size"):
            public[field] = public[field] / bb_chips
        public["starting_stacks"] = {
            key: value / bb_chips for key, value in public["starting_stacks"].items()
        }
        for action in public["history"]:
            for field in ("amount", "pot_after", "pot_before", "to_call_before"):
                action[field] = action[field] / bb_chips
        legal = [
            action.value for action in self._engine(table).legal_actions(state, participant)
        ] if participant else []
        public.update({
            "phase": runtime["phase"], "revision": runtime["revision"],
            "legal_actions": legal, "action_deadline": None,
            "occupancy": len(seats), "current_seats": current,
            "ready_seats": [], "cash_test": True,
        })
        return public

    async def seat(
        self, user_id: str, table_id: str, seat_no: int,
        buy_in_micros: int, request_id: str,
    ) -> CashSeat:
        async with self.session_factory() as session:
            async with session.begin():
                self._require_postgres(session)
                table = await self._table(session, table_id, lock=True)
                self._validate_buy_in(table, seat_no, buy_in_micros)
                existing = (
                    await session.execute(
                        select(table_seats).where(
                            table_seats.c.user_id == user_id,
                            table_seats.c.state.in_(("seated", "held", "leaving")),
                        ).with_for_update()
                    )
                ).mappings().one_or_none()
                if existing is not None:
                    if (
                        existing["table_id"] == table_id
                        and existing["seat_no"] == seat_no
                        and existing["stack_micros"] == buy_in_micros
                        and existing["cash_escrow_account_id"]
                    ):
                        return self._seat_result(existing)
                    raise CashSeatError("user already has an active seat")

                slot = (
                    await session.execute(
                        select(table_seats).where(
                            table_seats.c.table_id == table_id,
                            table_seats.c.seat_no == seat_no,
                        ).with_for_update()
                    )
                ).mappings().one_or_none()
                if slot is not None and slot["state"] != "empty":
                    raise CashSeatError("seat is occupied")
                seat_id = slot["id"] if slot is not None else uuid4().hex
                wallet_id = await self._available_account(session, user_id)
                escrow_id = await self._escrow_account(session, user_id)
                await self.ledger.post(
                    session, scope=f"cash-seat:{table_id}", key=request_id,
                    kind="reserve", reference_id=escrow_id, actor=f"user:{user_id}",
                    postings={wallet_id: -buy_in_micros, escrow_id: buy_in_micros},
                )
                values = dict(
                    occupant_kind="user", user_id=user_id, system_player_id=None,
                    escrow_account_id=None, cash_escrow_account_id=escrow_id,
                    stack_units=0, stack_micros=buy_in_micros, state="seated",
                    seated_at=datetime.now(timezone.utc), disconnected_at=None, hold_until=None,
                )
                if slot is None:
                    await session.execute(insert(table_seats).values(
                        id=seat_id, table_id=table_id, seat_no=seat_no, **values,
                    ))
                else:
                    await session.execute(update(table_seats).where(
                        table_seats.c.id == seat_id
                    ).values(**values))
                return CashSeat(
                    seat_id, user_id, table_id, seat_no, escrow_id, buy_in_micros,
                )

    async def start_hand(self, table_id: str, *, button_seat: int | None = None) -> CashRuntimeResult:
        failure = None
        result = None
        async with self.session_factory() as session:
            async with session.begin():
                self._require_postgres(session)
                table = await self._table(session, table_id, lock=True)
                runtime = (
                    await session.execute(select(table_runtimes).where(
                        table_runtimes.c.table_id == table_id
                    ).with_for_update())
                ).mappings().one_or_none()
                if runtime and runtime["phase"] == "paused":
                    raise CashRuntimeError(runtime["paused_reason"] or "cash table is paused")
                if runtime and runtime["phase"] == "active":
                    return CashRuntimeResult(runtime["revision"], deserialize_state(runtime["private_state_json"]))
                seats = (
                    await session.execute(select(table_seats).where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.state == "seated",
                    ).order_by(table_seats.c.seat_no).with_for_update())
                ).mappings().all()
                if any(row["occupant_kind"] != "user" for row in seats):
                    raise CashSeatError("system occupants are forbidden at CASH tables")
                if not 2 <= len(seats) <= 6:
                    raise CashRuntimeError("a cash hand requires 2 to 6 seated users")
                failure = await self._escrow_mismatch(session, seats)
                if failure:
                    await self._pause(session, table_id, None, failure, runtime=runtime)
                else:
                    engine = self._engine(table)
                    details = dict((await session.execute(select(
                        users.c.id, users.c.display_name,
                    ).where(users.c.id.in_([row["user_id"] for row in seats])))).all())
                    engine_seats = [{
                        "id": row["user_id"], "name": details[row["user_id"]],
                        "seat": row["seat_no"],
                        "stack": row["stack_micros"] // table["chip_micros"],
                        "is_bot": False, "profile_id": row["user_id"],
                    } for row in seats]
                    if button_seat is None:
                        occupied = [row["seat_no"] for row in seats]
                        previous = table["button_seat"]
                        button_seat = (
                            occupied[(occupied.index(previous) + 1) % len(occupied)]
                            if previous in occupied else occupied[0]
                        )
                    state = engine.new_hand(engine_seats, button_seat=button_seat)
                    revision = (runtime["revision"] if runtime else 0) + 1
                    values = dict(
                        revision=revision, phase="active",
                        private_state_json=serialize_state(state),
                        public_payload_json=state.to_dict(), paused_reason=None,
                        action_deadline=None, result_clear_at=None, next_hand_at=None,
                    )
                    if runtime:
                        await session.execute(update(table_runtimes).where(
                            table_runtimes.c.table_id == table_id
                        ).values(**values))
                    else:
                        await session.execute(insert(table_runtimes).values(table_id=table_id, **values))
                    await session.execute(update(poker_tables).where(
                        poker_tables.c.id == table_id
                    ).values(button_seat=state.players[state.button].seat))
                    await session.execute(insert(hands).values(
                        id=state.hand_id, table_id=table_id, revision_started=revision,
                        button_seat=state.players[state.button].seat, board_json=[], terminal=False,
                    ))
                    by_user = {row["user_id"]: row for row in seats}
                    for participant_id in state.seat_order:
                        player = state.players[participant_id]
                        seat = by_user[participant_id]
                        await session.execute(insert(hand_players).values(
                            hand_id=state.hand_id, participant_id=participant_id,
                            user_id=participant_id, system_player_id=None,
                            seat_no=player.seat, position=player.position,
                            start_stack_units=None,
                            cash_escrow_account_id=seat["cash_escrow_account_id"],
                            start_stack_micros=seat["stack_micros"],
                        ))
                    result = CashRuntimeResult(revision, state)
        if failure:
            raise CashIntegrityError(failure)
        return result

    async def add_on(
        self, user_id: str, table_id: str, amount_micros: int, request_id: str,
    ) -> CashSeat:
        failure = None
        result = None
        async with self.session_factory() as session:
            async with session.begin():
                self._require_postgres(session)
                table = await self._table(session, table_id, lock=True)
                if (
                    type(amount_micros) is not int or amount_micros <= 0
                    or amount_micros % table["chip_micros"]
                ):
                    raise CashSeatError("cash add-on must be a positive whole chip amount")
                runtime = (
                    await session.execute(select(table_runtimes).where(
                        table_runtimes.c.table_id == table_id
                    ).with_for_update())
                ).mappings().one_or_none()
                if runtime and runtime["phase"] in {"active", "paused"}:
                    raise CashSeatError("cash add-on is only allowed between hands")
                seat = (
                    await session.execute(select(table_seats).where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.user_id == user_id,
                        table_seats.c.state.in_(("seated", "held")),
                    ).with_for_update())
                ).mappings().one_or_none()
                if seat is None or not seat["cash_escrow_account_id"]:
                    raise CashSeatError("cash seat not found")
                failure = await self._escrow_mismatch(session, [seat])
                if failure:
                    await self._pause(session, table_id, None, failure, runtime=runtime)
                else:
                    maximum = table["big_blind_micros"] * table["max_buy_in_bb"]
                    if seat["stack_micros"] + amount_micros > maximum:
                        raise CashSeatError("cash stack exceeds the table maximum")
                    wallet_id = await self._available_account(session, user_id)
                    receipt = await self.ledger.post(
                        session, scope=f"cash-seat:{table_id}", key=request_id,
                        kind="reserve", reference_id=seat["cash_escrow_account_id"], actor=f"user:{user_id}",
                        postings={
                            wallet_id: -amount_micros,
                            seat["cash_escrow_account_id"]: amount_micros,
                        },
                    )
                    new_stack = (
                        seat["stack_micros"] + amount_micros
                        if receipt.created else seat["stack_micros"]
                    )
                    if receipt.created:
                        await session.execute(update(table_seats).where(
                            table_seats.c.id == seat["id"]
                        ).values(stack_micros=new_stack))
                    result = CashSeat(
                        seat["id"], user_id, table_id, seat["seat_no"],
                        seat["cash_escrow_account_id"], new_stack,
                    )
        if failure:
            raise CashIntegrityError(failure)
        return result

    async def act(
        self, table_id: str, user_id: str, action: ActionType,
        *, amount_micros: int, command_id: str, expected_revision: int,
    ) -> CashRuntimeResult:
        failure = None
        result = None
        async with self.session_factory() as session:
            async with session.begin():
                self._require_postgres(session)
                table = await self._table(session, table_id, lock=True)
                payload = {"amount_micros": amount_micros}
                existing = (
                    await session.execute(select(game_commands).where(
                        game_commands.c.table_id == table_id,
                        game_commands.c.command_id == command_id,
                    ).with_for_update())
                ).mappings().one_or_none()
                if existing:
                    same = (
                        existing["user_id"] == user_id
                        and existing["expected_revision"] == expected_revision
                        and existing["command_type"] == action.value
                        and existing["payload_json"] == payload
                    )
                    if not same:
                        raise CashCommandConflict("same command id with different content")
                    if existing["status"] == "rejected":
                        raise CashIntegrityError(existing["result_json"]["error"])
                    stored = existing["result_json"]
                    return CashRuntimeResult(stored["revision"], deserialize_state(stored["state"]))

                runtime = (
                    await session.execute(select(table_runtimes).where(
                        table_runtimes.c.table_id == table_id
                    ).with_for_update())
                ).mappings().one_or_none()
                if runtime is None or runtime["phase"] != "active":
                    raise CashRuntimeError("cash hand is not active")
                if runtime["revision"] != expected_revision:
                    raise CashCommandConflict("stale cash revision")
                if type(amount_micros) is not int or amount_micros < 0:
                    raise CashCommandConflict("cash action amount must be nonnegative integer micros")
                if amount_micros % table["chip_micros"]:
                    raise CashCommandConflict("cash action amount must be a whole chip")
                state = deserialize_state(runtime["private_state_json"])
                if state.acting_player != user_id:
                    raise CashCommandConflict("user is not the acting player")
                before = serialize_state(state)
                try:
                    self._engine(table).apply_action(
                        state, user_id, action, amount_micros // table["chip_micros"],
                    )
                except InvalidAction as exc:
                    raise CashCommandConflict(str(exc)) from exc
                # A disconnected/leaving player must never hold a money hand
                # open indefinitely. Their escrow stays reserved and the exact
                # engine folds them only when their turn is actually reached.
                leaving = set((await session.execute(select(table_seats.c.user_id).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.state == "leaving",
                    table_seats.c.user_id.is_not(None),
                ))).scalars())
                while not state.terminal and state.acting_player in leaving:
                    self._engine(table).apply_action(
                        state, state.acting_player, ActionType.FOLD, 0,
                    )
                revision = expected_revision + 1
                if state.terminal:
                    failure = await self._settle(session, table, state)
                if failure:
                    await self._pause(session, table_id, state.hand_id, failure, runtime=runtime, state=before)
                    await session.execute(insert(game_commands).values(
                        table_id=table_id, command_id=command_id, user_id=user_id,
                        expected_revision=expected_revision, command_type=action.value,
                        payload_json=payload, status="rejected", result_json={"error": failure},
                    ))
                else:
                    phase = "result" if state.terminal else "active"
                    await session.execute(update(table_runtimes).where(
                        table_runtimes.c.table_id == table_id
                    ).values(
                        revision=revision, phase=phase,
                        private_state_json=serialize_state(state),
                        public_payload_json=state.to_dict(),
                    ))
                    stored = {"revision": revision, "state": serialize_state(state)}
                    await session.execute(insert(game_commands).values(
                        table_id=table_id, command_id=command_id, user_id=user_id,
                        expected_revision=expected_revision, command_type=action.value,
                        payload_json=payload, status="accepted", result_json=stored,
                    ))
                    result = CashRuntimeResult(revision, state)
        if failure:
            raise CashIntegrityError(failure)
        return result

    async def leave(self, user_id: str, table_id: str, request_id: str) -> None:
        failure = None
        async with self.session_factory() as session:
            async with session.begin():
                self._require_postgres(session)
                await self._table(session, table_id, lock=True)
                seat = (
                    await session.execute(select(table_seats).where(
                        table_seats.c.table_id == table_id,
                        table_seats.c.user_id == user_id,
                        table_seats.c.state.in_(("seated", "held", "leaving")),
                    ).with_for_update())
                ).mappings().one_or_none()
                if seat is None:
                    return
                runtime = (
                    await session.execute(select(table_runtimes).where(
                        table_runtimes.c.table_id == table_id
                    ).with_for_update())
                ).mappings().one_or_none()
                if runtime and runtime["phase"] in {"active", "paused"}:
                    await session.execute(update(table_seats).where(
                        table_seats.c.id == seat["id"]
                    ).values(state="leaving"))
                    return
                failure = await self._escrow_mismatch(session, [seat])
                if failure:
                    await self._pause(session, table_id, None, failure, runtime=runtime)
                else:
                    await self._release_seat(session, seat, request_id)
        if failure:
            raise CashIntegrityError(failure)

    async def _settle(self, session: AsyncSession, table, state: GameState) -> str | None:
        rows = (
            await session.execute(select(hand_players).where(
                hand_players.c.hand_id == state.hand_id
            ).with_for_update())
        ).mappings().all()
        seats = (
            await session.execute(select(table_seats).where(
                table_seats.c.table_id == table["id"],
                table_seats.c.user_id.in_([row["participant_id"] for row in rows]),
                table_seats.c.state.in_(("seated", "held", "leaving")),
            ).with_for_update())
        ).mappings().all()
        by_user = {row["user_id"]: row for row in seats}
        if len(rows) != len(state.players) or len(seats) != len(state.players):
            return "cash escrow invariant failed: participant seat is missing"
        mismatch = await self._escrow_mismatch(session, seats)
        if mismatch:
            return mismatch
        chip = table["chip_micros"]
        starts = {row["participant_id"]: row["start_stack_micros"] for row in rows}
        ends = {pid: player.stack * chip for pid, player in state.players.items()}
        if any(type(value) is not int for value in ends.values()) or sum(starts.values()) != sum(ends.values()):
            return "cash escrow invariant failed: hand did not conserve exact chips"
        postings = {}
        for participant_id in state.seat_order:
            seat = by_user[participant_id]
            delta = ends[participant_id] - starts[participant_id]
            if delta:
                postings[seat["cash_escrow_account_id"]] = delta
        if postings:
            try:
                await self.ledger.post(
                    session, scope=f"cash-table:{table['id']}", key=f"hand:{state.hand_id}",
                    kind="settlement", reference_id=state.hand_id, actor="system:cash-game",
                    postings=postings,
                )
            except (ValueError, IdempotencyConflict) as exc:
                return f"cash escrow settlement failed: {exc}"
        now = datetime.now(timezone.utc)
        for participant_id, player in state.players.items():
            seat = by_user[participant_id]
            end = ends[participant_id]
            await session.execute(update(table_seats).where(
                table_seats.c.id == seat["id"]
            ).values(stack_micros=end))
            await session.execute(update(hand_players).where(
                hand_players.c.hand_id == state.hand_id,
                hand_players.c.participant_id == participant_id,
            ).values(
                end_stack_micros=end, net_micros=end - starts[participant_id],
                hole_cards_json=list(player.hole_cards), shown=not player.folded,
                folded=player.folded,
            ))
        await session.execute(update(hands).where(hands.c.id == state.hand_id).values(
            board_json=list(state.board), result_json=state.to_dict(),
            completed_at=now, terminal=True,
        ))
        for participant_id in state.seat_order:
            seat = by_user[participant_id]
            if seat["state"] == "leaving":
                refreshed = dict(seat) | {"stack_micros": ends[participant_id]}
                await self._release_seat(
                    session, refreshed, f"leave:{seat['cash_escrow_account_id']}",
                )
        return None

    async def _release_seat(self, session: AsyncSession, seat, request_id: str) -> None:
        amount = int(seat["stack_micros"])
        escrow_id = seat["cash_escrow_account_id"]
        if not escrow_id:
            raise CashIntegrityError("cash seat has no escrow account")
        actual = await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.id == escrow_id
        ).with_for_update())
        if actual != amount:
            raise CashIntegrityError("cash escrow does not match seat stack")
        if amount:
            wallet_id = await self._available_account(session, seat["user_id"])
            await self.ledger.post(
                session, scope=f"cash-seat:{seat['table_id']}", key=request_id,
                kind="release", reference_id=escrow_id, actor=f"user:{seat['user_id']}",
                postings={escrow_id: -amount, wallet_id: amount},
            )
        await session.execute(update(table_seats).where(
            table_seats.c.id == seat["id"]
        ).values(
            occupant_kind="empty", user_id=None, system_player_id=None,
            escrow_account_id=None, cash_escrow_account_id=None,
            stack_units=0, stack_micros=0, state="empty",
            seated_at=None, disconnected_at=None, hold_until=None,
        ))

    async def _escrow_mismatch(self, session: AsyncSession, seats) -> str | None:
        account_ids = [row["cash_escrow_account_id"] for row in seats]
        if any(not account_id for account_id in account_ids):
            return "cash escrow invariant failed: account is missing"
        accounts = {
            row["id"]: row
            for row in (
                await session.execute(select(
                    cash_accounts.c.id, cash_accounts.c.balance_micros,
                    cash_accounts.c.kind, cash_accounts.c.user_id,
                ).where(cash_accounts.c.id.in_(account_ids)).with_for_update())
            ).mappings().all()
        }
        if len(accounts) != len(account_ids):
            return "cash escrow invariant failed: account is missing"
        for seat in seats:
            account = accounts[seat["cash_escrow_account_id"]]
            if account["kind"] != "escrow" or account["user_id"] != seat["user_id"]:
                return "cash escrow invariant failed: account owner or kind differs"
            if account["balance_micros"] != seat["stack_micros"]:
                return "cash escrow invariant failed: account and stack differ"
            if seat["stack_micros"] < 0:
                return "cash escrow invariant failed: negative stack"
        return None

    async def _pause(
        self, session: AsyncSession, table_id: str, hand_id: str | None, reason: str,
        *, runtime=None, state=None,
    ) -> None:
        values = {"phase": "paused", "paused_reason": reason}
        if state is not None:
            values["private_state_json"] = state
        if runtime:
            await session.execute(update(table_runtimes).where(
                table_runtimes.c.table_id == table_id
            ).values(**values))
        else:
            await session.execute(insert(table_runtimes).values(
                table_id=table_id, revision=0, private_state_json=None,
                public_payload_json={}, **values,
            ))
        await append_integrity_event(
            session, event_type="cash_escrow_mismatch", table_id=table_id,
            hand_id=hand_id, payload={"reason": reason},
        )

    async def _available_account(self, session: AsyncSession, user_id: str) -> str:
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

    async def _escrow_account(self, session: AsyncSession, user_id: str) -> str:
        candidate = uuid4().hex
        await session.execute(insert(cash_accounts).values(
            id=candidate, kind="escrow", user_id=user_id,
            reference_id=f"seat:{uuid4().hex}",
        ))
        return candidate

    async def _table(self, session: AsyncSession, table_id: str, *, lock: bool):
        query = select(poker_tables).where(poker_tables.c.id == table_id)
        if lock:
            query = query.with_for_update()
        table = (await session.execute(query)).mappings().one_or_none()
        if table is None or table["asset"] != CASH_USDT:
            raise CashSeatError("CASH table not found")
        for field in ("small_blind_micros", "big_blind_micros", "chip_micros"):
            if type(table[field]) is not int or table[field] <= 0:
                raise CashSeatError("CASH table has invalid exact-chip parameters")
        if (
            table["small_blind_micros"] % table["chip_micros"]
            or table["big_blind_micros"] % table["chip_micros"]
        ):
            raise CashSeatError("CASH blinds must be whole chips")
        return table

    @staticmethod
    def _validate_buy_in(table, seat_no: int, amount: int) -> None:
        if type(seat_no) is not int or not 0 <= seat_no <= 5:
            raise CashSeatError("invalid seat number")
        if type(amount) is not int or amount <= 0 or amount % table["chip_micros"]:
            raise CashSeatError("cash buy-in must be a positive whole chip amount")
        minimum = table["big_blind_micros"] * table["min_buy_in_bb"]
        maximum = table["big_blind_micros"] * table["max_buy_in_bb"]
        if not minimum <= amount <= maximum:
            raise CashSeatError("cash buy-in is outside the table limits")

    @staticmethod
    def _engine(table) -> PokerEngine:
        chip = table["chip_micros"]
        return PokerEngine(
            exact_chips=True,
            small_blind=table["small_blind_micros"] // chip,
            big_blind=table["big_blind_micros"] // chip,
        )

    @staticmethod
    def _seat_result(row) -> CashSeat:
        return CashSeat(
            row["id"], row["user_id"], row["table_id"], row["seat_no"],
            row["cash_escrow_account_id"], row["stack_micros"],
        )

    @staticmethod
    def _require_postgres(session: AsyncSession) -> None:
        if session.get_bind().dialect.name != "postgresql":
            raise CashRuntimeError("cash game requires PostgreSQL row locks")
