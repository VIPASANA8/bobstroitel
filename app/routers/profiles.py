from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.dependencies import AuthenticatedUser, get_current_user
from online import missions as missions_module
from online.achievements import ACHIEVEMENTS
from online.catalogue import PLAY
from online.progression import (
    MIN_SESSION_HANDS,
    level_for_xp,
    msk_day,
    rank_for_level,
    xp_to_next_level,
)
from online.schema import (
    play_sessions,
    poker_tables,
    progress_days,
    table_seats,
    user_achievements,
    user_progression,
    users,
)
from online.history import HistoryService


router = APIRouter(prefix="/api/profile", tags=["profile"])


class TopUpRequest(BaseModel):
    amount_units: int = Field(ge=1, le=100_000_000)
    request_id: str = Field(min_length=1, max_length=200)


async def _profile(request: Request, user: AuthenticatedUser) -> dict[str, object]:
    async with request.app.state.session_factory() as session:
        row = (
            await session.execute(select(users).where(users.c.id == user.user_id))
        ).mappings().one()
        stack_units = (
            await session.execute(
                select(table_seats.c.stack_units)
                .join(poker_tables, poker_tables.c.id == table_seats.c.table_id)
                .where(
                    table_seats.c.user_id == user.user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                    poker_tables.c.asset == PLAY,
                )
            )
        ).scalars().all()
        active_table_id = (
            await session.execute(
                select(table_seats.c.table_id)
                .join(poker_tables, poker_tables.c.id == table_seats.c.table_id)
                .where(
                    table_seats.c.user_id == user.user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                    poker_tables.c.asset == PLAY,
                ).limit(1)
            )
        ).scalar_one_or_none()
        # A player who has not finished a hand since the migration has no row
        # yet: the settlement writes the first one.
        xp = (
            await session.execute(
                select(user_progression.c.xp).where(user_progression.c.user_id == user.user_id)
            )
        ).scalar_one_or_none() or 0
    level = level_for_xp(xp)
    return {
        "user_id": row["id"],
        "telegram_user_id": row["telegram_user_id"],
        "display_name": row["display_name"],
        "wins": row["wins"],
        "hands_played": row["hands_played"],
        "xp": xp,
        "level": level,
        "rank": rank_for_level(level),
        "xp_to_next_level": xp_to_next_level(xp),
        "available_units": await request.app.state.ledger.available_units(user.user_id),
        "active_table_stack_units": sum(stack_units),
        "active_table_id": active_table_id,
    }


