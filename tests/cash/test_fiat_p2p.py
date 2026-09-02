from datetime import datetime, timezone

import httpx
import pytest

from cash.fiat_p2p import (
    Case8PartnerClient,
    MockCase8Partner,
    PartnerEvent,
    PartnerProtocolError,
    _kopecks,
    usdt_micros_to_case8_amount,
)


def test_case8_amount_uses_integer_usdt_cents():
    assert usdt_micros_to_case8_amount(20_000_000) == 2000
    assert usdt_micros_to_case8_amount(1_000_000_000) == 100000
    with pytest.raises(ValueError, match="whole USDT cents"):
        usdt_micros_to_case8_amount(20_001_000)
    with pytest.raises(ValueError, match="20 and 1000"):
        usdt_micros_to_case8_amount(19_990_000)


@pytest.mark.parametrize("raw, kopecks", [
    ("1850,75", 185075), ("1850.75", 185075), ("1 850,5", 185050),
    (1850, 185000), (1850.0, 185000),
])
def test_partner_amount_reads_rub_kopecks_after_the_comma(raw, kopecks):
    assert _kopecks({"Amount": raw}, "Amount", "amount") == kopecks


@pytest.mark.parametrize("raw", ["1850,755", "1 850 ₽", "", None, True, "-5"])
def test_partner_amount_refuses_anything_it_cannot_read_exactly(raw):
    with pytest.raises(PartnerProtocolError):
        _kopecks({"Amount": raw}, "Amount", "amount")


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
            "Amount": "1850,75",
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
    assert order.fiat_kopecks == 185075
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
    assert order is not None and order.fiat_kopecks == 180_000
    assert await partner.poll_events(0) == ([], 0)

    await partner.notify(order.partner_order_id, cancel=False)
    assert await partner.poll_events(0) == (
        [PartnerEvent(1, order.partner_order_id, "completed", None)], 1,
    )


def _client(handler):
    return Case8PartnerClient(
        "https://partner.example", "secret", transport=httpx.MockTransport(handler),
    )


@pytest.mark.anyio
async def test_no_trader_and_no_events_are_answered_with_204():
    client = _client(lambda request: httpx.Response(204))
    try:
        assert await client.create_order(20_000_000, "RUB") is None
        assert await client.poll_events(7) == ([], 7)
    finally:
        await client.close()


@pytest.mark.anyio
@pytest.mark.parametrize("status", [400, 422, 429, 500, 503])
async def test_partner_error_statuses_reach_the_caller_untouched(status):
    client = _client(lambda request: httpx.Response(status))
    try:
        with pytest.raises(httpx.HTTPStatusError) as raised:
            await client.poll_events(7)
    finally:
        await client.close()
    assert raised.value.response.status_code == status


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [
    {"ID": 1},
    ["not-an-event"],
    [{"ID": 1, "OrderID": 71, "Status": "Teleported"}],
    [{"ID": "x", "OrderID": 71, "Status": "CompletedByTrader"}],
    [{"ID": 1, "OrderID": 71}],
])
async def test_malformed_events_are_poison_and_never_partially_applied(payload):
    client = _client(lambda request: httpx.Response(200, json=payload))
    try:
        with pytest.raises(PartnerProtocolError):
            await client.poll_events(0)
    finally:
        await client.close()


@pytest.mark.anyio
async def test_reordered_and_repeated_events_still_advance_to_the_highest_id():
    client = _client(lambda request: httpx.Response(200, json=[
        {"ID": 14, "OrderID": 71, "Status": "CompletedByTrader"},
        {"ID": 11, "OrderID": 72, "Status": "Expired"},
        {"ID": 14, "OrderID": 71, "Status": "CompletedByTrader"},
    ]))
    try:
        events, offset = await client.poll_events(10)
    finally:
        await client.close()

    assert offset == 14
    assert events == [
        PartnerEvent(14, 71, "completed", None),
        PartnerEvent(11, 72, "expired", None),
        PartnerEvent(14, 71, "completed", None),
    ]


@pytest.mark.anyio
async def test_me_reports_the_partner_fee_for_the_operator():
    client = _client(lambda request: httpx.Response(200, json={
        "ID": 4, "Title": "partner", "Fee": 2.5, "Deposit": 1000,
    }))
    try:
        assert (await client.me())["Fee"] == 2.5
    finally:
        await client.close()
