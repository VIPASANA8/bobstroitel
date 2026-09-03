from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from cash.fiat_orders import ActiveFiatOrderExists, FiatOrderService
from cash.fiat_p2p import MockPservice, PartnerProtocolError
from cash.access import CashOperator
from cash.admin import CashAdminService
from cash.ledger import IdempotencyConflict
from online.schema import cash_fiat_orders, tenants, users


pytestmark = pytest.mark.anyio


class RecordingLedger:
    def __init__(self):
        self.calls = []

    async def post(self, session, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture
async def fiat_db(db_session_factory):
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(insert(tenants).values(id="tenant", slug="tenant", name="Tenant"))
            await session.execute(insert(users).values(
                id="alice", telegram_user_id=1, display_name="Alice",
                acquisition_tenant_id="tenant",
            ))
    return db_session_factory


async def test_create_is_content_bound_and_shows_the_trader_requisites(fiat_db):
    service = FiatOrderService(fiat_db, partner=MockPservice(rub_per_usdt=90))

    first = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )
    again = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )

    assert again["id"] == first["id"]
    # A trader is found on the first status read, so the user sees requisites.
    assert first["status"] == "awaiting_user"
    assert first["pservice_order_id"] is not None
    assert first["requested_micros"] == 20_000_000
    # 20 USDT credited, 1% on top, so the trader collects 20.20 USDT in roubles.
    assert first["fee_micros"] == 200_000
    assert first["fiat_kopecks"] == 181_800
    assert service.public(first)["fiat_rub"] == "1818,00"
    assert service.public(first)["charged_usdt"] == "20.2"
    assert first["requisites"].startswith("4276")
    with pytest.raises(IdempotencyConflict):
        await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt="21", request_key="rub-1",
        )


async def test_user_paid_only_confirms_and_never_credits(fiat_db):
    ledger = RecordingLedger()
    service = FiatOrderService(fiat_db, partner=MockPservice(), ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-paid",
    )

    paid = await service.mark_paid(order["id"], "alice")

    assert paid["status"] == "waiting_trader" and paid["user_confirmed"] is True
    assert ledger.calls == []


async def test_a_completed_order_credits_once_and_a_restart_credits_nothing(fiat_db):
    ledger = RecordingLedger()
    partner = MockPservice()
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-complete",
    )
    await service.mark_paid(order["id"], "alice")

    # First poll sees COMPLETED and credits; the order is now terminal.
    assert await service.poll_once() == 1
    restarted = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    assert await restarted.poll_once() == 0

    final = await restarted.get(order["id"], "alice")
    assert final["status"] == "credited"
    assert len(ledger.calls) == 1
    # The clearing account pays the whole charge: 20 USDT to the user, 0.20 to us.
    assert sorted(ledger.calls[0]["postings"].values()) == [-20_200_000, 200_000, 20_000_000]
    assert ledger.calls[0]["key"] == f"case8-p2p:{order['id']}"


async def test_a_cancelled_order_never_credits(fiat_db):
    ledger = RecordingLedger()
    service = FiatOrderService(fiat_db, partner=MockPservice(), ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-cancel",
    )
    await service.cancel(order["id"], "alice")
    # A cancelled order is terminal, so the poll does not touch it.
    assert await service.poll_once() == 0

    assert (await service.get(order["id"], "alice"))["status"] == "cancelled"
    assert ledger.calls == []


async def test_an_unknown_pservice_status_is_refused_not_guessed(fiat_db):
    partner = MockPservice()
    service = FiatOrderService(fiat_db, partner=partner)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-weird",
    )
    partner._force_status(order["pservice_order_id"], 99)
    with pytest.raises(PartnerProtocolError, match="unknown pservice status"):
        await service.poll_once()
    # Nothing was applied: the order is left where it was for a person to see.
    assert (await service.get(order["id"], "alice"))["status"] == "awaiting_user"


async def test_a_confirmed_user_is_not_walked_back_by_a_lagging_trader_read(fiat_db):
    partner = MockPservice()
    service = FiatOrderService(fiat_db, partner=partner)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-lag",
    )
    await service.mark_paid(order["id"], "alice")   # -> waiting_trader, confirmed
    # pservice momentarily still reports TRADER_FOUND(3).
    partner._force_status(order["pservice_order_id"], 3)
    await service.poll_once()

    assert (await service.get(order["id"], "alice"))["status"] == "waiting_trader"


