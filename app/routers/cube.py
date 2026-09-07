from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.dependencies import AuthenticatedUser, get_cash_user
from cash.amounts import micros_to_usdt, usdt_to_micros
from cash.antifraud import LossLimitReached
from cash.cube import CubeError, MAX_SELECTED
from cash.holds import CashUserFrozen
from cash.ledger import IdempotencyConflict, InsufficientCash


router = APIRouter(prefix="/api/cube", tags=["cube"])


class RollRequest(BaseModel):
    # A decimal string, like every other amount the cash API takes: a float
    # would arrive at 0.30000000000000004 for three ten-cent chips.
    stake_usdt: str = Field(min_length=1, max_length=32)
    selected: list[int] = Field(min_length=1, max_length=MAX_SELECTED)
    request_id: str = Field(min_length=1, max_length=100)


@router.get("/history")
async def history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_cash_user),
):
    return {"rounds": await request.app.state.cube.recent(user.user_id, limit=limit)}


@router.post("/roll")
async def roll(
    payload: RollRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_cash_user),
):
    """Draw one CUBE round and settle it against the player's USDT wallet.

    The browser never decides anything: it posts a stake and a selection and is
    told the face. The whole round -- the hold check, the daily loss limit, the
    draw and the posting -- happens in one transaction with the wallet row
    locked, inside `CashCubeService`.
    """
    try:
        stake_micros = usdt_to_micros(payload.stake_usdt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Введите сумму в USDT.") from exc

    try:
        round_result = await request.app.state.cube.settle(
            user.user_id, payload.request_id, stake_micros, payload.selected,
        )
    except CashUserFrozen as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LossLimitReached as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except InsufficientCash:
        raise HTTPException(status_code=400, detail="Недостаточно средств на балансе.") from None
    except CubeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (IdempotencyConflict, IntegrityError):
        # The same request id with different content, or a racing twin that won
        # the insert. Either way this call settled nothing.
        raise HTTPException(status_code=409, detail="Этот бросок уже рассчитан.") from None

    return {
        "round_id": round_result["round_id"],
        "selected": round_result["selected"],
        "roll": round_result["roll"],
        "won": round_result["won"],
        "stake_usdt": micros_to_usdt(round_result["stake_micros"]),
        "payout_usdt": micros_to_usdt(round_result["payout_micros"]),
        "available_usdt": micros_to_usdt(round_result["available_micros"]),
    }
