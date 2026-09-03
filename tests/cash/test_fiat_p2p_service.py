from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from cash.fiat_orders import ActiveFiatOrderExists, FiatOrderService
from cash.fiat_p2p import MockCase8Partner, PartnerEvent
from cash.access import CashOperator
from cash.admin import CashAdminService
from cash.ledger import IdempotencyConflict
from online.schema import (
    cash_fiat_events, cash_fiat_orders, cash_partner_cursors, tenants, users,
)


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


async def test_create_is_content_bound_and_persists_partner_requisites(fiat_db):
    partner = MockCase8Partner(rub_per_usdt=90)
    service = FiatOrderService(fiat_db, partner=partner)

    first = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )
    again = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )

    assert again["id"] == first["id"]
    assert first["status"] == "awaiting_user"
    assert first["requested_micros"] == 20_000_000
    # 20 USDT credited, 1% on top, so the trader collects 20.20 USDT in roubles.
    assert first["fee_micros"] == 200_000
    assert first["fiat_kopecks"] == 181_800
    assert service.public(first)["fiat_rub"] == "1818,00"
    assert service.public(first)["fee_usdt"] == "0.2"
    assert service.public(first)["charged_usdt"] == "20.2"
    assert first["currency"] == "RUB"
    assert first["requisites"].startswith("4276")
    assert service.public(first)["requested_units"] == "200"
    assert service.public(first)["requested_usdt"] == "20"
    with pytest.raises(IdempotencyConflict):
        await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt="21", request_key="rub-1",
        )


async def test_user_paid_only_notifies_partner_and_never_credits(fiat_db):
    ledger = RecordingLedger()
    partner = MockCase8Partner()
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-paid",
    )

    paid = await service.mark_paid(order["id"], "alice")

    assert paid["status"] == "waiting_trader"
    assert ledger.calls == []


async def test_completed_event_credits_once_and_cursor_survives_restart(fiat_db):
    ledger = RecordingLedger()
    partner = MockCase8Partner()
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-complete",
    )
    await service.mark_paid(order["id"], "alice")

    assert await service.poll_once() == 1
    restarted = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    assert await restarted.poll_once() == 0

    final = await restarted.get(order["id"], "alice")
    assert final["status"] == "credited"
    assert len(ledger.calls) == 1
    # The clearing account pays the whole charge: 20 USDT to the user, 0.20 to us.
    assert sorted(ledger.calls[0]["postings"].values()) == [-20_200_000, 200_000, 20_000_000]
    async with fiat_db() as session:
        assert await session.scalar(select(cash_partner_cursors.c.offset)) == 1
        assert await session.scalar(select(cash_fiat_events.c.status)) == "processed"


async def test_terminal_nonpayment_event_never_credits(fiat_db):
    ledger = RecordingLedger()
    partner = MockCase8Partner()
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-cancel",
    )
    await service.cancel(order["id"], "alice")
    await service.poll_once()

    assert (await service.get(order["id"], "alice"))["status"] == "cancelled"
    assert ledger.calls == []


class UnknownOrderPartner:
    async def poll_events(self, offset):
        if offset:
            return [], offset
        return [PartnerEvent(9, 404, "completed")], 9


async def test_unknown_partner_event_is_quarantined_and_offset_advances(fiat_db):
    service = FiatOrderService(fiat_db, partner=UnknownOrderPartner(), ledger=RecordingLedger())

    assert await service.poll_once() == 1

    async with fiat_db() as session:
        event = (await session.execute(select(cash_fiat_events))).mappings().one()
        assert event["status"] == "review_required"
        assert event["partner_order_id"] == 404
        assert await session.scalar(select(cash_partner_cursors.c.offset)) == 9


async def test_admin_queue_and_user_view_include_scoped_fiat_state(fiat_db):
    partner = MockCase8Partner()
    fiat = FiatOrderService(fiat_db, partner=partner, ledger=RecordingLedger())
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
    assert user["fiat_orders"] == [{
        "id": order["id"], "partner_order_id": order["partner_order_id"],
        "status": "clarifying", "currency": "RUB", "fiat_kopecks": 181_800,
        "requested_usdt": "20",
    }]


async def test_database_allows_one_open_rub_order_per_user(fiat_db):
    service = FiatOrderService(fiat_db, partner=MockCase8Partner())
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
    service = FiatOrderService(fiat_db, partner=MockCase8Partner(), now=lambda: clock[0])
    first = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )

    clock[0] += timedelta(minutes=20)
    second = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-2",
    )

    assert (await service.get(first["id"], "alice"))["status"] == "expired"
    assert second["status"] == "awaiting_user"


async def test_a_lost_partner_answer_goes_to_review_instead_of_blocking_the_user(fiat_db):
    clock = [datetime.now(timezone.utc)]
    service = FiatOrderService(fiat_db, partner=MockCase8Partner(), now=lambda: clock[0])
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
    free = FiatOrderService(fiat_db, partner=MockCase8Partner(rub_per_usdt=90), fee_bps=0)
    order = await free.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-free",
    )

    assert order["fee_micros"] == 0
    assert order["fiat_kopecks"] == 180_000
    assert free.public(order)["charged_usdt"] == "20"


async def test_a_changed_redelivery_of_a_known_event_id_goes_to_review(fiat_db):
    ledger = RecordingLedger()
    partner = MockCase8Partner()
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )
    await service.mark_paid(order["id"], "alice")
    await service.poll_once()

    class Rewriter:
        async def poll_events(self, offset):
            return [PartnerEvent(1, order["partner_order_id"], "cancelled", "CanceledBySupport")], 1

    await FiatOrderService(fiat_db, partner=Rewriter(), ledger=ledger).poll_once()

    assert len(ledger.calls) == 1
    assert (await service.get(order["id"], "alice"))["status"] == "credited"
    async with fiat_db() as session:
        event = (await session.execute(select(cash_fiat_events))).mappings().one()
    assert event["status"] == "review_required"
    assert "redelivered event 1 as cancelled" in event["detail"]


@pytest.mark.parametrize("amount, accepted", [
    ("19.99", False), ("20", True), ("300", True), ("300.01", False), ("500", False), ("1000", False),
])
async def test_the_pilot_deposit_window_is_twenty_to_three_hundred(fiat_db, amount, accepted):
    service = FiatOrderService(fiat_db, partner=MockCase8Partner())
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
