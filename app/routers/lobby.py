from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import AuthenticatedUser, get_current_user
from online.catalogue import ROOM_BLIND_LEVELS, ROOM_NAME_MAX, RoomError, RoomLimitReached
from online.schema import poker_tables, seat_queue, table_runtimes, table_seats


class CreateRoomRequest(BaseModel):
    name: str = Field(min_length=1, max_length=ROOM_NAME_MAX)
    level: str = Field(min_length=1, max_length=16)
    visibility: str = Field(default="public", pattern="^(public|link)$")


router = APIRouter(prefix="/api/lobby", tags=["lobby"])


@router.get("/tables")
async def list_lobby_tables(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(6, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
):
    rows = await request.app.state.catalogue.list_tables(
        page=page, per_page=per_page, viewer_id=user.user_id
    )
    return {"tables": [row.public_dict() for row in rows], "page": page, "per_page": per_page}


@router.get("/session")
async def current_lobby_session(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return the caller's one active seat or queue entry for lobby CTAs."""
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
                .where(seat_queue.c.user_id == user.user_id, seat_queue.c.state == "waiting")
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
):
    available_units = await request.app.state.ledger.available_units(user.user_id)
    try:
        chosen = await request.app.state.catalogue.quick_play(user.user_id, available_units)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"table": chosen.public_dict(), "join_mode": chosen.join_mode}


@router.get("/room-levels")
async def room_levels(_: AuthenticatedUser = Depends(get_current_user)):
    """Blind levels a room may be opened at. Bots are not a setting."""
    return {
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
    try:
        room = await request.app.state.catalogue.create_room(
            user.user_id, payload.name, payload.level, payload.visibility
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
    # Empty it first: a closed table stops being advanced, so anyone still
    # seated would keep their chips locked in its escrow.
    try:
        await request.app.state.seating.evict_table(table_id)
        await request.app.state.catalogue.close_room(table_id, user.user_id)
    except RoomError as exc:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_room", "message": str(exc),
        }) from exc
    return {"closed": True, "table_id": table_id}
