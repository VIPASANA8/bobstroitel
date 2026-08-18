from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import AuthenticatedUser, get_current_user
from online.schema import poker_tables, seat_queue, table_seats
from online.seating import AlreadySeated, SeatingError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tables", tags=["tables"])


class ReadyRequest(BaseModel):
    seat_no: int = Field(ge=0, le=5)
    buy_in_units: int = Field(gt=0)
    request_id: str = Field(min_length=1, max_length=128)


class AddOnRequest(BaseModel):
    amount_units: int = Field(gt=0)
    request_id: str = Field(min_length=1, max_length=128)


async def _table(request: Request, table_id: str):
    async with request.app.state.session_factory() as session:
        row = (await session.execute(select(poker_tables).where(poker_tables.c.id == table_id))).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="table not found")
    return row


def _error(exc: Exception) -> HTTPException:
    message = str(exc)
    if isinstance(exc, AlreadySeated):
        # The lobby needs somewhere to send the player, not just a refusal.
        return HTTPException(status_code=409, detail={
            "code": "already_seated",
            "message": message,
            "table_id": exc.table_id,
            "seat_state": exc.seat_state,
        })
    code = "between_hands_only" if "active hand" in message else "invalid_seating_request"
    return HTTPException(status_code=409, detail={"code": code, "message": message})


@router.get("/{table_id}")
async def table_snapshot(
    table_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    row = await _table(request, table_id)
    try:
        state = await request.app.state.runtime.public_snapshot(table_id, user.user_id)
    except Exception:
        # A table with no runtime yet is normal and renders as an empty table.
        # Anything else looks identical to the player, so it has to reach the log.
        logger.exception("table snapshot failed", extra={"table_id": table_id})
        state = {
            "phase": "waiting", "revision": 0, "occupancy": 0,
            "legal_actions": [], "players": {}, "action_deadline": None,
        }
    async with request.app.state.session_factory() as session:
        seat = (
            await session.execute(
                select(table_seats.c.state).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.user_id == user.user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                )
            )
        ).scalar_one_or_none()
        queue = (
            await session.execute(
                select(seat_queue.c.state).where(
                    seat_queue.c.table_id == table_id,
                    seat_queue.c.user_id == user.user_id,
                    seat_queue.c.state == "waiting",
                )
            )
        ).scalar_one_or_none()
    viewer_state = "seated" if seat in ("seated", "held", "leaving") else "waiting" if queue else "spectator"
    return {"table": dict(row), "state": state, "viewer_state": viewer_state, "queue_state": queue}


@router.post("/{table_id}/ready")
async def ready(table_id: str, payload: ReadyRequest, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        result = await request.app.state.seating.ready(
            user.user_id, table_id, payload.seat_no, payload.buy_in_units
        )
    except SeatingError as exc:
        raise _error(exc) from exc
    return {
        "request_id": result.id,
        "queue_state": result.state,
        "position_seq": result.position_seq,
        "seat_no": result.seat_no,
        "viewer_state": "waiting",
    }


@router.post("/{table_id}/ready/cancel")
async def cancel_ready(table_id: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    await request.app.state.seating.cancel_ready(user.user_id, table_id)
    return {"viewer_state": "spectator", "queue_state": "cancelled"}


@router.post("/{table_id}/ready-up")
async def ready_up(table_id: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    """Toggle ready-to-deal for the caller's own seat -- distinct from
    /ready above, which queues a brand new buy-in, not readiness."""
    seat_no = await request.app.state.seating.user_seat_number(user.user_id, table_id)
    if seat_no is None:
        raise HTTPException(status_code=409, detail={
            "code": "not_seated", "message": "take a seat before marking ready",
        })
    ready = await request.app.state.runtime.toggle_ready(table_id, seat_no)
    return {"seat_no": seat_no, "ready": ready}


@router.post("/{table_id}/leave")
async def leave(table_id: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    # Before marking the seat as leaving: if it's this player's turn right
    # now, fold it immediately rather than leaving their hand hanging until
    # the 30s clock times it out. fold_if_acting is a no-op whenever it isn't
    # actually their turn, so this is always safe to call.
    await request.app.state.runtime.fold_if_acting(table_id, user.user_id)
    await request.app.state.seating.request_leave(user.user_id, table_id)
    return {"viewer_state": "leaving"}


@router.post("/{table_id}/reconnect")
async def reconnect(table_id: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    await request.app.state.seating.reconnect(user.user_id, table_id)
    return {"viewer_state": "seated"}


@router.post("/{table_id}/add-on")
async def add_on(table_id: str, payload: AddOnRequest, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        await request.app.state.seating.add_on(user.user_id, table_id, payload.amount_units)
    except SeatingError as exc:
        raise _error(exc) from exc
    return {"ok": True, "amount_units": payload.amount_units}
