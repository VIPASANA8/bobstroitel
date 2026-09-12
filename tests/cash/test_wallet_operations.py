from datetime import datetime, timedelta, timezone

import pytest

from cash.wallet import WalletService, mask
from online.schema import (
    cash_accounts, cash_deposits, cash_fiat_orders, cash_withdrawals, tenants, users,
)


pytestmark = pytest.mark.anyio


async def test_operations_list_every_order_newest_first_and_stay_private(db_session_factory):
    now = datetime.now(timezone.utc)
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(tenants.insert().values(id="tenant", slug="cash", name="Cash"))
            await session.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(cash_accounts.insert().values(
                id="alice-wallet", kind="available", user_id="alice", reference_id="alice"))
            await session.execute(cash_deposits.insert().values(
                id="dep-1", user_id="alice", tenant_id="tenant", request_key="d1", request_hash="a" * 64,
                network="TRC20", token_contract="T-usdt", destination_address="TXk9abcdefghijklmnop",
                requested_micros=10_000_000, expected_micros=10_010_000, status="expired",
                expires_at=now, created_at=now - timedelta(days=2), updated_at=now - timedelta(days=2)))
            await session.execute(cash_fiat_orders.insert().values(
                id="ord-1", user_id="alice", tenant_id="tenant", request_key="o1", request_hash="b" * 64,
                pservice_order_id="psv-777", currency="RUB", requested_micros=20_000_000,
                fiat_kopecks=181_550, requisites="2200 1234 5678 9012 · Сбербанк · Иван И.",
                status="cancelled", created_at=now - timedelta(days=1), updated_at=now - timedelta(days=1)))
            await session.execute(cash_withdrawals.insert().values(
                id="wd-1", user_id="alice", tenant_id="tenant", request_key="w1", request_hash="c" * 64,
                network="P2P_RUB", destination_address="+79991234567", amount_micros=50_000_000,
                reserve_account_id="alice-wallet", payout_id="p-1", quote_kopecks=4_600_00,
                status="confirmed", created_at=now, updated_at=now))
            await session.execute(cash_fiat_orders.insert().values(
                id="ord-bob", user_id="bob", tenant_id="tenant", request_key="ob", request_hash="d" * 64,
                currency="RUB", requested_micros=20_000_000, status="credited",
                created_at=now, updated_at=now))

    rows = await WalletService(db_session_factory).operations("alice")

    assert [(row["id"], row["kind"], row["status_label"], row["settled"]) for row in rows] == [
        ("wd-1", "withdrawal", "выплачен", True),
        ("ord-1", "fiat_order", "отменена", False),
        ("dep-1", "deposit", "истекла", False),
    ]
    # The number is hidden, the bank and the holder are not; nothing here is
    # a full address anybody could pay into or from.
    assert rows[0]["requisites"] == "+7****4567" and rows[0]["fiat_rub"] == "4600,00"
    assert rows[1]["requisites"] == "22****9012 · Сбербанк · Иван И."
    assert rows[1]["partner_order_id"] == "psv-777" and rows[1]["fiat_rub"] == "1815,50"
    assert rows[2]["requisites"] == "TX****mnop" and rows[2]["amount_micros"] == 10_010_000
    assert rows[0]["amount_micros"] == -50_000_000


def test_mask_keeps_short_values_unreadable():
    assert mask("123456") == "1****"
    assert mask(None) is None
