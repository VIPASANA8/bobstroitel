"""What a referrer and a partner are owed, and when.

Three rules hold the whole thing up, and every line below exists to keep one
of them true:

1. A referrer is paid a share of money the project actually earned. Not of
   turnover, not of deposits, not of a player's losses to another player.
2. The unit that money is measured in is the *whole referral group*. One
   referral winning 100 and another losing 100 is a project that earned
   nothing, and a referrer who is paid for the first while the second is
   quietly filed away is a referrer being paid out of the house's pocket.
3. What the group is down never expires. Not at midnight, not at the end of
   the month, not when the boosted rate runs out. It is carried until future
   profit covers it.

Poker and Cube are settled apart and never touch: Poker's income is rake the
house actually kept, Cube's is what the house won, and the partner's share is
Cube's alone. Only the Cube half is implemented here -- see
docs/referrals-and-profit-share.md for what Poker still needs before its half
can be honest, and why what is missing is data and not arithmetic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from cash.cube import CUBE_ACCOUNT
from cash.holds import CashUserFrozen, assert_not_frozen
from cash.ledger import CashLedger
from online.schema import (
    cash_accounts, cube_adjustments, cube_rounds, partner_settlements, partner_shares,
    referral_settlements, referrals, users,
)


logger = logging.getLogger(__name__)

#: The first 30 days after the referral's first real-money round pay 15%;
#: everything after that pays 5%, for as long as the account plays.
BOOST_BPS = 1_500
BASE_BPS = 500
BOOST_DAYS = 30
#: Referral money waits here between being earned and being spendable.
REFERRAL_PENDING = "referral-pending"
#: What the partner is owed. Paying it out is an operator's job, not a job's.
PARTNER_PAYABLE = "partner-payable"


@dataclass(frozen=True)
class Award:
    """One referral's part of a day, and what it earned its referrer."""

    user_id: str
    rate_bps: int
    pnl_micros: int
    base_micros: int
    amount_micros: int


@dataclass(frozen=True)
class GroupPlan:
    gross_micros: int
    carryover_before_micros: int
    carryover_after_micros: int
    base_micros: int
    amount_micros: int
    awards: tuple[Award, ...]

    def as_breakdown(self) -> list[dict[str, object]]:
        return [
            {
                "user_id": award.user_id, "rate_bps": award.rate_bps,
                "pnl_micros": award.pnl_micros, "base_micros": award.base_micros,
                "amount_micros": award.amount_micros,
            }
            for award in self.awards
        ]


def _split(base: int, weights: list[tuple[tuple[str, int], int]]) -> dict[tuple[str, int], int]:
    """Share `base` out in proportion to `weights`, to the last micro.

    Largest remainder, ties broken by key, so the same input always splits the
    same way and the parts always add back up to the whole. Anything less and
    the ledger and the report disagree by a micro nobody can find.
    """
    total = sum(weight for _, weight in weights)
    shares: dict[tuple[str, int], int] = {}
    remainders = []
    assigned = 0
    for key, weight in weights:
        exact = base * weight
        part = exact // total
        shares[key] = part
        assigned += part
        remainders.append((exact - part * total, key))
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for _, key in remainders[: base - assigned]:
        shares[key] += 1
    return shares


def plan_group(contributions, carryover_before_micros: int = 0) -> GroupPlan:
    """The day's reward for one referrer, from their group's whole result.

    `contributions` is (referral user id, rate in bps, result in micros), the
    result being the *project's*: positive when the house won. A referral that
    crossed out of its boosted period mid-day appears twice, once at each
    rate, so the boost never leaks into the days after it.

    The order matters and is the point. The group's losses come off first, at
    the group level; only what is left is anybody's base; and only then does a
    rate apply. Paying 15% of a winning referral before a losing one has been
    covered is how a referrer comes to earn more than the project did.
    """
    rows = [((str(user_id), int(rate)), int(pnl)) for user_id, rate, pnl in contributions]
    gross = sum(pnl for _, pnl in rows)
    total = gross + carryover_before_micros
    base = max(total, 0)
    carryover_after = min(total, 0)
    positive = [(key, pnl) for key, pnl in rows if pnl > 0]
    shares = _split(base, positive) if base and positive else {}
    awards = []
    for key, pnl in sorted(rows):
        user_id, rate_bps = key
        share = shares.get(key, 0)
        awards.append(Award(
            user_id=user_id, rate_bps=rate_bps, pnl_micros=pnl, base_micros=share,
            # Floor: the fraction of a micro stays with the house, the only
            # direction that cannot pay out money that was never earned.
            amount_micros=share * rate_bps // 10_000,
        ))
    return GroupPlan(
        gross_micros=gross,
        carryover_before_micros=carryover_before_micros,
        carryover_after_micros=carryover_after,
        base_micros=base,
        amount_micros=sum(award.amount_micros for award in awards),
        awards=tuple(awards),
    )


