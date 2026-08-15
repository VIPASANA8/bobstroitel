import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, table_seats, tenants, users


@pytest.fixture
def runtime_factory(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
            ))
            await session.execute(insert(system_players).values(
                id="bot-1", name="Room Player", difficulty="normal", active=True,
            ))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.execute(insert(table_seats), [
                {"id": "seat-u1", "table_id": "t1", "seat_no": 0, "occupant_kind": "user",
                 "user_id": "u1", "system_player_id": None, "stack_units": 100_000, "state": "seated"},
                {"id": "seat-bot", "table_id": "t1", "seat_no": 1, "occupant_kind": "system",
                 "user_id": None, "system_player_id": "bot-1", "stack_units": 100_000, "state": "seated"},
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(ledger.grant("u1", 100_000, "grant:u1"))

    def factory(now=None):
        return TableRuntimeManager(db_session_factory, ledger, now=now)

    return factory


@pytest.mark.anyio
async def test_restart_restores_exact_hand_and_grants_ten_second_grace(runtime_factory):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = runtime_factory(now=lambda: now)
    await first.start_hand("t1")
    before = await first.private_snapshot("t1")
    deadline = first._tables["t1"].action_deadline

    restored = runtime_factory(now=lambda: deadline + timedelta(seconds=1))
    await restored.restore_all()
    after = await restored.private_snapshot("t1")
    public = await restored.public_snapshot("t1", "u1")

    assert after["deck_cards"] == before["deck_cards"]
    assert after["players"] == before["players"]
    assert public["revision"] == 1
    assert datetime.fromisoformat(public["action_deadline"]) >= deadline + timedelta(seconds=10)