@router.get("")
async def profile(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    return await _profile(request, user)


@router.get("/play-journal")
async def play_journal(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return {"entries": await request.app.state.ledger.journal("user", user.user_id, limit=limit)}


@router.get("/hands")
async def hand_history(
    request: Request,
    limit: int = Query(20, ge=1, le=20),
    user: AuthenticatedUser = Depends(get_current_user),
):
    return {"hands": await request.app.state.history.last_hands(user.user_id, limit=limit)}


@router.post("/play-top-up")
async def play_top_up(
    payload: TopUpRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    # Whoever calls this gets what they ask for, and the caller picks the
    # request id, so the idempotency guard does not cap anything: three calls
    # took a brand-new guest from 100 000 to 300 100 000 on the live site.
    # It stays available in development, where the balance is a fixture; on a
    # deployment a top-up has to arrive through a payment, not through here.
    if not request.app.state.settings.self_top_up_enabled:
        raise HTTPException(status_code=404, detail="not found")
    try:
        result = await request.app.state.ledger.grant(
            user.user_id,
            payload.amount_units,
            f"topup:{user.user_id}:{payload.request_id}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "transaction_id": result.transaction_id,
        "available_units": result.available_units,
    }


@router.get("/last-session")
async def last_session(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """The report for the last session this player has not been shown yet.

    Unseen rather than newest, so a player who closed the tab on the way out --
    or who was evicted for being away -- still gets it on their next visit.
    """
    async with request.app.state.session_factory() as session:
        row = (
            await session.execute(
                select(play_sessions)
                .where(play_sessions.c.user_id == user.user_id, play_sessions.c.seen_at.is_(None))
                .order_by(play_sessions.c.ended_at.desc())
                .limit(1)
            )
        ).mappings().first()
    if row is None:
        return {"session": None}
    big_blind = row["big_blind_units"] or 1
    return {"session": {
        "id": row["id"],
        "table_id": row["table_id"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "hands": row["hands"],
        "net_bb": round(row["net_units"] / big_blind, 1),
        "biggest_pot_bb": round(row["biggest_pot_units"] / big_blind, 1),
        "xp_earned": row["xp_earned"],
        "daily_xp": row["daily_xp"],
    }}


@router.post("/last-session/seen")
async def mark_last_session_seen(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Dismiss every report this player is still owed.

    No id in the request: the page only ever shows the one report, and marking
    by id would leave anything older than it unseen forever.
    """
    async with request.app.state.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(play_sessions)
                .where(play_sessions.c.user_id == user.user_id, play_sessions.c.seen_at.is_(None))
                .values(seen_at=datetime.now(timezone.utc))
            )
    return {"ok": True}


def _confidence(hands: int) -> str:
    """§28: no statistic is worth reading without the size of its sample."""
    if hands >= 1000:
        return "high"
    return "medium" if hands >= 200 else "low"


@router.get("/stats")
async def stats(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Basic statistics, read from the day rollup rather than from the hands.

    Recomputing these across every hand a player has ever played, on every
    visit to the profile, is the version that stops working at ten thousand
    hands. One row per player per day answers all of it.
    """
    async with request.app.state.session_factory() as session:
        days = (
            await session.execute(
                select(progress_days)
                .where(progress_days.c.owner_kind == "user", progress_days.c.owner_id == user.user_id)
                .order_by(progress_days.c.day)
            )
        ).mappings().all()
        # Records come from network tables only (§3): a room the player opened
        # is somewhere two accounts can hand each other any number they like.
        #
        # ponytail: the sittings are counted in Python rather than by SQL. It
        # is one row per sitting, so a heavy year is a few hundred; if that
        # ever stops being true, this is a GROUP BY.
        sittings = (
            await session.execute(
                select(
                    play_sessions.c.started_at,
                    play_sessions.c.ended_at,
                    play_sessions.c.biggest_pot_units,
                    play_sessions.c.big_blind_units,
                )
                .select_from(play_sessions.join(
                    poker_tables, poker_tables.c.id == play_sessions.c.table_id
                ))
                .where(
                    play_sessions.c.user_id == user.user_id,
                    poker_tables.c.created_by.is_(None),
                    # §4: a handful of hands is a receipt, not a session, and
                    # nothing that short sets a personal record.
                    play_sessions.c.hands >= MIN_SESSION_HANDS,
                )
            )
        ).all()

    hands = sum(day["hands"] for day in days)
    result_hands = sum(day["result_hands"] for day in days)
    net_bb_x100 = sum(day["net_bb_x100"] for day in days)
    longest = max(
        ((ended - started).total_seconds() / 60 for started, ended, _, _ in sittings),
        default=0,
    )
    biggest_pot_bb = max(
        (pot / blind for _, _, pot, blind in sittings if blind),
        default=0,
    )
    # A day spent entirely in a room the player opened has a result of zero
    # because none of it counted (§3) -- and a zero was beating a real losing
    # day to "best day". Only days that actually put a result on the board are
    # eligible for either record.
    scored = [day for day in days if day["result_hands"]]
    best = max(scored, key=lambda day: day["net_bb_x100"], default=None)
    # One day of play has a best and no worst. Printing the same day twice,
    # once in green and once under "худший день", reads as a broken page.
    worst = min(scored, key=lambda day: day["net_bb_x100"]) if len(scored) > 1 else None
    return {
        "hands": hands,
        # The two are not the same number, and the gap is the point: hands in a
        # room the player opened count as played and not as a result.
        "result_hands": result_hands,
        "hands_won": sum(day["hands_won"] for day in days),
        "days_played": len(days),
        "sessions": len(sittings),
        "net_bb": round(net_bb_x100 / 100, 1),
        # The long-run number, and the reason results are kept in big blinds.
        # Its denominator is the hands that were allowed to move it.
        "bb_per_100": round(net_bb_x100 / result_hands, 1) if result_hands else None,
        "biggest_pot_bb": round(biggest_pot_bb, 1),
        "longest_session_minutes": int(longest),
        "best_day": {"day": best["day"], "net_bb": round(best["net_bb_x100"] / 100, 1)} if best else None,
        "worst_day": {"day": worst["day"], "net_bb": round(worst["net_bb_x100"] / 100, 1)} if worst else None,
        "confidence": _confidence(result_hands),
    }


@router.get("/achievements")
async def achievements(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Every achievement, earned or not, with a secret one kept secret.

    The whole list is returned rather than only what has been earned: a
    collection the player cannot see the shape of is not a collection. A
    secret gives away nothing until it lands.
    """
    async with request.app.state.session_factory() as session:
        rows = {
            row["code"]: row
            for row in (
                await session.execute(
                    select(user_achievements).where(user_achievements.c.user_id == user.user_id)
                )
            ).mappings().all()
        }
        points = (
            await session.execute(
                select(user_progression.c.achievement_points)
                .where(user_progression.c.user_id == user.user_id)
            )
        ).scalar_one_or_none() or 0

    earned = []
    for definition in ACHIEVEMENTS.values():
        row = rows.get(definition.code)
        tier = row["tier"] if row else 0
        hidden = definition.secret and not tier
        earned.append({
            "code": definition.code,
            "title": "???" if hidden else definition.title,
            "rarity": definition.rarity,
            "secret": definition.secret,
            "tier": tier,
            "tiers": len(definition.tiers),
            "progress": row["progress"] if row else 0,
            # What this tier is climbing towards, or None once it is finished.
            "next_threshold": definition.tiers[tier] if tier < len(definition.tiers) else None,
            "completed_at": row["completed_at"] if row else None,
        })
    return {
        "achievement_points": points,
        "completed": sum(1 for item in earned if item["tier"] == item["tiers"]),
        "total": len(earned),
        "achievements": earned,
    }


@router.get("/missions")
async def missions(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Today's three, with the time left on them.

    Progress is read, never advanced: missions move when a hand is settled or
    a session closes, both of which are events the server owns. A page opening
    is not one.
    """
    now = datetime.now(timezone.utc)
    day = msk_day(now)
    async with request.app.state.session_factory() as session:
        state = await missions_module.state_for(session, user.user_id, day)
        reroll_used = await missions_module.rerolled_today(session, user.user_id, day)
    return {
        "day": day,
        "resets_in_seconds": int((missions_module.next_reset(now) - now).total_seconds()),
        "reroll_available": not reroll_used,
        "completed": sum(1 for slot in state.values() if slot["completed_at"]),
        "completion_xp": missions_module.COMPLETION_XP,
        "missions": [
            {
                "slot": slot,
                "code": item["mission"].code,
                "title": item["mission"].title,
                "target": item["mission"].target,
                "xp": item["mission"].xp,
                "progress": item["progress"],
                "done": item["completed_at"] is not None,
                "rerolled": item["rerolled"],
            }
            for slot, item in state.items()
        ],
    }


@router.post("/missions/{slot}/reroll")
async def reroll_mission(
    slot: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)
):
    """Swap one unfinished mission. One a day, and not for a finished one."""
    now = datetime.now(timezone.utc)
    try:
        async with request.app.state.session_factory() as session:
            async with session.begin():
                swapped = await missions_module.reroll(
                    session, user.user_id, msk_day(now), slot, now
                )
    except IntegrityError:
        # uq_user_missions_daily_reroll refused it, which means another request
        # took the day's one swap between this one's read and its write. That
        # is the same answer as asking for a second reroll, and it should read
        # like one rather than like the server falling over.
        swapped = False
    if not swapped:
        raise HTTPException(status_code=409, detail="reroll unavailable")
    return {"ok": True}
