from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.dependencies import get_cash_operator
from cash.access import CashOperator
from cash.admin import OperatorAccessDenied
from cash.ledger import IdempotencyConflict, InsufficientCash
from cash.withdrawals import WithdrawalStateError


router = APIRouter(prefix="/api/cash-admin", tags=["cash-admin"])


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ExecuteRequest(ReasonRequest):
    outcome: Literal["success", "failure", "unknown"]


class WithdrawalResolution(ReasonRequest):
    decision: Literal["confirmed", "rejected"]
    tx_hash: str | None = Field(default=None, max_length=128)


class PaymentResolution(ReasonRequest):
    decision: Literal["credit", "reject"]


class FiatEventResolution(ReasonRequest):
    decision: Literal["credit", "reject"]
    # Only needed when the partner event names an order Poker8 never stored.
    order_id: str | None = Field(default=None, min_length=1, max_length=64)


def _error(exc):
    if isinstance(exc, OperatorAccessDenied):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (IdempotencyConflict, InsufficientCash, WithdrawalStateError)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/me")
async def operator_me(operator: CashOperator = Depends(get_cash_operator)):
    return {"telegram_user_id": operator.telegram_user_id, "tenant_id": operator.tenant_id,
            "role": operator.role}


@router.get("/queue")
async def queue(request: Request, operator: CashOperator = Depends(get_cash_operator)):
    return await request.app.state.cash_admin.queue(operator)


@router.get("/audit")
async def audit(request: Request, limit: int = 100,
                operator: CashOperator = Depends(get_cash_operator)):
    return await request.app.state.cash_admin.audit(operator, limit)


@router.get("/users/{identifier}")
async def user(identifier: str, request: Request,
               operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.user(operator, identifier)
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(withdrawal_id: str, body: ReasonRequest, request: Request,
                             key: str = Header(alias="Idempotency-Key"),
                             operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.approve_withdrawal(
            withdrawal_id, operator, reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(withdrawal_id: str, body: ReasonRequest, request: Request,
                            key: str = Header(alias="Idempotency-Key"),
                            operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.reject_withdrawal(
            withdrawal_id, operator, reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/withdrawals/{withdrawal_id}/execute-mock")
async def execute_withdrawal(withdrawal_id: str, body: ExecuteRequest, request: Request,
                             key: str = Header(alias="Idempotency-Key"),
                             operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.execute_mock(
            withdrawal_id, operator, outcome=body.outcome, reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/withdrawals/{withdrawal_id}/resolve")
async def resolve_withdrawal(withdrawal_id: str, body: WithdrawalResolution, request: Request,
                             key: str = Header(alias="Idempotency-Key"),
                             operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.resolve_withdrawal(
            withdrawal_id, operator, decision=body.decision, tx_hash=body.tx_hash,
            reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/payment-events/{event_id}/resolve")
async def resolve_payment(event_id: str, body: PaymentResolution, request: Request,
                          key: str = Header(alias="Idempotency-Key"),
                          operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.resolve_payment(
            event_id, operator, decision=body.decision, reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.get("/fiat-orders/{identifier}")
async def fiat_order(identifier: str, request: Request,
                     operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.fiat_order(operator, identifier)
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/fiat-events/{event_id}/resolve")
async def resolve_fiat_event(event_id: int, body: FiatEventResolution, request: Request,
                             key: str = Header(alias="Idempotency-Key"),
                             operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.resolve_fiat_event(
            event_id, operator, decision=body.decision, order_id=body.order_id,
            reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.post("/fiat-orders/{order_id}/close")
async def close_fiat_order(order_id: str, body: ReasonRequest, request: Request,
                           key: str = Header(alias="Idempotency-Key"),
                           operator: CashOperator = Depends(get_cash_operator)):
    try:
        return await request.app.state.cash_admin.close_fiat_order(
            order_id, operator, reason=body.reason, key=key,
        )
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc


@router.get("/reconciliation")
async def fiat_reconciliation(request: Request, day: str | None = None,
                              operator: CashOperator = Depends(get_cash_operator)):
    try:
        chosen = date.fromisoformat(day) if day else datetime.now(timezone.utc).date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD") from exc
    try:
        return await request.app.state.cash_admin.fiat_reconciliation(operator, chosen)
    except (ValueError, LookupError) as exc:
        raise _error(exc) from exc
