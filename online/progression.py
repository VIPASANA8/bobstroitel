"""Account progression: the XP one played hand is worth, and the level it buys.

Every number here comes from docs/progression.md. Two things are worth knowing
before changing any of them:

* a day is an MSK day, the same boundary for everybody (§8), so the soft cap
  cannot be reset by flying somewhere;
* XP is granted by the settlement that writes the hand, never by the client.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from online import achievements
from online.schema import (
    hand_actions,
    hand_players,
    hands,
    play_sessions,
    poker_tables,
    progress_days,
    system_players,
    user_progression,
    xp_events,
)


# UTC+3 with no daylight saving, so every day is exactly 24 hours long and the
# boundary is the same for every player -- which is what lets an idempotency
# key carry a bare date (§13).
MSK = timezone(timedelta(hours=3))

FULL_RATE_HANDS = 150   # hands 1..150 pay 1 XP
HALF_RATE_HANDS = 300   # hands 151..300 pay 0.5 XP, see xp_for_hand
DAILY_HAND_XP_CAP = 150 + (300 - 150) // 2   # 225, what the two bands add up to

# Published totals from §6. Every gap between two of them divides evenly by the
# levels it spans, so the ladder below joins them with a constant step and the
# anchors survive untouched -- no rounding, and the cost of a level never falls.
_ANCHORS = (
    (1, 0), (2, 150), (3, 350), (4, 600), (5, 900), (10, 3_000), (15, 5_500),
    (20, 9_000), (25, 13_000), (30, 18_000), (35, 23_500), (40, 30_000),
    (45, 37_000), (50, 45_000),
)


def _ladder() -> tuple[int, ...]:
    """Total XP standing at each level, level 1 first."""
    totals = [_ANCHORS[0][1]]
    for (level, xp), (next_level, next_xp) in zip(_ANCHORS, _ANCHORS[1:]):
        span = next_level - level
        step, remainder = divmod(next_xp - xp, span)
        assert not remainder, f"anchor {next_level} does not divide evenly from {level}"
        totals.extend(xp + step * n for n in range(1, span + 1))
    return tuple(totals)


LEVEL_XP = _ladder()
MAX_LEVEL = len(LEVEL_XP)

RANKS = (
    (5, "ROOKIE"), (10, "PLAYER"), (20, "REGULAR"), (30, "GRINDER"),
    (40, "SHARK"), (49, "ELITE"), (50, "VETERAN"),
)


def msk_day(now: datetime) -> str:
    return now.astimezone(MSK).strftime("%Y-%m-%d")


def xp_for_hand(hand_number: int) -> int:
    """XP for the day's `hand_number`-th eligible hand.

    The second band is worth half a point a hand. Rather than carry halves
    through every total, every other hand in that band pays 1 and the rest pay
    nothing: the same 75 XP across the band, in integers the whole way.
    """
    if hand_number <= FULL_RATE_HANDS:
        return 1
    if hand_number <= HALF_RATE_HANDS:
        return hand_number % 2
    return 0


def level_for_xp(xp: int) -> int:
    return max((level for level, threshold in enumerate(LEVEL_XP, start=1) if xp >= threshold), default=1)


def xp_to_next_level(xp: int) -> int | None:
    """XP still owed for the next level, or None at the top of the ladder."""
    remaining = [threshold - xp for threshold in LEVEL_XP if threshold > xp]
    return min(remaining) if remaining else None


def rank_for_level(level: int) -> str:
    return next(name for ceiling, name in RANKS if level <= ceiling)


async def record_hand(
    session: AsyncSession,
    *,
    owner_kind: str,
    owner_id: str,
    hand_id: str,
    net_units: int,
    big_blind_units: int,
    counts_results: bool,
    now: datetime,
    hole_cards: Sequence[str] = (),
    board: Sequence[str] = (),
    pot_bb: float = 0.0,
    opponent_ids: frozenset[str] = frozenset(),
) -> int:
    """Count one eligible hand for this player and grant what it is worth.

    Returns the XP granted, which is 0 once the day's soft cap is spent -- the
    hand itself is counted either way, and so are its achievements. Only the
    XP stops.

    `counts_results` is the rule from §3: volume counts wherever it is played,
    but anything measured in big blinds counts only at a network table. Two
    accounts alone in a room they opened can otherwise write any result they
    like into their own statistics.

    The caller must reach here exactly once per hand per player. Settlement
    guards on hands.completed_at, which is null until the very transaction
    that calls this commits -- a replayed settlement therefore counts nothing.
    """
    day = msk_day(now)
    hands_today = await _count_hand(session, owner_kind, owner_id, day)
    amount = xp_for_hand(hands_today)
    tally: dict[str, object] = {}
    if amount:
        tally["xp"] = progress_days.c.xp + amount
    if net_units > 0:
        tally["hands_won"] = progress_days.c.hands_won + 1
    if counts_results and owner_kind == "user":
        tally["result_hands"] = progress_days.c.result_hands + 1
        tally["net_bb_x100"] = progress_days.c.net_bb_x100 + round(
            net_units * 100 / big_blind_units
        )
    if tally:
        await session.execute(
            update(progress_days)
            .where(
                progress_days.c.owner_kind == owner_kind,
                progress_days.c.owner_id == owner_id,
                progress_days.c.day == day,
            )
            .values(**tally)
        )

    if owner_kind != "user":
        # A bot has a level for one reason: so its seat reads like everyone
        # else's (§5). No events, no achievements, nothing else to keep.
        if amount:
            await session.execute(
                update(system_players)
                .where(system_players.c.id == owner_id)
                .values(xp=system_players.c.xp + amount)
            )
        return amount

    points = await achievements.record_hand(
        session,
        user_id=owner_id,
        hole_cards=list(hole_cards),
        board=list(board),
        won=net_units > 0,
        pot_bb=pot_bb,
        counts_results=counts_results,
        opponent_ids=set(opponent_ids),
        now=now,
    )
    if amount:
        # The event row is the audit trail and the second lock: its unique key
        # turns a double grant into an error instead of a silent extra level.
        await session.execute(xp_events.insert().values(
            id=uuid.uuid4().hex,
            user_id=owner_id,
            amount=amount,
            source="hand",
            reference=hand_id,
            idempotency_key=f"hand:{hand_id}:{owner_id}",
        ))
    if amount or points:
        await add_progression(session, owner_id, xp=amount, ap=points, now=now)
    return amount


async def _count_hand(session: AsyncSession, owner_kind: str, owner_id: str, day: str) -> int:
    """This hand's ordinal in the owner's day, counting from 1.

    ponytail: read-then-write rather than an upsert. A user holds one active
    seat (uq_active_table_seat_user) and settlement runs under the table's own
    lock, so nothing else is counting this owner's hands at the same moment.
    A second writer outside settlement would need a real upsert here.
    """
    where = (
        progress_days.c.owner_kind == owner_kind,
        progress_days.c.owner_id == owner_id,
        progress_days.c.day == day,
    )
    played = (
        await session.execute(select(progress_days.c.hands).where(*where))
    ).scalar_one_or_none()
    if played is None:
        await session.execute(progress_days.insert().values(
            owner_kind=owner_kind, owner_id=owner_id, day=day, hands=1,
        ))
        return 1
    await session.execute(update(progress_days).where(*where).values(hands=played + 1))
    return played + 1


async def add_progression(
    session: AsyncSession, user_id: str, *, xp: int, ap: int, now: datetime
) -> None:
    """Add to a player's totals, creating the row on their first hand.

    Both currencies go through here because they arrive together and the day's
    XP cap does not stop achievement points: a capped player who lands a Royal
    still collects for it.
    """
    row = (
        await session.execute(
            select(user_progression.c.xp, user_progression.c.achievement_points).where(
                user_progression.c.user_id == user_id
            )
        )
    ).first()
    if row is None:
        await session.execute(user_progression.insert().values(
            user_id=user_id, xp=xp, level=level_for_xp(xp), achievement_points=ap,
        ))
        return
    total = row[0] + xp
    await session.execute(
        update(user_progression)
        .where(user_progression.c.user_id == user_id)
        .values(
            xp=total,
            level=level_for_xp(total),
            achievement_points=row[1] + ap,
            updated_at=now,
        )
    )


async def close_play_session(
    session: AsyncSession,
    *,
    user_id: str,
    table_id: str,
    seated_at: datetime,
    now: datetime,
) -> str | None:
    """Write the report for one finished occupancy. Returns its id, or None.

    Called as the seat is released, which is the only moment the whole session
    is known and the last moment the seat still says when it began: the row is
    blanked and reused, not deleted.

    A player who sat down and never finished a hand gets no report rather than
    an empty one.
    """
    played = (
        select(hand_players.c.hand_id.label("hand_id"), hand_players.c.net_units.label("net_units"))
        .join(hands, hands.c.id == hand_players.c.hand_id)
        .where(
            hand_players.c.user_id == user_id,
            hands.c.table_id == table_id,
            hands.c.completed_at.is_not(None),
            # Seat rows are reused, so the same player may have several
            # sessions at one table. This is what separates them.
            hands.c.completed_at >= seated_at,
        )
        .subquery()
    )
    counted, net = (
        await session.execute(select(func.count(), func.sum(played.c.net_units)).select_from(played))
    ).one()
    if not counted:
        return None
    # A subquery rather than the list of hand ids: a long session runs to
    # hundreds of hands, and SQLite has a ceiling on bound parameters.
    hand_ids = select(played.c.hand_id)
    biggest_pot = (
        await session.execute(
            select(func.max(hand_actions.c.pot_after_units)).where(hand_actions.c.hand_id.in_(hand_ids))
        )
    ).scalar() or 0
    xp_earned = (
        await session.execute(
            select(func.sum(xp_events.c.amount)).where(
                xp_events.c.user_id == user_id,
                xp_events.c.reference.in_(hand_ids),
            )
        )
    ).scalar() or 0
    big_blind_units, created_by = (
        await session.execute(
            select(poker_tables.c.big_blind_units, poker_tables.c.created_by)
            .where(poker_tables.c.id == table_id)
        )
    ).one()
    # A comeback is a shape across a session, not a fact about one hand, so it
    # is read here rather than at settlement -- and like every other result it
    # is only earned at a network table (§3).
    if created_by is None:
        stacks_bb = [
            stack / big_blind_units
            for stack in (
                await session.execute(
                    select(hand_players.c.start_stack_units)
                    .join(hands, hands.c.id == hand_players.c.hand_id)
                    .where(
                        hand_players.c.user_id == user_id,
                        hands.c.table_id == table_id,
                        hands.c.completed_at.is_not(None),
                        hands.c.completed_at >= seated_at,
                    )
                    .order_by(hands.c.completed_at)
                )
            ).scalars().all()
        ]
        points = 0
        for code in achievements.comeback_codes(stacks_bb):
            points += await achievements.advance(
                session, user_id=user_id, code=code, high_water=1, now=now,
            )
        if points:
            await add_progression(session, user_id, xp=0, ap=points, now=now)
    report_id = uuid.uuid4().hex
    await session.execute(play_sessions.insert().values(
        id=report_id,
        user_id=user_id,
        table_id=table_id,
        started_at=seated_at,
        ended_at=now,
        hands=counted,
        net_units=net or 0,
        big_blind_units=big_blind_units,
        biggest_pot_units=biggest_pot,
        xp_earned=xp_earned,
    ))
    return report_id
