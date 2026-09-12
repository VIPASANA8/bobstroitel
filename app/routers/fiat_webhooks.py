"""What pservice pushes to "CASE8's backend" -- which, on this host, is us.

pservice's InternalBackendClient signs every webhook with
`sha256=HMAC(secret, "<unix ts>.<compact sorted json body>")` and expects a
2xx; anything else it retries for half a minute inside the very request the
player is waiting on (see `FiatOrderService._tell_partner`). So this answers
fast and does the minimum: a webhook is a *nudge*, never the truth. On each
one the order is read back from pservice and applied through the same
`_sync` the poller uses, so money moves on exactly one path, with the same
idempotent ledger key, whichever of the two heard about it first.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/payments", tags=["fiat-webhooks"])

#: A signed timestamp older than this is replayed or from a clock nobody set.
MAX_SKEW_SECONDS = 300


def verify_signature(secret: str, body: bytes, signature: str | None, timestamp: str | None,
                     *, now: float | None = None) -> None:
    if not secret:
        raise HTTPException(status_code=404, detail="not found")
    if not signature or not timestamp or not timestamp.isdigit():
        raise HTTPException(status_code=401, detail="unsigned webhook")
    if abs((now if now is not None else time.time()) - int(timestamp)) > MAX_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="stale webhook")
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.removeprefix("sha256="), expected):
        raise HTTPException(status_code=401, detail="bad webhook signature")


async def _signed_body(request: Request, signature: str | None, timestamp: str | None) -> dict:
    body = await request.body()
    verify_signature(request.app.state.settings.cash_fiat_webhook_secret, body, signature, timestamp)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="webhook body is not JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="webhook body is not an object")
    return payload


def _order_id_from_intent(value) -> str | None:
    """The intent id pservice carries is our order id as a UUID (see create_payment)."""
    try:
        return uuid.UUID(str(value)).hex
    except (ValueError, AttributeError, TypeError):
        return None


async def _refresh(request: Request, order_id: str | None) -> JSONResponse:
    if not order_id or not await request.app.state.cash_fiat_orders.refresh(order_id):
        # 404 is one pservice does not retry: an order that is not ours will
        # not become ours by asking again.
        raise HTTPException(status_code=404, detail="unknown order")
    return JSONResponse({"ok": True})


@router.post("/webhook/approval")
async def approval(request: Request,
                   signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
                   timestamp: str | None = Header(default=None, alias="X-Webhook-Timestamp")):
    """The trader confirmed: `externalTransactionId` is our order id."""
    payload = await _signed_body(request, signature, timestamp)
    order_id = str(payload.get("externalTransactionId") or "") or _order_id_from_intent(payload.get("paymentIntentId"))
    return await _refresh(request, order_id)


@router.post("/webhook/failure")
async def failure(request: Request,
                  signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
                  timestamp: str | None = Header(default=None, alias="X-Webhook-Timestamp")):
    """Cancelled or expired on the partner's side: keyed by the intent id."""
    payload = await _signed_body(request, signature, timestamp)
    return await _refresh(request, _order_id_from_intent(payload.get("paymentIntentId")))


@router.post("/webhook/settlement")
async def settlement(request: Request,
                     signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
                     timestamp: str | None = Header(default=None, alias="X-Webhook-Timestamp")):
    """CASE8 closes a float entry here. We credited on approval; nothing to do."""
    await _signed_body(request, signature, timestamp)
    return JSONResponse({"ok": True})
