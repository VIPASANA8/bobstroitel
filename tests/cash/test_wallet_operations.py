from datetime import datetime, timedelta, timezone

import pytest

from cash.wallet import WalletService
from online.schema import cash_accounts, cash_entries, cash_transactions, tenants, users


pytestmark = pytest.mark.anyio


async def test_operations_filter_before_limit_and_stay_private(db_session_factory):
    now = datetime.now(timezone.utc)
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(tenants.insert().values(id="tenant", slug="cash", name="Cash"))
            await session.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(cash_accounts.insert(), [
                {"id": "alice-wallet", "kind": "available", "user_id": "alice", "reference_id": "alice"},
                {"id": "bob-wallet", "kind": "available", "user_id": "bob", "reference_id": "bob"},
            ])
            transactions = [{
                "id": "alice-deposit", "scope": "c2c", "idempotency_key": "alice-deposit",
                "request_hash": "a" * 64, "kind": "deposit", "reference_id": "deposit",
                "actor": "system:test", "created_at": now - timedelta(days=1),
            }, {
                "id": "bob-deposit", "scope": "c2c", "idempotency_key": "bob-deposit",
                "request_hash": "b" * 64, "kind": "deposit", "reference_id": "deposit",
                "actor": "system:test", "created_at": now,
            }]
            entries = [
                {"transaction_id": "alice-deposit", "account_id": "alice-wallet", "amount_micros": 500_000},
                {"transaction_id": "bob-deposit", "account_id": "bob-wallet", "amount_micros": 700_000},
            ]
            for index in range(101):
                transaction_id = f"game-{index:03d}"
                transactions.append({
                    "id": transaction_id, "scope": "poker", "idempotency_key": transaction_id,
                    "request_hash": f"{index:064x}", "kind": "settlement", "reference_id": transaction_id,
                    "actor": "system:test", "created_at": now - timedelta(minutes=index),
                })
                entries.append({"transaction_id": transaction_id, "account_id": "alice-wallet", "amount_micros": 1})
            await session.execute(cash_transactions.insert(), transactions)
            await session.execute(cash_entries.insert(), entries)

    rows = await WalletService(db_session_factory).operations("alice", limit=20)

    assert [row["id"] for row in rows] == ["alice-deposit"]

