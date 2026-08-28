from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import AuthenticatedUser, get_current_user
from online.runtime import EMPTY_SNAPSHOT
from online.schema import poker_tables, seat_queue, table_seats
from online.seating import AlreadySeated, InsufficientFunds, SeatingError, WrongPassword


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tables", tags=["tables"])


class ReadyRequest(BaseModel):
    seat_no: int = Field(ge=0, le=5)
    buy_in_units: int = Field(gt=0)
    request_id: str = Field(min_length=1, max_length=128)
    password: str | None = Field(default=None, max_length=32)


class AddOnRequest(BaseModel):
    amount_units: int = Field(gt=0)
    request_id: str = Field(min_length=1, max_length=128)


async def _table(request: Request, table_id: str):
    async with request.app.state.session_factory() as session:
        row = (await session.execute(select(poker_tables).where(poker_tables.c.id == table_id))).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="table not found")
    # password_hash never leaves this process -- has_password is all a client
    # needs to know to show a lock icon and ask.
    row = dict(row)
    row["has_password"] = bool(row.pop("password_hash", None))
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
    if isinstance(exc, InsufficientFunds):
        # Both numbers, so the client can say how far short the player is
        # instead of a bare refusal.
        return HTTPException(status_code=409, detail={
            "code": "insufficient_funds",
            "message": message,
            "required_units": exc.required_units,
            "available_units": exc.available_units,
        })
    if isinstance(exc, WrongPassword):
        return HTTPException(status_code=403, detail={"code": "wrong_password", "message": message})
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
        # A table with no hand behind it is no longer an exception -- it comes
        # back as EMPTY_SNAPSHOT. Anything that lands here now is a real
        # failure, and it looks identical to the player, so it has to be logged.
        logger.exception("table snapshot failed", extra={"table_id": table_id})
        state = dict(EMPTY_SNAPSHOT)
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
        # Every state, not just "waiting": a request can die on its own -- the
        # table stays full past its TTL, or the balance no longer covers the
        # buy-in -- and reporting only "waiting" left the client unable to tell
        # "never asked" from "asked and lost it", so the seat request simply
        # vanished with no explanation.
        queue = (
            await session.execute(
                select(seat_queue.c.state).where(
                    seat_queue.c.table_id == table_id,
                    seat_queue.c.user_id == user.user_id,
                )
            )
        ).scalar_one_or_none()
    # viewer_player_id is set whenever the runtime still treats this user as a
    # player, including when their seat row disappeared mid-hand. Calling them a
    # spectator then would hide the whole action panel on a client that is being
    # asked to act, so the live hand wins over the missing seat row.
    viewer_state = (
        "seated" if seat in ("seated", "held", "leaving") or state.get("viewer_player_id")
        # Only a live request counts as waiting; the other states above are
        # reported for the client's benefit but mean the player is a spectator.
        else "waiting" if queue == "waiting"
        else "spectator"
    )
    # The seat the ready-up endpoint itself would find -- state == "seated",
    # nothing else. viewer_state above deliberately reads "seated" for a seat
    # that is only held or leaving, and during a live hand the snapshot omits
    # current_seats entirely, so the client has no way to work this out and
    # was offering "mark ready" to somebody the endpoint then refused. A
    # reconnect holds the seat for its grace window, and a restart holds every
    # seat at once, so that window opens on every deploy.
    seated_seat_no = await request.app.state.seating.user_seat_number(user.user_id, table_id)
    state["viewer_seat_no"] = seated_seat_no
    return {
        "table": dict(row), "state": state, "viewer_state": viewer_state,
        "queue_state": queue, "viewer_seat_no": seated_seat_no,
    }


@router.post("/{table_id}/ready")
async def ready(table_id: str, payload: ReadyRequest, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        result = await request.app.state.seating.ready(
            user.user_id, table_id, payload.seat_no, payload.buy_in_units, payload.password
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
    # Fold it now if it's their turn, rather than leaving the hand hanging on
    # the 30s clock. A no-op whenever it isn't actually their turn.
    await request.app.state.runtime.fold_if_acting(table_id, user.user_id)
    # And note them for the rest of the hand, so the engine folds them the
    # moment it reaches them on any later street instead of waiting again.
    in_hand = await request.app.state.runtime.mark_leaving(table_id, user.user_id)
    # Somebody not in the running hand has nothing to wait for at all.
    await request.app.state.seating.request_leave(user.user_id, table_id, immediate=not in_hand)
    return {"viewer_state": "leaving"}


@router.post("/{table_id}/reconnect")
async def reconnect(table_id: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    await request.app.state.seating.reconnect(user.user_id, table_id)
    return {"viewer_state": "seated"}


@router.post("/{table_id}/add-on")
async def add_on(table_id: str, payload: AddOnRequest, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    try:
        await request.app.state.seating.add_on(
            user.user_id, table_id, payload.amount_units, payload.request_id
        )
    except SeatingError as exc:
        raise _error(exc) from exc
    return {"ok": True, "amount_units": payload.amount_units}
