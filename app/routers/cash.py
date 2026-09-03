from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.dependencies import AuthenticatedUser, get_cash_user
from cash.antifraud import DepositRefused
from cash.deposits import DepositUnavailable
from cash.holds import CashUserFrozen
from cash.fiat_orders import ActiveFiatOrderExists
from cash.ledger import IdempotencyConflict, InsufficientCash
from cash.trc20 import TransferEvent
from cash.withdrawals import WithdrawalStateError


router = APIRouter(prefix="/api/cash", tags=["cash"])


class DepositRequest(BaseModel):
    amount_usdt: str
    request_id: str = Field(min_length=1, max_length=200)


class WithdrawalRequest(BaseModel):
    amount_usdt: str
    # A TRC20 address, or the card/phone an operator will pay by hand.
    address: str = Field(min_length=1, max_length=128)
    rail: Literal["TRC20", "P2P_RUB"] = "TRC20"
    request_id: str = Field(min_length=1, max_length=200)


class FiatOrderRequest(BaseModel):
    amount_usdt: str
    request_id: str = Field(min_length=1, max_length=200)


def _guard(exc):
    """A hold and a limit are refusals with different answers for the caller."""
    if isinstance(exc, CashUserFrozen):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=429, detail=str(exc))


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
    except (CashUserFrozen, DepositRefused) as exc:
        raise _guard(exc) from exc
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


@router.post("/deposits/{deposit_id}/simulate-transfer")
async def simulate_deposit_transfer(
    deposit_id: str, request: Request,
    user: AuthenticatedUser = Depends(get_cash_user),
):
    """Inject the deterministic provider event for the development/test pilot."""
    row = _not_found(await request.app.state.cash_deposits.get(deposit_id, user.user_id))
    if row["status"] == "credited":
        return request.app.state.cash_deposits.public(row)
    if row["status"] != "awaiting_transfer":
        raise HTTPException(status_code=409, detail="deposit cannot receive a mock transfer")
    now = datetime.now(timezone.utc)
    if now > row["expires_at"]:
        raise HTTPException(status_code=409, detail="deposit has expired")
    await request.app.state.cash_deposits.observe(TransferEvent(
        provider="c2c-client-mock",
        external_event_id=f"deposit:{deposit_id}",
        tx_hash=f"mock-deposit-{deposit_id}", event_index=0,
        network=row["network"], token_contract=row["token_contract"],
        destination_address=row["destination_address"],
        amount_micros=row["expected_micros"], occurred_at=now,
    ))
    final = _not_found(await request.app.state.cash_deposits.get(deposit_id, user.user_id))
    return request.app.state.cash_deposits.public(final)


@router.post("/fiat-orders", status_code=201)
async def create_fiat_order(body: FiatOrderRequest, request: Request,
                            user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = await request.app.state.cash_fiat_orders.create(
            user_id=user.user_id, tenant_id=user.tenant_id,
            amount_usdt=body.amount_usdt, request_key=body.request_id,
        )
    except (CashUserFrozen, DepositRefused) as exc:
        raise _guard(exc) from exc
    except (ActiveFiatOrderExists, IdempotencyConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return request.app.state.cash_fiat_orders.public(row)


@router.get("/fiat-orders/active")
async def active_fiat_order(request: Request, user: AuthenticatedUser = Depends(get_cash_user)):
    row = await request.app.state.cash_fiat_orders.active(user.user_id)
    return None if row is None else request.app.state.cash_fiat_orders.public(row)


@router.get("/fiat-orders/{order_id}")
async def get_fiat_order(order_id: str, request: Request,
                         user: AuthenticatedUser = Depends(get_cash_user)):
    row = _not_found(await request.app.state.cash_fiat_orders.get(order_id, user.user_id))
    return request.app.state.cash_fiat_orders.public(row)


@router.post("/fiat-orders/{order_id}/paid")
async def mark_fiat_order_paid(order_id: str, request: Request,
                               user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = _not_found(await request.app.state.cash_fiat_orders.mark_paid(order_id, user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return request.app.state.cash_fiat_orders.public(row)


@router.post("/fiat-orders/{order_id}/cancel")
async def cancel_fiat_order(order_id: str, request: Request,
                            user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = _not_found(await request.app.state.cash_fiat_orders.cancel(order_id, user.user_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return request.app.state.cash_fiat_orders.public(row)


@router.post("/fiat-orders/{order_id}/simulate-trader-confirmation")
async def simulate_fiat_confirmation(order_id: str, request: Request,
                                     user: AuthenticatedUser = Depends(get_cash_user)):
    row = _not_found(await request.app.state.cash_fiat_orders.get(order_id, user.user_id))
    if row["status"] not in {"waiting_trader", "credited"}:
        raise HTTPException(status_code=409, detail="fiat order is not waiting for trader confirmation")
    await request.app.state.cash_fiat_orders.poll_once()
    final = _not_found(await request.app.state.cash_fiat_orders.get(order_id, user.user_id))
    return request.app.state.cash_fiat_orders.public(final)


@router.post("/withdrawals", status_code=201)
async def create_withdrawal(body: WithdrawalRequest, request: Request,
                            user: AuthenticatedUser = Depends(get_cash_user)):
    try:
        row = await request.app.state.cash_withdrawals.create(
            user_id=user.user_id, tenant_id=user.tenant_id, amount_usdt=body.amount_usdt,
            destination_address=body.address, request_key=body.request_id, rail=body.rail,
        )
    except CashUserFrozen as exc:
        raise _guard(exc) from exc
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
