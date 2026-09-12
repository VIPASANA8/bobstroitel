from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from cash.fiat_orders import ActiveFiatOrderExists, FiatOrderService
from cash.fiat_p2p import MockPservice, PartnerProtocolError, PserviceOrderStatus
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


async def test_one_unanswerable_order_does_not_block_the_others(fiat_db):
    """pservice answering 404 for one order (its database was rebuilt, say)
    must not leave every other paid deposit uncredited until an operator
    closes that one."""
    import httpx

    class Partner(MockPservice):
        lost = None

        async def order_status(self, order_id):
            if order_id == self.lost:
                request = httpx.Request("GET", f"http://p2p/api/v1/payments/{order_id}")
                raise httpx.HTTPStatusError("gone", request=request,
                                            response=httpx.Response(404, request=request))
            return await super().order_status(order_id)

    async with fiat_db() as session:
        async with session.begin():
            await session.execute(insert(users).values(
                id="bob", telegram_user_id=2, display_name="Bob", acquisition_tenant_id="tenant",
            ))
    ledger = RecordingLedger()
    partner = Partner()
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    stuck = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    paid = await service.create(user_id="bob", tenant_id="tenant", amount_usdt="20", request_key="k2")
    await service.mark_paid(paid["id"], "bob")
    partner.lost = stuck["pservice_order_id"]

    assert await service.poll_once() == 2
    assert (await service.get(paid["id"], "bob"))["status"] == "credited"
    assert (await service.get(stuck["id"], "alice"))["status"] == "awaiting_user"
    # Only the stuck one is left; a round where nothing could be read still
    # fails, so the poller backs off and the watchdog sees it.
    with pytest.raises(httpx.HTTPStatusError):
        await service.poll_once()


class ScriptedPservice(MockPservice):
    """A mock whose status reads come from a script, so a test can say what
    pservice answered without walking the happy path."""

    def __init__(self, *reads):
        super().__init__()
        self.reads = list(reads)

    async def order_status(self, order_id):
        base = await super().order_status(order_id)
        if not self.reads:
            return base
        override = self.reads.pop(0)
        return PserviceOrderStatus(**{**base.__dict__, **override})


async def test_no_trader_closes_the_order_instead_of_paging_an_operator(fiat_db):
    """pservice answers FAILED/no_traders_available before anyone saw
    requisites: nobody could have paid, so the slot frees up and the user
    sees "try later", not "under review"."""
    partner = ScriptedPservice({"status": 8, "requisites": None, "trader_username": None,
                                "detail": "no_traders_available"})
    service = FiatOrderService(fiat_db, partner=partner, ledger=RecordingLedger())
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    assert order["status"] == "unavailable" and order["detail"] == "no_traders_available"
    assert await service.active("alice") is None
    again = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k2")
    assert again["id"] != order["id"]


async def test_a_quote_that_ran_out_unpaid_expires_instead_of_paging_an_operator(fiat_db):
    """pservice fails a TRADER_FOUND order at its TTL (order_expired_ttl). The
    user saw a card and did not pay: nothing is owed, the slot frees up."""
    partner = ScriptedPservice({}, {"status": 8, "detail": "order_expired_ttl"})
    service = FiatOrderService(fiat_db, partner=partner, ledger=RecordingLedger())
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    assert order["status"] == "awaiting_user" and order["requisites"]
    await service.poll_once()
    final = await service.get(order["id"], "alice")
    assert final["status"] == "expired" and final["detail"] == "order_expired_ttl"
    assert await service.active("alice") is None


async def test_a_failure_after_the_user_paid_waits_for_a_person(fiat_db):
    partner = ScriptedPservice({}, {"status": 8, "detail": "partner_dispute"})
    service = FiatOrderService(fiat_db, partner=partner, ledger=RecordingLedger())
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    await service.mark_paid(order["id"], "alice")
    await service.poll_once()
    assert (await service.get(order["id"], "alice"))["status"] == "review_required"


async def test_an_earlier_order_the_partner_still_holds_is_named_not_crashed_into(fiat_db):
    """pservice returns the user's open order on create. If that order is
    already bound to a local row an operator closed, the second binding is
    refused by the database -- and the user gets a reason, not a 500."""
    from cash.fiat_p2p import PservicePayment
    from datetime import datetime, timezone

    class Partner(MockPservice):
        async def create_payment(self, **kwargs):
            payment = await super().create_payment(**kwargs)
            self.last = payment.order_id
            return payment

    partner = Partner()
    service = FiatOrderService(fiat_db, partner=partner, ledger=RecordingLedger())
    first = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    await service.mark_paid(first["id"], "alice")
    # An operator closes it locally; pservice still has it in AWAITING_RESULT.
    async with fiat_db() as session:
        async with session.begin():
            await session.execute(cash_fiat_orders.update().where(
                cash_fiat_orders.c.id == first["id"]).values(status="cancelled"))
    held = partner.last
    partner.create_payment = lambda **kw: _reused(held)

    async def _reused(order_id):
        return PservicePayment(order_id=order_id, status=6, expires_at=datetime.now(timezone.utc))

    with pytest.raises(ValueError, match="earlier order"):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k2")
    assert await service.active("alice") is None


