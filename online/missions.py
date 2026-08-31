"""Daily missions: three a day, none of which asks for a result.

The rule from docs/progression.md §70 is the whole design constraint. A mission
either rewards ordinary activity or notices something that happened anyway; it
never pays for winning. Winning Session, Three Showdowns and Big Pot were all
cut from the dailies for that reason -- the first rewards standing up the
moment you are one blind ahead, and the other two reward calling too much.

Assignment is derived, not stored: the same player on the same day always draws
the same three missions, so nothing has to be written before the first hand is
played. A reroll is the one thing that has to be remembered, and it is the only
reason a mission row exists before it has any progress.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from online.schema import user_missions


#: Positions the engine deals, in mask order. Heads-up labels the one seat
#: "BTN / SB"; it counts as the button rather than as two positions.
POSITIONS = ("BTN", "SB", "BB", "UTG", "HJ", "CO")

SLOTS = ("volume", "session", "variety")
COMPLETION_XP = 50

#: One clock for the whole progression (§8): UTC+3, no daylight saving, so a
#: day is always 24 hours and the boundary is the same for every player.
MSK = timezone(timedelta(hours=3))


def next_reset(now: datetime) -> datetime:
    """When today's missions are replaced -- what the page counts down to."""
    local = now.astimezone(MSK)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return midnight.astimezone(timezone.utc)


@dataclass(frozen=True)
class Mission:
    code: str
    slot: str
    title: str
    target: int
    xp: int
    #: Which fact answers it. A mission is only evaluated where its fact is
    #: known, so nothing has to be queried on the off chance.
    source: str


POOLS: dict[str, tuple[Mission, ...]] = {
    "volume": (
        Mission("play_20", "volume", "Сыграйте 20 раздач", 20, 50, "hands"),
        Mission("play_30", "volume", "Сыграйте 30 раздач", 30, 50, "hands"),
        Mission("play_40", "volume", "Сыграйте 40 раздач", 40, 50, "hands"),
        Mission("play_60", "volume", "Сыграйте 60 раздач", 60, 50, "hands"),
    ),
    "session": (
        Mission("finish_session", "session", "Завершите игровую сессию", 1, 55, "sessions"),
        Mission("two_tables", "session", "Сыграйте за двумя разными столами", 2, 55, "tables"),
        Mission(
            "full_table_20", "session", "Сыграйте 20 раздач за столом с 5+ участниками",
            20, 55, "full_table_hands",
        ),
    ),
    "variety": (
        # Four rather than the six of §8: a mission has to be finishable at the
        # table the player actually finds, and six positions needs a full ring.
        Mission("four_positions", "variety", "Сыграйте с четырёх разных позиций", 4, 60, "positions"),
        Mission("long_session", "variety", "Проведите сессию на 40+ раздач", 40, 60, "longest_session"),
    ),
}

MISSIONS = {mission.code: mission for pool in POOLS.values() for mission in pool}


def position_bit(position: str) -> int:
    """The mask bit for one dealt position, or 0 for one we do not track."""
    label = position.split("/")[0].strip()
    return 1 << POSITIONS.index(label) if label in POSITIONS else 0


def positions_played(mask: int) -> int:
    return bin(mask).count("1")


def assigned(user_id: str, day: str, slot: str, *, offset: int = 0) -> Mission:
    """The mission this player draws in this slot today.

    Derived from the player and the date rather than rolled and stored, so the
    same day always shows the same three. `offset` is what a reroll moves by.
    """
    pool = POOLS[slot]
    digest = hashlib.sha256(f"{user_id}:{day}:{slot}".encode()).digest()
    return pool[(int.from_bytes(digest[:8], "big") + offset) % len(pool)]


async def state_for(session: AsyncSession, user_id: str, day: str) -> dict[str, dict]:
    """Every slot's mission today, with whatever has been written about it."""
    rows = {
        row["slot"]: row
        for row in (
            await session.execute(
                select(user_missions).where(
                    user_missions.c.user_id == user_id, user_missions.c.day == day
                )
            )
        ).mappings().all()
    }
    out = {}
    for slot in SLOTS:
        row = rows.get(slot)
        mission = assigned(user_id, day, slot, offset=row["reroll_offset"] if row else 0)
        out[slot] = {
            "mission": mission,
            "progress": row["progress"] if row else 0,
            "completed_at": row["completed_at"] if row else None,
            "rerolled": bool(row and row["reroll_offset"]),
        }
    return out


async def rerolled_today(session: AsyncSession, user_id: str, day: str) -> bool:
    return bool((
        await session.execute(
            select(user_missions.c.slot).where(
                user_missions.c.user_id == user_id,
                user_missions.c.day == day,
                user_missions.c.reroll_offset != 0,
            )
        )
    ).first())


async def reroll(session: AsyncSession, user_id: str, day: str, slot: str, now: datetime) -> bool:
    """Swap one unfinished mission for the next in its pool. One a day.

    Returns whether it happened: a finished mission is not swapped, and neither
    is anything once the day's one reroll is spent.
    """
    if slot not in POOLS or await rerolled_today(session, user_id, day):
        return False
    row = (
        await session.execute(
            select(user_missions).where(
                user_missions.c.user_id == user_id,
                user_missions.c.day == day,
                user_missions.c.slot == slot,
            )
        )
    ).mappings().first()
    if row and row["completed_at"]:
        return False
    values = dict(reroll_offset=1, progress=0, updated_at=now)
    if row is None:
        await session.execute(user_missions.insert().values(
            user_id=user_id, day=day, slot=slot, **values,
        ))
    else:
        await session.execute(
            update(user_missions)
            .where(
                user_missions.c.user_id == user_id,
                user_missions.c.day == day,
                user_missions.c.slot == slot,
            )
            .values(**values)
        )
    return True


async def advance(
    session: AsyncSession, *, user_id: str, day: str, facts: dict[str, int], now: datetime
) -> list[Mission]:
    """Record what today's facts say and return the missions just finished.

    Only slots whose fact is in `facts` are looked at: settlement knows the day
    row and nothing about sessions, and the end of a session knows both.
    """
    finished = []
    for slot, current in (await state_for(session, user_id, day)).items():
        mission = current["mission"]
        if mission.source not in facts or current["completed_at"]:
            continue
        progress = min(facts[mission.source], mission.target)
        if progress == current["progress"]:
            continue
        done = progress >= mission.target
        values = dict(progress=progress, updated_at=now)
        if done:
            values["completed_at"] = now
            finished.append(mission)
        exists = (
            await session.execute(
                select(user_missions.c.slot).where(
                    user_missions.c.user_id == user_id,
                    user_missions.c.day == day,
                    user_missions.c.slot == slot,
                )
            )
        ).first()
        if exists is None:
            await session.execute(user_missions.insert().values(
                user_id=user_id, day=day, slot=slot, reroll_offset=0, **values,
            ))
        else:
            await session.execute(
                update(user_missions)
                .where(
                    user_missions.c.user_id == user_id,
                    user_missions.c.day == day,
                    user_missions.c.slot == slot,
                )
                .values(**values)
            )
    return finished


async def all_complete(session: AsyncSession, user_id: str, day: str) -> bool:
    return all(
        slot["completed_at"] is not None
        for slot in (await state_for(session, user_id, day)).values()
    )
