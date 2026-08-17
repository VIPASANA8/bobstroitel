from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

from app.dependencies import AuthenticatedUser, get_current_user
from online.schema import poker_tables, seat_queue, table_runtimes, table_seats


router = APIRouter(prefix="/api/lobby", tags=["lobby"])


@router.get("/tables")
async def list_lobby_tables(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(6, ge=1, le=100),
    _: AuthenticatedUser = Depends(get_current_user),
):
    rows = await request.app.state.catalogue.list_tables(page=page, per_page=per_page)
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
