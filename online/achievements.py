"""Achievements: what has already happened to this player, recorded after it did.

Definitions live here rather than in the database. They are read on every hand
and written by nobody but a release, so a table would be a table nothing ever
updates -- and a threshold that can only change with a deploy is safer read
from the deploy.

The rule from docs/progression.md §7 is the one to keep in mind when adding to
this file: an achievement notices something, it never asks for it. Nothing here
may be worth playing a hand differently for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from online.schema import user_achievements, user_opponents
from poker.evaluator import HandEvaluator


AP_BY_RARITY = {"common": 10, "rare": 25, "epic": 60, "legendary": 150}


@dataclass(frozen=True)
class Achievement:
    code: str
    title: str
    rarity: str
    #: Thresholds the progress has to reach, in order. A one-shot has one.
    tiers: tuple[int, ...]
    #: Shown as ??? until it lands.
    secret: bool = False

    @property
    def ap_per_tier(self) -> int:
        return AP_BY_RARITY[self.rarity]


def _one_shot(code: str, title: str, rarity: str, *, secret: bool = False) -> Achievement:
    return Achievement(code, title, rarity, (1,), secret)


ACHIEVEMENTS: dict[str, Achievement] = {a.code: a for a in (
    Achievement("grind", "THE GRIND", "rare", (100, 500, 1_000, 5_000, 10_000, 50_000)),
    # In big blinds, and only where a result may be earned: two accounts alone
    # in a room they opened could otherwise mint a Historic Pot in one hand.
    Achievement("big_pot", "BIG POT", "epic", (100, 250, 500, 1_000)),
    Achievement("social", "SOCIAL", "rare", (10, 50, 100)),
    _one_shot("straight", "STRAIGHT", "common"),
    _one_shot("flush", "FLUSH", "common"),
    _one_shot("full_house", "FULL HOUSE", "common"),
    _one_shot("quads", "QUADS", "rare"),
    _one_shot("straight_flush", "STRAIGHT FLUSH", "epic"),
    _one_shot("royal_flush", "ROYAL", "legendary", secret=True),
    _one_shot("seven_deuce", "SEVEN-DEUCE", "epic", secret=True),
    _one_shot("still_alive", "STILL ALIVE", "rare"),
    _one_shot("back_from_the_dead", "BACK FROM THE DEAD", "epic"),
)}

#: Evaluator categories worth an achievement, weakest first.
_HAND_CLASSES = {4: "straight", 5: "flush", 6: "full_house", 7: "quads", 8: "straight_flush"}

#: A comeback is a low followed by a recovery, both in big blinds.
COMEBACKS = (("still_alive", 10, 50), ("back_from_the_dead", 5, 100))

_evaluator = HandEvaluator()


def tiers_completed(thresholds: tuple[int, ...], progress: int) -> int:
    return sum(1 for threshold in thresholds if progress >= threshold)


def hand_class_code(hole_cards: list[str], board: list[str]) -> str | None:
    """The achievement a finished hand made, if it made one.

    A royal flush is a straight flush to the ace, and it is the one the player
    will want to see; it is reported instead of, not as well as, the straight
    flush.
    """
    if len(hole_cards) < 2 or len(board) < 5:
        return None
    score = _evaluator.score(list(hole_cards), list(board))
    if score[0] == 8 and score[1] == 14:
        return "royal_flush"
    return _HAND_CLASSES.get(score[0])


def is_seven_deuce(hole_cards: list[str]) -> bool:
    """The worst starting hand in hold'em, offsuit."""
    if len(hole_cards) != 2:
        return False
    (first_rank, first_suit), (second_rank, second_suit) = hole_cards
    return {first_rank, second_rank} == {"7", "2"} and first_suit != second_suit