async def test_a_pservice_order_for_another_amount_is_never_credited(fiat_db):
    """pservice hands a user their open order back on create. Bound to a quote
    for 20.20 USDT, a 100 USDT order must not credit 100 when it completes."""
    ledger = RecordingLedger()
    partner = ScriptedPservice({"amount_cents": 2020}, {"amount_cents": 2020, "status": 7})
    service = FiatOrderService(fiat_db, partner=partner, ledger=ledger)
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="100", request_key="k1")
    assert order["status"] == "review_required"
    assert "2020 USDT cents" in order["detail"] and "10100" in order["detail"]
    await service.poll_once()
    assert (await service.get(order["id"], "alice"))["status"] == "review_required"
    assert ledger.calls == []


async def test_a_partner_refusal_resyncs_instead_of_crashing(fiat_db):
    """The trader cancelled a tick before the user pressed "paid": pservice
    answers 409. The user gets a 409 and the real state, not a 500."""
    import httpx

    class Partner(MockPservice):
        async def confirm(self, order_id):
            self._force_status(order_id, 9)
            request = httpx.Request("POST", f"http://p2p/api/v1/orders/{order_id}/confirm")
            raise httpx.HTTPStatusError("conflict", request=request,
                                        response=httpx.Response(409, request=request))

    service = FiatOrderService(fiat_db, partner=Partner(), ledger=RecordingLedger())
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    with pytest.raises(ValueError, match="partner's side"):
        await service.mark_paid(order["id"], "alice")
    assert (await service.get(order["id"], "alice"))["status"] == "cancelled"


async def test_a_refused_create_frees_the_slot_at_once(fiat_db):
    """pservice answering 503 (no traders) must not leave a "requesting" row
    the user can neither cancel nor replace for five minutes."""
    import httpx

    class Partner(MockPservice):
        async def create_payment(self, **kwargs):
            request = httpx.Request("POST", "http://p2p/api/v1/payments")
            raise httpx.HTTPStatusError("busy", request=request,
                                        response=httpx.Response(503, request=request))

    service = FiatOrderService(fiat_db, partner=Partner(), ledger=RecordingLedger())
    with pytest.raises(ValueError, match="try again later"):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    assert await service.active("alice") is None
    # And the slot is free: the next attempt reaches the partner again.
    with pytest.raises(ValueError, match="try again later"):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k2")


async def test_a_slow_partner_answer_is_read_back_not_reported_as_failure(fiat_db):
    """pservice persists a cancel/confirm before it retries a dead backend
    webhook for half a minute. Live, our 15 s client gave up while the order
    was already cancelled there -- the user saw "could not cancel"."""
    import httpx

    class Partner(MockPservice):
        async def cancel(self, order_id):
            await super().cancel(order_id)          # applied...
            raise httpx.ReadTimeout("slow")           # ...but the answer never came

        async def confirm(self, order_id):
            # Applied, and parked in CLARIFYING so the mock's next read does not
            # walk it straight to COMPLETED: the point is the read-back, not the credit.
            self._force_status(order_id, 10)
            raise httpx.ReadTimeout("slow")

    service = FiatOrderService(fiat_db, partner=Partner(), ledger=RecordingLedger())
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    paid = await service.mark_paid(order["id"], "alice")
    assert paid["status"] == "clarifying" and paid["user_confirmed"] is True

    async with fiat_db() as session:
        async with session.begin():
            await session.execute(insert(users).values(
                id="bob", telegram_user_id=2, display_name="Bob", acquisition_tenant_id="tenant",
            ))
    other = await service.create(user_id="bob", tenant_id="tenant", amount_usdt="20", request_key="k2")
    assert (await service.cancel(other["id"], "bob"))["status"] == "cancelled"


async def test_a_timeout_on_a_call_that_did_not_land_is_an_error(fiat_db):
    import httpx

    class Partner(MockPservice):
        async def cancel(self, order_id):
            raise httpx.ConnectTimeout("down")        # nothing reached pservice

    service = FiatOrderService(fiat_db, partner=Partner(), ledger=RecordingLedger())
    order = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="k1")
    with pytest.raises(ValueError, match="did not answer in time"):
        await service.cancel(order["id"], "alice")
    assert (await service.get(order["id"], "alice"))["status"] == "awaiting_user"


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
    # A paid order the trader never answered surfaces once the quote is well
    # past its window; a fresh one does not, the trader may still be at it.
    async with fiat_db() as session:
        async with session.begin():
            await session.execute(cash_fiat_orders.update().where(
                cash_fiat_orders.c.id == order["id"],
            ).values(status="waiting_trader", user_confirmed=True,
                     expires_at=datetime(2026, 9, 11, 23, 3, tzinfo=timezone.utc)))
    soon = CashAdminService(fiat_db, now=lambda: datetime(2026, 9, 11, 23, 20, tzinfo=timezone.utc))
    late = CashAdminService(fiat_db, now=lambda: datetime(2026, 9, 11, 23, 40, tzinfo=timezone.utc))
    assert (await soon.queue(operator))["fiat_orders"] == []
    assert [row["id"] for row in (await late.queue(operator))["fiat_orders"]] == [order["id"]]
    async with fiat_db() as session:
        async with session.begin():
            await session.execute(cash_fiat_orders.update().where(
                cash_fiat_orders.c.id == order["id"],
            ).values(status="clarifying"))
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
