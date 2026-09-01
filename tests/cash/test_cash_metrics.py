from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import insert

from app.routers.health import metrics
from online.schema import cash_fiat_events, cash_fiat_orders, cash_partner_cursors, tenants, users


pytestmark = pytest.mark.anyio


async def test_metrics_report_fiat_attention_and_durable_partner_offset(db_session_factory):
    now = datetime.now(timezone.utc)
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(insert(tenants).values(id="tenant", slug="tenant", name="Tenant"))
            await session.execute(insert(users).values(
                id="alice", telegram_user_id=1, display_name="Alice",
                acquisition_tenant_id="tenant",
            ))
            await session.execute(insert(cash_fiat_orders).values(
                id="rub-1", user_id="alice", tenant_id="tenant", request_key="rub-1",
                request_hash="a" * 64, partner_order_id=71, currency="RUB",
                requested_micros=20_000_000, fiat_amount=1800, status="clarifying",
                expires_at=now + timedelta(minutes=5),
            ))
            await session.execute(insert(cash_fiat_events).values(
                provider="case8-p2p", event_id=9, partner_order_id=404,
                event_type="completed", status="review_required", detail="unknown partner order",
            ))
            await session.execute(insert(cash_partner_cursors).values(
                provider="case8-p2p", offset=9,
            ))
    state = SimpleNamespace(
        session_factory=db_session_factory, coordinator=None, integrity_monitor=None,
    )

    result = await metrics(SimpleNamespace(app=SimpleNamespace(state=state)))

    assert result["cash"] == {
        "expired_deposits_pending_reconciliation": 0,
        "unknown_withdrawals": 0,
        "fiat_orders_requiring_attention": 1,
        "fiat_events_requiring_review": 1,
        "paused_tables": 0,
        "partner_event_offset": 9,
    }
