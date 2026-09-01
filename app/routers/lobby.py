from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.dependencies import AuthenticatedUser, get_current_user
from cash.access import CashAccessDenied, ensure_cash_access
from online.catalogue import CASH_USDT, PLAY, ROOM_BLIND_LEVELS, ROOM_NAME_MAX, ROOM_PASSWORD_MAX, RoomError, RoomLimitReached
from online.schema import cash_accounts, poker_tables, seat_queue, table_runtimes, table_seats


class CreateRoomRequest(BaseModel):
    name: str = Field(min_length=1, max_length=ROOM_NAME_MAX)
    level: str = Field(min_length=1, max_length=16)
    # Empty/omitted means open to anyone -- catalogue.create_room is the one
    # place that actually enforces the length bounds; this just keeps an
    # absurdly long value from reaching it.
    password: str | None = Field(default=None, max_length=ROOM_PASSWORD_MAX)


router = APIRouter(prefix="/api/lobby", tags=["lobby"])


def _cash_gate(request: Request, user: AuthenticatedUser, asset: str) -> None:
    if asset != CASH_USDT:
        return
    try:
        ensure_cash_access(request.app.state.settings.cash_mode, user.auth_method)
    except CashAccessDenied as exc:
        status = 404 if request.app.state.settings.cash_mode == "off" else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/tables")
async def list_lobby_tables(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(6, ge=1, le=100),
    asset: Literal["PLAY", "CASH_USDT"] = PLAY,
    user: AuthenticatedUser = Depends(get_current_user),
):
    _cash_gate(request, user, asset)
    rows = await request.app.state.catalogue.list_tables(
        page=page, per_page=per_page, viewer_id=user.user_id, asset=asset,
    )
    return {"tables": [row.public_dict() for row in rows], "page": page, "per_page": per_page}


@router.get("/session")
async def current_lobby_session(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    asset: Literal["PLAY", "CASH_USDT"] = PLAY,
):
    """Return the caller's one active seat or queue entry for lobby CTAs."""
    _cash_gate(request, user, asset)
    async with request.app.state.session_factory() as session:
        seat = (
            await session.execute(
                select(
                    table_seats.c.table_id,
                    table_seats.c.state.label("seat_state"),
                    table_seats.c.seat_no,
                    poker_tables.c.name.label("table_name"),
                    table_runtimes.c.phase.label("phase"),
                )
                .select_from(
                    table_seats
                    .join(poker_tables, poker_tables.c.id == table_seats.c.table_id)
                    .outerjoin(table_runtimes, table_runtimes.c.table_id == table_seats.c.table_id)
                )
                .where(
                    table_seats.c.user_id == user.user_id,
                    table_seats.c.state.in_(("seated", "held", "leaving")),
                    poker_tables.c.asset == asset,
                )
                .order_by(table_seats.c.updated_at.desc())
            )
        ).mappings().first()
        if seat:
            return {"session": {"kind": "seat", **dict(seat)}}

        queued = (
            await session.execute(
                select(
                    seat_queue.c.table_id,
                    seat_queue.c.seat_no,
                    seat_queue.c.position_seq,
                    poker_tables.c.name.label("table_name"),
                    table_runtimes.c.phase.label("phase"),
                )
                .select_from(
                    seat_queue
                    .join(poker_tables, poker_tables.c.id == seat_queue.c.table_id)
                    .outerjoin(table_runtimes, table_runtimes.c.table_id == seat_queue.c.table_id)
                )
                .where(
                    seat_queue.c.user_id == user.user_id,
                    seat_queue.c.state == "waiting",
                    poker_tables.c.asset == asset,
                )
                .order_by(seat_queue.c.created_at.desc())
            )
        ).mappings().first()
        if queued:
            return {"session": {"kind": "waiting", "seat_state": "waiting", **dict(queued)}}

    return {"session": None}


@router.post("/quick-play")
async def quick_play(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    asset: Literal["PLAY", "CASH_USDT"] = PLAY,
):
    _cash_gate(request, user, asset)
    if asset == CASH_USDT:
        async with request.app.state.session_factory() as session:
            available_units = await session.scalar(select(func.coalesce(func.sum(
                cash_accounts.c.balance_micros
            ), 0)).where(
                cash_accounts.c.user_id == user.user_id,
                cash_accounts.c.kind == "available",
            ))
    else:
        available_units = await request.app.state.ledger.available_units(user.user_id)
    try:
        chosen = await request.app.state.catalogue.quick_play(
            user.user_id, int(available_units or 0), asset=asset,
        )
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"table": chosen.public_dict(), "join_mode": chosen.join_mode}


@router.get("/room-levels")
async def room_levels(request: Request, _: AuthenticatedUser = Depends(get_current_user)):
    """Blind levels a room may be opened at. Bots are not a setting."""
    return {
        "enabled": request.app.state.settings.legacy_play_rooms_enabled,
        "levels": [
            {"key": key, "small_blind_units": small, "big_blind_units": big}
            for key, (small, big) in ROOM_BLIND_LEVELS.items()
        ],
        "name_max": ROOM_NAME_MAX,
    }


@router.post("/rooms")
async def create_room(
    payload: CreateRoomRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    if not request.app.state.settings.legacy_play_rooms_enabled:
        raise HTTPException(status_code=409, detail={
            "code": "cash_runtime_pending",
            "message": "new PLAY rooms are disabled until CASH runtime is ready",
        })
    try:
        room = await request.app.state.catalogue.create_room(
            user.user_id, payload.name, payload.level, payload.password
        )
    except RoomLimitReached as exc:
        # Name the room they already have, so the client can offer to open it
        # instead of leaving them to work out why nothing happened.
        raise HTTPException(status_code=409, detail={
            "code": "room_limit_reached", "message": str(exc), "table_id": exc.table_id,
        }) from exc
    except RoomError as exc:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_room", "message": str(exc),
        }) from exc
    return {"room": room.public_dict()}


@router.get("/rooms/mine")
async def my_room(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    room = await request.app.state.catalogue.own_room(user.user_id)
    return {"room": room.public_dict() if room else None}


@router.post("/rooms/{table_id}/close")
async def close_room(table_id: str, request: Request, user: AuthenticatedUser = Depends(get_current_user)):
    # Prove ownership before touching a single seat. Eviction is not part of the
    # close transaction and cannot be rolled back, so doing it first would let
    # anyone clear any table just by naming it and swallowing the error that
    # follows. One open room per player is the invariant, so a match here is the
    # whole proof.
    own = await request.app.state.catalogue.own_room(user.user_id)
    if own is None or own.id != table_id:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_room", "message": "not your room",
        })
    # Empty it only now: a closed table stops being advanced, so anyone still
    # seated would keep their chips locked in its escrow.
    try:
        await request.app.state.seating.evict_table(table_id)
        await request.app.state.catalogue.close_room(table_id, user.user_id)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_room", "message": str(exc),
        }) from exc
    return {"closed": True, "table_id": table_id}