def comeback_codes(
    hands: "Sequence[tuple[int, int]]", big_blind_units: int
) -> list[str]:
    """Comebacks visible in one session's run of stacks.

    `hands` is (start, end) in units, oldest first. Both ends of every hand are
    read: a recovery that lands on the final hand of a sitting has no next
    hand to start from, and reading only starting stacks lost it.

    Order matters and is the whole achievement -- the recovery has to come
    after the low. So does where the chips came from: a stack that begins a
    hand above where the last one ended was topped up, not won, and an add-on
    is not a comeback. A rebuy therefore clears the low it followed.
    """
    earned = []
    for code, low_bb, recovered_bb in COMEBACKS:
        low = low_bb * big_blind_units
        recovered = recovered_bb * big_blind_units
        seen_low = False
        previous_end = None
        for start, end in hands:
            if previous_end is not None and start > previous_end:
                seen_low = False
            for stack in (start, end):
                if stack < low:
                    seen_low = True
                elif seen_low and stack >= recovered:
                    earned.append(code)
                    break
            else:
                previous_end = end
                continue
            break
    return earned


async def advance(
    session: AsyncSession,
    *,
    user_id: str,
    code: str,
    now: datetime,
    increment: int = 0,
    high_water: int | None = None,
) -> int:
    """Move one achievement along. Returns the AP this earned, usually 0.

    `high_water` is for the achievements that keep a best rather than a total:
    a 300 BB pot does not undo a 400 BB one.
    """
    definition = ACHIEVEMENTS[code]
    row = (
        await session.execute(
            select(user_achievements.c.progress, user_achievements.c.tier).where(
                user_achievements.c.user_id == user_id,
                user_achievements.c.code == code,
            )
        )
    ).first()
    current, current_tier = row if row else (0, 0)
    progress = max(current, high_water) if high_water is not None else current + increment
    if progress <= current and row is not None:
        return 0
    tier = tiers_completed(definition.tiers, progress)
    finished = now if tier == len(definition.tiers) and current_tier < tier else None
    values = dict(progress=progress, tier=tier, updated_at=now)
    if finished is not None:
        values["completed_at"] = finished
    if row is None:
        await session.execute(user_achievements.insert().values(
            user_id=user_id, code=code, **values,
        ))
    else:
        await session.execute(
            update(user_achievements)
            .where(user_achievements.c.user_id == user_id, user_achievements.c.code == code)
            .values(**values)
        )
    return (tier - current_tier) * definition.ap_per_tier


async def note_opponents(
    session: AsyncSession, *, user_id: str, opponent_ids: set[str], now: datetime
) -> int:
    """Record who the player just sat with. Returns how many were new.

    Read-then-write rather than an upsert, for the reason in progression.py's
    _count_hand: settlement holds the table's lock, and a hand brings at most
    five names.
    """
    candidates = opponent_ids - {user_id}
    if not candidates:
        return 0
    known = set((
        await session.execute(
            select(user_opponents.c.opponent_id).where(
                user_opponents.c.user_id == user_id,
                user_opponents.c.opponent_id.in_(candidates),
            )
        )
    ).scalars().all())
    fresh = candidates - known
    for opponent_id in sorted(fresh):
        await session.execute(user_opponents.insert().values(
            user_id=user_id, opponent_id=opponent_id, first_played_at=now,
        ))
    return len(fresh)


async def record_hand(
    session: AsyncSession,
    *,
    user_id: str,
    hole_cards: list[str],
    board: list[str],
    won: bool,
    pot_bb: float,
    counts_results: bool,
    opponent_ids: set[str],
    now: datetime,
) -> int:
    """Everything one finished hand can advance. Returns the AP it earned."""
    earned = await advance(session, user_id=user_id, code="grind", increment=1, now=now)

    new_faces = await note_opponents(session, user_id=user_id, opponent_ids=opponent_ids, now=now)
    if new_faces:
        earned += await advance(session, user_id=user_id, code="social", increment=new_faces, now=now)

    made = hand_class_code(hole_cards, board)
    if made:
        earned += await advance(session, user_id=user_id, code=made, high_water=1, now=now)

    if won and counts_results:
        earned += await advance(
            session, user_id=user_id, code="big_pot", high_water=int(pot_bb), now=now,
        )
        # §21: the point is winning a real pot with the worst hand there is,
        # not being dealt it.
        if pot_bb >= 50 and is_seven_deuce(hole_cards):
            earned += await advance(session, user_id=user_id, code="seven_deuce", high_water=1, now=now)
    return earned
