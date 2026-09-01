from datetime import datetime, timezone

import httpx
import pytest

from cash.fiat_p2p import (
    Case8PartnerClient,
    MockCase8Partner,
    PartnerEvent,
    usdt_micros_to_case8_amount,
)


def test_case8_amount_uses_integer_usdt_cents():
    assert usdt_micros_to_case8_amount(20_000_000) == 2000
    assert usdt_micros_to_case8_amount(1_000_000_000) == 100000
    with pytest.raises(ValueError, match="whole USDT cents"):
        usdt_micros_to_case8_amount(20_001_000)
    with pytest.raises(ValueError, match="20 and 1000"):
        usdt_micros_to_case8_amount(19_990_000)


@pytest.mark.anyio
async def test_case8_client_sends_pinned_contract_and_parses_rub_order():
    seen = {}

    def handler(request: httpx.Request):
        seen.update(
            method=request.method,
            path=request.url.path,
            params=dict(request.url.params),
            token=request.headers.get("X-Token"),
        )
        return httpx.Response(200, json={
            "ID": 71,
            "Amount": 1850,
            "Method": "4276 **** **** 1234",
            "Expires": "2026-09-02T12:30:00Z",
            "Username": "trader_one",
        })

    client = Case8PartnerClient(
        "https://partner.example", "secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        order = await client.create_order(20_000_000, "RUB")
    finally:
        await client.close()

    assert seen == {
        "method": "POST", "path": "/order",
        "params": {"amount": "2000", "currency": "RUB"},
        "token": "secret",
    }
    assert order is not None
    assert order.partner_order_id == 71
    assert order.fiat_amount == 1850
    assert order.requisites == "4276 **** **** 1234"
    assert order.trader_username == "trader_one"
    assert order.expires_at == datetime(2026, 9, 2, 12, 30, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_case8_client_keeps_paid_as_notification_and_reads_events():
    requests = []

    def handler(request: httpx.Request):
        requests.append((request.method, request.url.path, dict(request.url.params)))
        if request.url.path == "/notify":
            return httpx.Response(200)
        return httpx.Response(200, json=[
            {"ID": 10, "Status": "WaitingTrader", "OrderID": 71},
            {"ID": 11, "Status": "CompletedByTrader", "OrderID": 71},
            {"ID": 12, "Status": "Clarifying", "OrderID": 72, "Reason": "contact_support"},
        ])

    client = Case8PartnerClient(
        "https://partner.example", "secret",
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.notify(71, cancel=False)
        events, offset = await client.poll_events(9)
    finally:
        await client.close()

    assert requests == [
        ("POST", "/notify", {"order_id": "71", "cancel": "false"}),
        ("GET", "/events", {"offset": "9"}),
    ]
    assert offset == 12
    assert events == [
        PartnerEvent(11, 71, "completed", None),
        PartnerEvent(12, 72, "clarifying", "contact_support"),
    ]


@pytest.mark.anyio
async def test_mock_partner_only_completes_after_user_notification():
    partner = MockCase8Partner(rub_per_usdt=90)
    order = await partner.create_order(20_000_000, "RUB")
    assert order is not None and order.fiat_amount == 1800
    assert await partner.poll_events(0) == ([], 0)

    await partner.notify(order.partner_order_id, cancel=False)
    assert await partner.poll_events(0) == (
        [PartnerEvent(1, order.partner_order_id, "completed", None)], 1,
    )
