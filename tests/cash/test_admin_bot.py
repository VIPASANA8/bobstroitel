import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from admin_bot.client import AdminAPIError, CashAdminClient
from admin_bot.config import BotConfig
from admin_bot.formatting import fiat_order_message, queue_messages


class Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self):
        return self.body


def test_client_sends_service_identity_actor_and_idempotency_key():
    captured = {}

    def opener(request, timeout):
        captured.update(headers=dict(request.header_items()), url=request.full_url,
                        body=json.loads(request.data), timeout=timeout)
        return Response({"status": "approved"})

    client = CashAdminClient("https://poker.example", "secret", opener=opener)
    result = client.decide(1001, "approve", "withdrawal-id", {"reason": "checked"}, key="command-1")
    assert result["status"] == "approved"
    assert captured["headers"]["X-cash-admin-key"] == "secret"
    assert captured["headers"]["X-cash-operator-telegram-id"] == "1001"
    assert captured["headers"]["Idempotency-key"] == "command-1"
    assert captured["body"] == {"reason": "checked"}


def test_client_surfaces_backend_denial():
    def opener(_request, timeout):
        raise HTTPError("url", 403, "Forbidden", {}, BytesIO(b'{"detail":"denied"}'))

    with pytest.raises(AdminAPIError) as denied:
        CashAdminClient("https://poker.example", "secret", opener=opener).me(999)
    assert denied.value.status == 403


def test_bot_refuses_plain_http_outside_localhost(monkeypatch):
    monkeypatch.setenv("POKER8_CASH_ADMIN_BOT_TOKEN", "token")
    monkeypatch.setenv("POKER8_CASH_ADMIN_API_KEY", "secret")
    monkeypatch.setenv("POKER8_CASH_ADMIN_API_URL", "http://poker.example")
    with pytest.raises(ValueError, match="HTTPS"):
        BotConfig.from_env()


def test_queue_format_keeps_money_and_identifiers_visible():
    messages = queue_messages({"withdrawals": [{
        "id": "w1", "status": "unknown", "user_id": "alice", "amount_micros": 1_250_000,
        "destination_address": "TWallet",
    }], "payment_reviews": [], "paused_tables": []})
    assert len(messages) == 1
    assert "1.25 USDT" in messages[0][3]
    assert "unknown" in messages[0][3]


def test_queue_format_exposes_fiat_orders_and_unknown_partner_events():
    messages = queue_messages({
        "withdrawals": [], "payment_reviews": [], "paused_tables": [],
        "fiat_orders": [{
            "id": "rub-1", "partner_order_id": 71, "status": "clarifying",
            "user_id": "alice", "requested_micros": 20_000_000,
            "fiat_kopecks": 180_050, "currency": "RUB", "detail": "contact support",
        }],
        "fiat_reviews": [{
            "event_id": 9, "partner_order_id": 404, "event_type": "completed",
            "status": "review_required", "detail": "unknown partner order",
        }],
    })
    assert len(messages) == 2
    assert "20 USDT" in messages[0][3] and "1800,50 RUB" in messages[0][3]
    assert "404" in messages[1][3] and "unknown partner order" in messages[1][3]


def test_order_card_shows_the_events_and_never_the_full_requisites():
    card = fiat_order_message({
        "id": "rub-1", "user_id": "alice", "status": "review_required",
        "currency": "RUB", "requested_micros": 20_000_000, "fiat_kopecks": 180_050,
        "partner_order_id": 71, "trader_username": "trader_one",
        "requisites_tail": "…1234", "expires_at": "2026-09-02T12:30:00+00:00",
        "detail": "unknown partner order",
        "events": [
            {"event_id": 41, "event_type": "completed", "status": "review_required",
             "detail": "unknown partner order"},
        ],
    })

    assert "1800,50 RUB" in card and "20 USDT" in card
    assert "…1234" in card and "4276" not in card
    assert "#41 completed" in card
