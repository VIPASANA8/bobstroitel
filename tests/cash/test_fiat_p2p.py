import httpx
import pytest

from cash.fiat_p2p import (
    COMPLETED_STATUS,
    MockPservice,
    PSERVICE_STATUS,
    PartnerProtocolError,
    PserviceClient,
    quote_with_fee,
    usdt_micros_to_case8_amount,
)


def test_case8_amount_uses_integer_usdt_cents():
    assert usdt_micros_to_case8_amount(20_000_000) == 2000
    assert usdt_micros_to_case8_amount(1_000_000_000) == 100000
    with pytest.raises(ValueError, match="whole USDT cents"):
        usdt_micros_to_case8_amount(20_001_000)
    with pytest.raises(ValueError, match="between 20 and 1000"):
        usdt_micros_to_case8_amount(10_000_000)


def test_the_fee_rounds_up_into_the_fee_never_into_the_credit():
    charged, fee = quote_with_fee(20_000_000, 100)  # 1%
    assert charged == 20_200_000 and fee == 200_000
    # A credit whose 1% is not a whole cent rounds the charge up, and the extra
    # is the fee, so the user is still credited exactly what they asked for.
    charged, fee = quote_with_fee(20_010_000, 100)
    assert charged % 10_000 == 0 and charged - fee == 20_010_000


def test_every_pservice_status_maps_to_a_state_and_only_completed_credits():
    # The mapping must be total over the partner's enum (0..10): an unmapped
    # status would raise mid-poll, and the whole point is no silent guessing.
    assert set(PSERVICE_STATUS) == set(range(11))
    assert PSERVICE_STATUS[COMPLETED_STATUS] == "credited"
    assert [k for k, v in PSERVICE_STATUS.items() if v == "credited"] == [7]


def test_the_client_requires_a_key_and_https_for_public_targets():
    with pytest.raises(ValueError, match="requires a service key"):
        PserviceClient("https://pservice.example", "")
    # A public host over plain http is refused; an internal one is allowed,
    # because on a private bridge network the transport never leaves the host.
    with pytest.raises(ValueError, match="HTTPS unless the target is internal"):
        PserviceClient("http://pservice.example", "k")
    PserviceClient("http://p2p-service:8000", "k")      # docker service name
    PserviceClient("http://127.0.0.1:8000", "k")        # loopback


@pytest.mark.anyio
async def test_the_client_speaks_api_v1_with_the_service_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("x-service-key")
        if request.url.path.endswith("/payments") and request.method == "POST":
            import json
            seen["body"] = json.loads(request.content)
            return httpx.Response(201, json={
                "order_id": "11111111-1111-1111-1111-111111111111",
                "status": 0, "status_name": "CREATED",
                "expires_at": "2026-09-04T12:00:00Z",
            })
        return httpx.Response(200, json={
            "id": "11111111-1111-1111-1111-111111111111",
            "user_id": "u", "payment_intent_id": "i",
            "status": 3, "status_name": "TRADER_FOUND",
            "amount_usdt": 2000, "currency": "RUB",
            "fiat_amount_with_commission": 181800,
            "trader_info": "4276 0000 0000 1234", "trader_tg": "@trader",
            "created_at": "2026-09-04T11:00:00Z", "expires_at": "2026-09-04T12:00:00Z",
        })

    client = PserviceClient("https://pservice.example", "svc-key",
                            transport=httpx.MockTransport(handler))
    payment = await client.create_payment(
        amount_micros=20_200_000, currency="RUB",
        client_payment_id="local-1", user_id="alice",
    )
    assert seen["path"] == "/api/v1/payments" and seen["key"] == "svc-key"
    assert seen["body"]["amount_usdt"] == 2020 and seen["body"]["currency"] == "RUB"
    assert payment.order_id == "11111111-1111-1111-1111-111111111111"

    status = await client.order_status(payment.order_id)
    assert status.local_status == "awaiting_user"
    assert status.fiat_kopecks == 181800
    assert status.requisites == "4276 0000 0000 1234" and status.trader_username == "@trader"
    await client.close()


@pytest.mark.anyio
async def test_an_unknown_status_from_the_wire_is_refused():
    client = PserviceClient(
        "https://pservice.example", "k",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
            "id": "x", "user_id": "u", "payment_intent_id": "i", "status": 99,
            "status_name": "?", "amount_usdt": 2000, "currency": "RUB",
            "created_at": "2026-09-04T11:00:00Z", "expires_at": "2026-09-04T12:00:00Z",
        })),
    )
    status = await client.order_status("x")
    with pytest.raises(PartnerProtocolError, match="unknown pservice status"):
        _ = status.local_status
    await client.close()


@pytest.mark.anyio
async def test_the_mock_runs_the_whole_lifecycle():
    partner = MockPservice(rub_per_usdt=90)
    payment = await partner.create_payment(
        amount_micros=20_000_000, currency="RUB", client_payment_id="l", user_id="alice",
    )
    # CREATED, then a trader is found on the first read.
    found = await partner.order_status(payment.order_id)
    assert found.local_status == "awaiting_user" and found.fiat_kopecks == 180_000
    # Confirm, and the next read completes it -- the only status that credits.
    await partner.confirm(payment.order_id)
    assert (await partner.order_status(payment.order_id)).local_status == "credited"


@pytest.mark.anyio
async def test_the_mock_can_be_cancelled():
    partner = MockPservice()
    payment = await partner.create_payment(
        amount_micros=20_000_000, currency="RUB", client_payment_id="l", user_id="alice",
    )
    await partner.cancel(payment.order_id)
    assert (await partner.order_status(payment.order_id)).local_status == "cancelled"
