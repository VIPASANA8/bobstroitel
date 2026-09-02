from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import MockCase8Partner
from cash.watchdog import REQUISITES_RETENTION, CashWatchdog
from online.schema import cash_fiat_events, cash_fiat_orders, tenants, users


pytestmark = pytest.mark.anyio


class Recorder:
    configured = True

    def __init__(self):
        self.sent = []

    async def send(self, event, text, payload):
        self.sent.append((event, payload["finding"]))


class FakePoller:
    def __init__(self, *, leader=True, poisoned=False, last_success_at=None, last_error=None):
        self.leader = leader
        self.poisoned = poisoned
        self.last_success_at = last_success_at
        self.last_error = last_error


@pytest.fixture
async def cash_rows(db_session_factory):
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(insert(tenants).values(id="tenant", slug="tenant", name="Tenant"))
            await session.execute(insert(users).values(
                id="alice", telegram_user_id=1, display_name="Alice", acquisition_tenant_id="tenant",
            ))
    return db_session_factory


async def test_a_finding_alerts_once_and_once_more_when_it_clears(cash_rows):
    notifier = Recorder()
    watchdog = CashWatchdog(cash_rows, notifier=notifier, housekeeping_seconds=10_000)
    async with cash_rows() as session:
        async with session.begin():
            await session.execute(insert(cash_fiat_events).values(
                provider="case8-p2p", event_id=9, partner_order_id=404,
                event_type="completed", status="review_required", detail="unknown partner order",
            ))

    assert sorted(await watchdog.check()) == ["fiat-events-review"]
    await watchdog.check()
    assert notifier.sent == [("poker8_cash_alert", "fiat-events-review")]

    async with cash_rows() as session:
        async with session.begin():
            await session.execute(cash_fiat_events.update().values(status="processed"))
    assert await watchdog.check() == {}
    assert notifier.sent[-1] == ("poker8_cash_alert_cleared", "fiat-events-review")


async def test_a_stopped_partner_poll_is_the_alert_nobody_gets_from_silence(cash_rows):
    now = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    stalled = CashWatchdog(
        cash_rows, poller=FakePoller(last_success_at=now - timedelta(seconds=600)),
        notifier=Recorder(), housekeeping_seconds=10_000, now=lambda: now,
    )
    poisoned = CashWatchdog(
        cash_rows, poller=FakePoller(poisoned=True, last_error="unknown status"),
        notifier=Recorder(), housekeeping_seconds=10_000, now=lambda: now,
    )
    healthy = CashWatchdog(
        cash_rows, poller=FakePoller(last_success_at=now - timedelta(seconds=5)),
        notifier=Recorder(), housekeeping_seconds=10_000, now=lambda: now,
    )
    follower = CashWatchdog(
        cash_rows, poller=FakePoller(leader=False), notifier=Recorder(),
        housekeeping_seconds=10_000, now=lambda: now,
    )

    assert "poller-stalled" in await stalled.check()
    assert "unknown status" in (await poisoned.check())["poller-poisoned"]
    assert await healthy.check() == {}
    # A process that never won the lock has no poll to be late with.
    assert await follower.check() == {}


async def test_requisites_do_not_outlive_their_retention(cash_rows):
    service = FiatOrderService(cash_rows, partner=MockCase8Partner())
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-1",
    )
    watchdog = CashWatchdog(cash_rows, fiat=service, notifier=Recorder())

    await watchdog.check()
    async with cash_rows() as session:
        assert await session.scalar(select(cash_fiat_orders.c.requisites)) == order["requisites"]

    async with cash_rows() as session:
        async with session.begin():
            await session.execute(cash_fiat_orders.update().values(
                created_at=datetime.now(timezone.utc) - REQUISITES_RETENTION - timedelta(hours=1),
            ))
    await watchdog._housekeeping()

    async with cash_rows() as session:
        assert await session.scalar(select(cash_fiat_orders.c.requisites)) is None
    assert watchdog.purged_requisites == 1


async def test_cancelling_after_saying_you_paid_becomes_an_operator_signal(cash_rows):
    now = datetime.now(timezone.utc)
    watchdog = CashWatchdog(cash_rows, notifier=Recorder(), housekeeping_seconds=10_000)
    async with cash_rows() as session:
        async with session.begin():
            for index in range(3):
                await session.execute(insert(cash_fiat_orders).values(
                    id=f"order-{index}", user_id="alice", tenant_id="tenant",
                    request_key=f"key-{index}", request_hash="a" * 64,
                    partner_order_id=100 + index, currency="RUB",
                    requested_micros=20_000_000, fee_micros=200_000, status="cancelled",
                    user_confirmed=True, created_at=now, updated_at=now,
                ))

    findings = await watchdog.check()

    assert findings["cancel-after-paid-alice"] == "пользователь alice: 3 отмен после «я оплатил» за сутки"


async def test_two_cancellations_are_not_yet_a_pattern(cash_rows):
    now = datetime.now(timezone.utc)
    watchdog = CashWatchdog(cash_rows, notifier=Recorder(), housekeeping_seconds=10_000)
    async with cash_rows() as session:
        async with session.begin():
            for index in range(2):
                await session.execute(insert(cash_fiat_orders).values(
                    id=f"order-{index}", user_id="alice", tenant_id="tenant",
                    request_key=f"key-{index}", request_hash="a" * 64,
                    partner_order_id=200 + index, currency="RUB",
                    requested_micros=20_000_000, fee_micros=200_000, status="cancelled",
                    user_confirmed=True, created_at=now, updated_at=now,
                ))

    assert await watchdog.check() == {}
