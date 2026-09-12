"""pservice's webhooks land here instead of at CASE8's backend.

What has to hold: nothing unsigned or stale is believed; a signed webhook is
a nudge that reads the order back from pservice and applies it through the
poller's own path, so a completion heard twice still credits once; and an
order that is not ours is refused in a way pservice does not retry.
"""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import fiat_webhooks
from app.routers.fiat_webhooks import verify_signature
from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import COMPLETED_STATUS, MockPservice
from fastapi import HTTPException
from online.schema import tenants, users
from sqlalchemy import insert

SECRET = "shared-with-pservice"


def signed(body: dict, *, secret=SECRET, at=None):
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True)
    ts = str(int(at if at is not None else time.time()))
    sig = hmac.new(secret.encode(), f"{ts}.{raw}".encode(), hashlib.sha256).hexdigest()
    return raw, {"X-Webhook-Signature": f"sha256={sig}", "X-Webhook-Timestamp": ts,
                 "Content-Type": "application/json"}


def test_the_signature_is_checked_the_way_pservice_makes_it():
    raw, headers = signed({"paymentIntentId": "x"})
    verify_signature(SECRET, raw.encode(), headers["X-Webhook-Signature"], headers["X-Webhook-Timestamp"])
    for bad in ({"signature": "sha256=" + "0" * 64}, {"timestamp": "abc"}, {"timestamp": None}):
        with pytest.raises(HTTPException) as caught:
            verify_signature(SECRET, raw.encode(),
                             bad.get("signature", headers["X-Webhook-Signature"]),
                             bad.get("timestamp", headers["X-Webhook-Timestamp"]))
        assert caught.value.status_code == 401
    # A minute is skew; ten minutes is a replay.
    old, old_headers = signed({"paymentIntentId": "x"}, at=time.time() - 601)
    with pytest.raises(HTTPException, match="stale"):
        verify_signature(SECRET, old.encode(), old_headers["X-Webhook-Signature"], old_headers["X-Webhook-Timestamp"])
    # No secret configured means no receiver at all, not an open one.
    with pytest.raises(HTTPException) as caught:
        verify_signature("", raw.encode(), headers["X-Webhook-Signature"], headers["X-Webhook-Timestamp"])
    assert caught.value.status_code == 404


class RecordingLedger:
    def __init__(self):
        self.calls = []

    async def post(self, session, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture
def cash_app(db_session_factory):
    import asyncio

    async def seed():
        async with db_session_factory() as session:
            async with session.begin():
                await session.execute(insert(tenants).values(id="tenant", slug="tenant", name="Tenant"))
                await session.execute(insert(users).values(
                    id="alice", telegram_user_id=1, display_name="Alice", acquisition_tenant_id="tenant",
                ))
    asyncio.run(seed())
    ledger = RecordingLedger()
    partner = MockPservice()
    service = FiatOrderService(db_session_factory, partner=partner, ledger=ledger)
    app = FastAPI()
    app.include_router(fiat_webhooks.router)
    app.state.settings = SimpleNamespace(cash_fiat_webhook_secret=SECRET)
    app.state.cash_fiat_orders = service
    return app, service, partner, ledger


def test_a_signed_completion_credits_once_and_a_repeat_is_harmless(cash_app):
    app, service, partner, ledger = cash_app
    with TestClient(app) as client:
        import asyncio
        order = asyncio.run(service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1"))
        asyncio.run(service.mark_paid(order["id"], "alice"))
        partner._force_status(order["pservice_order_id"], COMPLETED_STATUS)

        raw, headers = signed({"externalTransactionId": order["id"], "provider": "Partner"})
        assert client.post("/api/payments/webhook/approval", content=raw, headers=headers).status_code == 200
        assert asyncio.run(service.get(order["id"], "alice"))["status"] == "credited"
        assert len(ledger.calls) == 1
        # Heard again -- from pservice's retry, or the poller a tick later.
        assert client.post("/api/payments/webhook/approval", content=raw, headers=headers).status_code == 200
        assert len(ledger.calls) == 1

        # Tampered body under a valid-looking header: refused, nothing read.
        assert client.post("/api/payments/webhook/approval", content=raw.replace(order["id"], "x" * 32),
                           headers=headers).status_code == 401
        # An order that is not ours is acknowledged, not refused: a refusal
        # holds pservice's event offset, and with it every later completion.
        raw, headers = signed({"externalTransactionId": "f" * 32, "provider": "Partner"})
        answer = client.post("/api/payments/webhook/approval", content=raw, headers=headers)
        assert answer.status_code == 200 and answer.json()["ok"] is False
        assert len(ledger.calls) == 1


def test_a_failure_webhook_is_keyed_by_the_intent_that_is_our_order_id(cash_app):
    import asyncio
    import uuid
    app, service, partner, ledger = cash_app
    with TestClient(app) as client:
        order = asyncio.run(service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1"))
        partner._force_status(order["pservice_order_id"], 9)   # cancelled on the partner's side
        raw, headers = signed({"paymentIntentId": str(uuid.UUID(hex=order["id"])),
                               "failureCode": "cancelled_by_trader", "failureReason": "cancelled_by_trader"})
        assert client.post("/api/payments/webhook/failure", content=raw, headers=headers).status_code == 200
        assert asyncio.run(service.get(order["id"], "alice"))["status"] == "cancelled"
        assert ledger.calls == []
        raw, headers = signed({"paymentIntentId": str(uuid.UUID(hex=order["id"]))})
        assert client.post("/api/payments/webhook/settlement", content=raw, headers=headers).status_code == 200
