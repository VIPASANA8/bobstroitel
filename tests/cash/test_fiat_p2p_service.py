from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select

from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import MockCase8Partner, PartnerEvent
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
    assert first["fiat_amount"] == 1800
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
    assert sorted(ledger.calls[0]["postings"].values()) == [-20_000_000, 20_000_000]
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
