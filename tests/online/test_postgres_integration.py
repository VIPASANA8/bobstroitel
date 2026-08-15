from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import insert, select

from online.database import create_database
from online.ledger import PlayLedger
from online.schema import play_accounts, poker_tables, tenants, users


@pytest.mark.postgres
def test_play_balances_survive_a_new_postgres_session():
    database_url = os.environ.get("POKER8_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POKER8_TEST_DATABASE_URL is not configured")

    async def run():
        engine, session_factory = create_database(database_url)
        suffix = uuid.uuid4().hex[:8]
        user_id = f"u-{suffix}"
        table_id = f"t-{suffix}"
        tenant_id = f"tenant-{suffix}"
        async with session_factory() as session:
            async with session.begin():
                await session.execute(tenants.insert().values(id=tenant_id, slug=f"p-{suffix}", name="Test"))
                await session.execute(users.insert().values(
                    id=user_id,
                    telegram_user_id=int(suffix[:7], 16),
                    display_name="Test",
                    acquisition_tenant_id=tenant_id,
                ))
                await session.execute(poker_tables.insert().values(
                    id=table_id,
                    scope="network",
                    name="Test",
                    small_blind_units=50,
                    big_blind_units=100,
                    min_buy_in_bb=40,
                    max_buy_in_bb=100,
                    max_seats=6,
                ))
        ledger = PlayLedger(session_factory)
        await ledger.grant(user_id, 10_000, f"grant:{suffix}")
        await ledger.reserve_buy_in(user_id, table_id, 4_000, f"buyin:{suffix}")
        await engine.dispose()

        engine, session_factory = create_database(database_url)
        assert await PlayLedger(session_factory).available_units(user_id) == 6_000
        async with session_factory() as session:
            escrow = (
                await session.execute(
                    select(play_accounts.c.balance_units).where(
                        play_accounts.c.owner_kind == "table",
                        play_accounts.c.owner_id == table_id,
                        play_accounts.c.account_kind == "escrow",
                    )
                )
            ).scalar_one()
            assert escrow == 4_000
        await engine.dispose()

    asyncio.run(run())
