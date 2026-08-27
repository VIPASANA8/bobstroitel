from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import AuthenticatedUser, get_current_user
from online.schema import table_seats, users
from online.history import HistoryService


router = APIRouter(prefix="/api/profile", tags=["profile"])
LEVEL_THRESHOLDS = (0, 10, 50, 100, 200, 500)


class TopUpRequest(BaseModel):
    amount_units: int = Field(ge=1, le=100_000_000)
    request_id: str = Field(min_length=1, max_length=200)


def level_for_wins(wins: int) -> int:
    return max(level for level, threshold in enumerate(LEVEL_THRESHOLDS) if wins >= threshold)


async def _profile(request: Request, user: AuthenticatedUser) -> dict[str, object]:
    async with request.app.state.session_factory() as session:
        row = (
            await session.execute(select(users).where(users.c.id == user.user_id))
        ).mappings().one()
        stack_units = (
            await session.execute(
                select(table_seats.c.stack_units).where(
                    table_seats.c.user_id == user.user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                )
            )
        ).scalars().all()
        active_table_id = (
            await session.execute(
                select(table_seats.c.table_id).where(
                    table_seats.c.user_id == user.user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                ).limit(1)
            )
        ).scalar_one_or_none()
    return {
        "user_id": row["id"],
        "telegram_user_id": row["telegram_user_id"],
        "display_name": row["display_name"],
        "wins": row["wins"],
        "hands_played": row["hands_played"],
        "level": level_for_wins(row["wins"]),
        "available_units": await request.app.state.ledger.available_units(user.user_id),
        "active_table_stack_units": sum(stack_units),
        "avatar_asset_key": f"level-{level_for_wins(row['wins'])}",
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