async def test_database_allows_one_open_rub_order_per_user(fiat_db):
    service = FiatOrderService(fiat_db, partner=MockPservice())
    first = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )
    assert (await service.active("alice"))["id"] == first["id"]

    with pytest.raises(ActiveFiatOrderExists):
        await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt="25", request_key="rub-2",
        )

    await service.cancel(first["id"], "alice")
    assert await service.active("alice") is None
    second = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="25", request_key="rub-2",
    )
    assert second["id"] != first["id"] and second["status"] == "awaiting_user"


async def test_an_expired_quote_stops_holding_the_users_only_open_slot(fiat_db):
    clock = [datetime.now(timezone.utc)]
    service = FiatOrderService(fiat_db, partner=MockPservice(), now=lambda: clock[0])
    first = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )

    clock[0] += timedelta(minutes=20)
    second = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-2",
    )

    assert (await service.get(first["id"], "alice"))["status"] == "expired"
    assert second["status"] == "awaiting_user"


async def test_a_lost_create_goes_to_review_instead_of_blocking_the_user(fiat_db):
    clock = [datetime.now(timezone.utc)]
    service = FiatOrderService(fiat_db, partner=MockPservice(), now=lambda: clock[0])
    async with fiat_db() as session:
        async with session.begin():
            await session.execute(insert(cash_fiat_orders).values(
                id="lost", user_id="alice", tenant_id="tenant", request_key="lost",
                request_hash="a" * 64, currency="RUB", requested_micros=20_000_000,
                status="requesting", created_at=clock[0], updated_at=clock[0],
            ))

    clock[0] += timedelta(minutes=6)
    fresh = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )

    lost = await service.get("lost", "alice")
    assert lost["status"] == "review_required" and lost["detail"] == "partner answer was lost"
    assert fresh["status"] == "awaiting_user"


async def test_the_deposit_fee_is_charged_on_top_and_never_taken_from_the_credit(fiat_db):
    free = FiatOrderService(fiat_db, partner=MockPservice(rub_per_usdt=90), fee_bps=0)
    order = await free.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-free",
    )

    assert order["fee_micros"] == 0
    assert order["fiat_kopecks"] == 180_000
    assert free.public(order)["charged_usdt"] == "20"


async def test_admin_queue_and_user_view_include_scoped_fiat_state(fiat_db):
    fiat = FiatOrderService(fiat_db, partner=MockPservice(), ledger=RecordingLedger())
    order = await fiat.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-admin",
    )
    async with fiat_db() as session:
        async with session.begin():
            await session.execute(cash_fiat_orders.update().where(
                cash_fiat_orders.c.id == order["id"],
            ).values(status="clarifying", detail="contact support"))
    operator = CashOperator("operator", 1001, "tenant", "operator")
    other = CashOperator("other", 1002, "other", "operator")
    admin = CashAdminService(fiat_db)

    assert [row["id"] for row in (await admin.queue(operator))["fiat_orders"]] == [order["id"]]
    assert (await admin.queue(other))["fiat_orders"] == []
    user = await admin.user(operator, "alice")
    assert user["fiat_orders"][0]["id"] == order["id"]
    assert user["fiat_orders"][0]["status"] == "clarifying"


@pytest.mark.parametrize("amount, accepted", [
    ("19.99", False), ("20", True), ("300", True), ("300.01", False), ("500", False), ("1000", False),
])
async def test_the_pilot_deposit_window_is_twenty_to_three_hundred(fiat_db, amount, accepted):
    service = FiatOrderService(fiat_db, partner=MockPservice())
    if accepted:
        order = await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt=amount, request_key="rub-" + amount,
        )
        assert order["status"] == "awaiting_user"
    else:
        with pytest.raises(ValueError, match="between 20 and 300"):
            await service.create(
                user_id="alice", tenant_id="tenant", amount_usdt=amount, request_key="rub-" + amount,
            )
