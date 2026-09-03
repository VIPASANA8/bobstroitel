from datetime import datetime, timezone

import pytest
from sqlalchemy import insert

from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import MockPservice
from cash.fiat_reconciliation import daily_fiat_reconciliation
from online.schema import cash_fiat_orders


pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


async def credited_order(cash_db, *, request_key="rub-1"):
    service = FiatOrderService(cash_db, partner=MockPservice(rub_per_usdt=90))
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key=request_key,
    )
    await service.mark_paid(order["id"], "alice")
    await service.poll_once()
    return order


async def test_a_settled_day_balances_down_to_the_fee(cash_db):
    await credited_order(cash_db)

    report = await daily_fiat_reconciliation(cash_db, datetime.now(timezone.utc).date())

    assert report["balanced"] is True and report["mismatches"] == []
    assert report["orders"] == {
        "count": 1, "credited_usdt": "20", "fee_usdt": "0.2", "charged_rub": "1818,00",
    }
    assert report["ledger"] == {
        "credited_usdt": "20", "fee_usdt": "0.2", "clearing_usdt": "-20.2",
    }
    assert report["balances"] == {"clearing_usdt": "-20.2", "fee_usdt": "0.2"}


async def test_a_credit_without_a_posting_is_named_not_averaged_away(cash_db):
    await credited_order(cash_db)
    now = datetime.now(timezone.utc)
    async with cash_db() as session:
        async with session.begin():
            await session.execute(insert(cash_fiat_orders).values(
                id="ghost", user_id="alice", tenant_id="tenant", request_key="ghost",
                request_hash="a" * 64, currency="RUB", requested_micros=20_000_000,
                fee_micros=200_000, fiat_kopecks=181_800, status="credited",
                created_at=now, updated_at=now,
            ))

    report = await daily_fiat_reconciliation(cash_db, now.date())

    assert report["balanced"] is False
    assert report["mismatches"] == [
        {"order_id": "ghost", "reason": "credited order without a ledger posting"},
    ]
    # The totals still report what the user was told, so the gap is visible.
    assert report["orders"]["credited_usdt"] == "40"
    assert report["ledger"]["credited_usdt"] == "20"
