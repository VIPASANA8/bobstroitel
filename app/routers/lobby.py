from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.dependencies import AuthenticatedUser, get_current_user


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