def period_bounds(kind: str, day: date) -> tuple[date, date]:
    """The week (Monday to Sunday) or the calendar month `day` falls in."""
    if kind == "week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    start = day.replace(day=1)
    following = (start + timedelta(days=32)).replace(day=1)
    return start, following - timedelta(days=1)


def next_period(kind: str, start: date) -> date:
    if kind == "week":
        return start + timedelta(days=7)
    return period_bounds("month", start + timedelta(days=32))[0]


def _aware(stamp: datetime | None) -> datetime | None:
    """SQLite hands back naive timestamps where PostgreSQL keeps the zone."""
    if stamp is None:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def rate_for(created_at: datetime, activated_at: datetime | None) -> int:
    """15% inside the first 30 days of real-money play, 5% after."""
    activated = _aware(activated_at)
    if activated is None:
        return BOOST_BPS
    return BOOST_BPS if _aware(created_at) < activated + timedelta(days=BOOST_DAYS) else BASE_BPS


class CashSettlements:
    """The daily pass: reward, release, and the partner's share.

    Every step is idempotent -- one row per (referrer, source, day), one
    ledger key per row -- so running it twice, or from two processes at once,
    pays nobody twice. That is the whole safety argument for wiring it into a
    loop that may well fire more than once a day.
    """

    #: How far back one pass reaches for days nobody settled. Long enough to
    #: cover an outage, short enough to stay a bounded scan.
    LOOKBACK_DAYS = 90

    def __init__(
        self, sessions, *, hold_days: int = 7, partner_period: str = "month", now=None,
    ) -> None:
        self.sessions = sessions
        self.hold_days = hold_days
        self.partner_period = partner_period
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.ledger = CashLedger()

    async def run(self) -> dict[str, int]:
        """One pass, in order: the days' rewards, releases, then the partner."""
        today = self.now().date()
        settled = 0
        for day in await self._pending_days(today):
            settled += len(await self.settle_cube_day(day))
        released = await self.release_due()
        partner = len(await self.settle_partner_periods(today - timedelta(days=1)))
        return {
            "referral_settlements": settled,
            "released": released,
            "partner_settlements": partner,
        }

    async def _pending_days(self, today: date) -> list[date]:
        yesterday = today - timedelta(days=1)
        async with self.sessions() as session:
            last = await session.scalar(select(func.max(referral_settlements.c.period_start)))
            first_round = await session.scalar(select(func.min(cube_rounds.c.created_at)))
        if first_round is None:
            return []
        start = (
            _aware(first_round).date() if last is None
            else _as_date(last) + timedelta(days=1)
        )
        # A day nobody earned anything on writes no row, so `last` does not
        # move and that day is looked at again tomorrow. Harmless and cheap;
        # the floor is what keeps it from becoming a scan of all history.
        start = max(start, yesterday - timedelta(days=self.LOOKBACK_DAYS))
        if start > yesterday:
            return []
        return [start + timedelta(days=offset) for offset in range((yesterday - start).days + 1)]

    async def settle_cube_day(self, day: date) -> list[str]:
        """Settle every referrer's Cube group for one UTC day."""
        start = datetime.combine(day, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        async with self.sessions() as session:
            async with session.begin():
                await self._activate(session, end)
            groups = await self._contributions(session, start, end)
        written = []
        for referrer_id, contributions in sorted(groups.items()):
            settlement_id = await self._settle_group(referrer_id, day, contributions)
            if settlement_id:
                written.append(settlement_id)
        return written

    async def _activate(self, session, before: datetime) -> None:
        """Start the boosted period at the first real-money round, not signup."""
        first_round = select(func.min(cube_rounds.c.created_at)).where(
            cube_rounds.c.user_id == referrals.c.user_id,
            cube_rounds.c.created_at < before,
        ).scalar_subquery()
        # ponytail: Cube only, because Poker has no real-money volume yet. When
        # cash tables open, the first cash hand counts here too -- one LEAST().
        await session.execute(update(referrals).where(
            referrals.c.activated_at.is_(None),
        ).values(activated_at=first_round))

    async def _contributions(self, session, start: datetime, end: datetime):
        rows = (await session.execute(
            select(
                referrals.c.referrer_id, referrals.c.user_id, referrals.c.activated_at,
                cube_rounds.c.created_at,
                (cube_rounds.c.stake_micros - cube_rounds.c.payout_micros).label("pnl"),
            ).select_from(
                cube_rounds
                .join(referrals, referrals.c.user_id == cube_rounds.c.user_id)
                .join(users, users.c.id == referrals.c.referrer_id)
            ).where(
                cube_rounds.c.created_at >= start,
                cube_rounds.c.created_at < end,
                # An owner or a partner is paid through the partner's share and
                # never through the players' programme.
                users.c.internal.is_(False),
            )
        )).mappings().all()
        # ponytail: one row per round. A GROUP BY in SQL if a day ever brings
        # more rounds than a single pass wants to carry in memory.
        groups: dict[str, dict[tuple[str, int], int]] = {}
        for row in rows:
            rate = rate_for(row["created_at"], row["activated_at"])
            group = groups.setdefault(row["referrer_id"], {})
            key = (row["user_id"], rate)
            group[key] = group.get(key, 0) + int(row["pnl"])
        return groups

    async def _settle_group(self, referrer_id: str, day: date, contributions) -> str | None:
        async with self.sessions() as session:
            async with session.begin():
                later = await session.scalar(select(func.count()).select_from(
                    referral_settlements
                ).where(
                    referral_settlements.c.referrer_id == referrer_id,
                    referral_settlements.c.source == "cube",
                    referral_settlements.c.period_start >= day,
                ))
                if later:
                    # Already settled, or a later day is -- and settling out of
                    # order would fork the carryover chain.
                    return None
                carryover = await session.scalar(select(
                    referral_settlements.c.carryover_after_micros
                ).where(
                    referral_settlements.c.referrer_id == referrer_id,
                    referral_settlements.c.source == "cube",
                    referral_settlements.c.period_start < day,
                ).order_by(referral_settlements.c.period_start.desc()).limit(1))
                plan = plan_group(
                    [(user_id, rate, pnl) for (user_id, rate), pnl in contributions.items()],
                    int(carryover or 0),
                )
                settlement_id = uuid4().hex
                now = self.now()
                paid = plan.amount_micros > 0
                try:
                    await session.execute(referral_settlements.insert().values(
                        id=settlement_id, referrer_id=referrer_id, source="cube",
                        period_start=day, gross_micros=plan.gross_micros,
                        carryover_before_micros=plan.carryover_before_micros,
                        carryover_after_micros=plan.carryover_after_micros,
                        base_micros=plan.base_micros, amount_micros=plan.amount_micros,
                        breakdown_json=plan.as_breakdown(),
                        # Nothing to hold is nothing to review: a zero reward is
                        # closed where it is written.
                        status="pending" if paid else "available",
                        released_at=None if paid else now,
                        created_at=now,
                    ))
                    if paid:
                        await self.ledger.post(
                            session, scope="referral",
                            key=f"cube:{referrer_id}:{day.isoformat()}",
                            kind="referral_reward", reference_id=settlement_id,
                            actor="system:referral-settlement",
                            postings={
                                await _account(session, "clearing", None, CUBE_ACCOUNT):
                                    -plan.amount_micros,
                                await _account(session, "clearing", None, REFERRAL_PENDING):
                                    plan.amount_micros,
                            },
                        )
                except IntegrityError:
                    # Another process settled this day first. Its row is the row.
                    return None
        return settlement_id

    async def release_due(self) -> int:
        """Move rewards that have sat out the hold onto the referrer's balance.

        The hold is what makes a reward reversible: a chargeback, a correction
        or a fraud review lands inside it. A frozen account simply keeps
        waiting -- the reward stays pending until somebody has looked at it.
        """
        cutoff = self.now() - timedelta(days=self.hold_days)
        async with self.sessions() as session:
            due = [row["id"] for row in (await session.execute(select(
                referral_settlements.c.id
            ).where(
                referral_settlements.c.status == "pending",
                referral_settlements.c.amount_micros > 0,
                referral_settlements.c.created_at <= cutoff,
            ).order_by(referral_settlements.c.created_at))).mappings().all()]
        released = 0
        for settlement_id in due:
            async with self.sessions() as session:
                async with session.begin():
                    row = (await session.execute(select(referral_settlements).where(
                        referral_settlements.c.id == settlement_id,
                    ).with_for_update())).mappings().one()
                    if row["status"] != "pending":
                        continue
                    try:
                        await assert_not_frozen(session, row["referrer_id"])
                    except CashUserFrozen:
                        continue
                    amount = int(row["amount_micros"])
                    await self.ledger.post(
                        session, scope="referral", key=f"release:{settlement_id}",
                        kind="referral_release", reference_id=settlement_id,
                        actor="system:referral-settlement",
                        postings={
                            await _account(session, "clearing", None, REFERRAL_PENDING): -amount,
                            await _account(
                                session, "available", row["referrer_id"], row["referrer_id"],
                            ): amount,
                        },
                    )
                    await session.execute(update(referral_settlements).where(
                        referral_settlements.c.id == settlement_id,
                    ).values(status="available", released_at=self.now()))
                    released += 1
        return released

    async def reverse(self, settlement_id: str, *, actor: str) -> bool:
        """Take back a reward that has not been released yet.

        Only while it is pending: once the money is on a balance it may have
        been played or withdrawn, and clawing it back is an operator's
        adjustment with a person behind it, not a job's.

        The base stays spent. A reversed day cannot fund a second reward,
        which errs towards paying less than was earned -- the only direction
        that cannot invent money.
        """
        async with self.sessions() as session:
            async with session.begin():
                row = (await session.execute(select(referral_settlements).where(
                    referral_settlements.c.id == settlement_id,
                ).with_for_update())).mappings().one_or_none()
                if row is None or row["status"] != "pending" or not row["amount_micros"]:
                    return False
                amount = int(row["amount_micros"])
                await self.ledger.post(
                    session, scope="referral", key=f"reverse:{settlement_id}",
                    kind="referral_reversal", reference_id=settlement_id, actor=actor,
                    postings={
                        await _account(session, "clearing", None, REFERRAL_PENDING): -amount,
                        await _account(session, "clearing", None, CUBE_ACCOUNT): amount,
                    },
                )
                await session.execute(update(referral_settlements).where(
                    referral_settlements.c.id == settlement_id,
                ).values(status="reversed", released_at=self.now()))
        return True

    async def settle_partner_periods(self, settled_through: date) -> list[str]:
        """Close every complete week and month up to `settled_through`.

        Both cadences are written; only the configured one moves money. Two
        paying cadences would share the same profit twice, and a week that is
        only a report is worth having anyway -- it is the number the partner
        asks about on Monday.
        """
        async with self.sessions() as session:
            first_round = await session.scalar(select(func.min(cube_rounds.c.created_at)))
            configured = await session.scalar(select(func.count()).select_from(partner_shares))
        if first_round is None or not configured:
            return []
        written = []
        for kind in ("week", "month"):
            start = period_bounds(kind, _aware(first_round).date())[0]
            for _ in range(self.LOOKBACK_DAYS):
                bounds = period_bounds(kind, start)
                if bounds[1] > settled_through:
                    break
                settlement_id = await self._settle_partner_period(kind, bounds)
                if settlement_id:
                    written.append(settlement_id)
                start = next_period(kind, start)
        return written

    async def _settle_partner_period(self, kind: str, bounds: tuple[date, date]) -> str | None:
        start, end = bounds
        async with self.sessions() as session:
            async with session.begin():
                exists = await session.scalar(select(func.count()).select_from(
                    partner_settlements
                ).where(
                    partner_settlements.c.period_kind == kind,
                    partner_settlements.c.period_start == start,
                ))
                if exists:
                    return None
                share_bps = await session.scalar(select(partner_shares.c.share_bps).where(
                    partner_shares.c.effective_from <= start,
                ).order_by(partner_shares.c.effective_from.desc()).limit(1))
                if share_bps is None:
                    # The partnership starts later than this period does.
                    return None
                window_start = datetime.combine(start, time.min, tzinfo=timezone.utc)
                window_end = datetime.combine(end, time.min, tzinfo=timezone.utc) + timedelta(days=1)
                gross = int(await session.scalar(select(func.coalesce(func.sum(
                    cube_rounds.c.stake_micros - cube_rounds.c.payout_micros,
                ), 0)).where(
                    cube_rounds.c.created_at >= window_start,
                    cube_rounds.c.created_at < window_end,
                )) or 0)
                # Referral cost belongs to the day it was earned on, not the day
                # it is released: the partner's share and the referrer's reward
                # are two halves of the same profit.
                referral_cost = int(await session.scalar(select(func.coalesce(func.sum(
                    referral_settlements.c.amount_micros,
                ), 0)).where(
                    referral_settlements.c.source == "cube",
                    referral_settlements.c.status != "reversed",
                    referral_settlements.c.period_start >= start,
                    referral_settlements.c.period_start <= end,
                )) or 0)
                adjustments = int(await session.scalar(select(func.coalesce(func.sum(
                    cube_adjustments.c.amount_micros,
                ), 0)).where(
                    cube_adjustments.c.occurred_on >= start,
                    cube_adjustments.c.occurred_on <= end,
                )) or 0)
                carryover = int(await session.scalar(select(
                    partner_settlements.c.carryover_after_micros
                ).where(
                    partner_settlements.c.period_kind == kind,
                    partner_settlements.c.period_start < start,
                ).order_by(partner_settlements.c.period_start.desc()).limit(1)) or 0)
                net = gross - referral_cost + adjustments
                total = net + carryover
                amount = total * int(share_bps) // 10_000 if total > 0 else 0
                posted = kind == self.partner_period and amount > 0
                settlement_id = uuid4().hex
                try:
                    await session.execute(partner_settlements.insert().values(
                        id=settlement_id, period_kind=kind, period_start=start, period_end=end,
                        gross_micros=gross, referral_cost_micros=referral_cost,
                        adjustment_micros=adjustments, net_micros=net,
                        carryover_before_micros=carryover, carryover_after_micros=min(total, 0),
                        share_bps=int(share_bps), amount_micros=amount, posted=posted,
                        created_at=self.now(),
                    ))
                    if posted:
                        await self.ledger.post(
                            session, scope="partner", key=f"{kind}:{start.isoformat()}",
                            kind="cube_profit_share", reference_id=settlement_id,
                            actor="system:partner-settlement",
                            postings={
                                await _account(session, "clearing", None, CUBE_ACCOUNT): -amount,
                                await _account(session, "clearing", None, PARTNER_PAYABLE): amount,
                            },
                        )
                except IntegrityError:
                    return None
        return settlement_id


async def _account(session, kind: str, user_id: str | None, reference_id: str) -> str:
    """The account, made if this is the first time anything landed in it."""
    await session.execute(pg_insert(cash_accounts).values(
        id=uuid4().hex, kind=kind, user_id=user_id, reference_id=reference_id,
    ).on_conflict_do_nothing(
        index_elements=[cash_accounts.c.kind, cash_accounts.c.reference_id]
    ))
    return await session.scalar(select(cash_accounts.c.id).where(
        cash_accounts.c.kind == kind, cash_accounts.c.reference_id == reference_id,
    ))
