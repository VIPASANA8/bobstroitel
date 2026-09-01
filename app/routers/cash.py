from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.dependencies import AuthenticatedUser, get_cash_user
from cash.deposits import DepositUnavailable
from cash.ledger import IdempotencyConflict, InsufficientCash
from cash.withdrawals import WithdrawalStateError


router = APIRouter(prefix="/api/cash", tags=["cash"])


class DepositRequest(BaseModel):
    amount_usdt: str
    request_id: str = Field(min_length=1, max_length=200)


class WithdrawalRequest(BaseModel):
    amount_usdt: str
    address: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=200)


def _not_found(row):
    if row is None:
        raise HTTPException(status_code=404, detail="cash operation not found")
    return row


@router.get("/wallet")
async def wallet(request: Request, user: AuthenticatedUser = Depends(get_cash_user)):
    return await request.app.state.cash_wallet.get(user.user_id)


@router.post("/deposits", status_code=201)
async def create_deposit(body: DepositRequest, request: Request,
                         user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = await request.app.state.cash_deposits.create(
            user_id=user.user_id, tenant_id=user.tenant_id,
            amount_usdt=body.amount_usdt, request_key=body.request_id,
        )
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DepositUnavailable, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return request.app.state.cash_deposits.public(row)


@router.get("/deposits/{deposit_id}")
async def get_deposit(deposit_id: str, request: Request,
                      user: AuthenticatedUser = Depends(get_cash_user)):
    row = _not_found(await request.app.state.cash_deposits.get(deposit_id, user.user_id))
    return request.app.state.cash_deposits.public(row)


@router.post("/deposits/{deposit_id}/cancel")
async def cancel_deposit(deposit_id: str, request: Request,
                         user: AuthenticatedUser = Depends(get_cash_user)):
    row = _not_found(await request.app.state.cash_deposits.cancel(deposit_id, user.user_id))
    return request.app.state.cash_deposits.public(row)


@router.post("/deposits/{deposit_id}/paid")
async def mark_deposit_paid(deposit_id: str, request: Request,
                            user: AuthenticatedUser = Depends(get_cash_user)):
    # This acknowledgement never changes a balance. Only an observed transfer can.
    row = _not_found(await request.app.state.cash_deposits.get(deposit_id, user.user_id))
    return {**request.app.state.cash_deposits.public(row), "reconciliation_requested": True}


@router.post("/withdrawals", status_code=201)
async def create_withdrawal(body: WithdrawalRequest, request: Request,
                            user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = await request.app.state.cash_withdrawals.create(
            user_id=user.user_id, tenant_id=user.tenant_id, amount_usdt=body.amount_usdt,
            destination_address=body.address, request_key=body.request_id,
        )
    except (IdempotencyConflict, InsufficientCash) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return request.app.state.cash_withdrawals.public(row)


@router.get("/withdrawals/{withdrawal_id}")
async def get_withdrawal(withdrawal_id: str, request: Request,
                         user: AuthenticatedUser = Depends(get_cash_user)):
    row = _not_found(await request.app.state.cash_withdrawals.get(withdrawal_id, user.user_id))
    return request.app.state.cash_withdrawals.public(row)


@router.post("/withdrawals/{withdrawal_id}/cancel")
async def cancel_withdrawal(withdrawal_id: str, request: Request,
                            user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = _not_found(await request.app.state.cash_withdrawals.cancel(withdrawal_id, user.user_id))
    except WithdrawalStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return request.app.state.cash_withdrawals.public(row)
