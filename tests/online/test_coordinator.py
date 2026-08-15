import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert

from online.catalogue import Catalogue
from online.coordinator import OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, table_seats, tenants
from online.seating import SeatingService


@pytest.fixture
def coordinator(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"Bot {i}", "difficulty": "normal", "active": True}
                for i in range(1, 7)
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    runtime = TableRuntimeManager(db_session_factory, ledger, now=lambda: datetime.now(timezone.utc))
    seating = SeatingService(db_session_factory, ledger)
    return OnlineCoordinator(runtime, seating, Catalogue(db_session_factory), interval_seconds=0)


@pytest.mark.anyio
async def test_coordinator_fills_table_and_starts_bot_hand(coordinator):
    await coordinator.tick()
    loaded = await coordinator.runtime.load("t1")

    assert loaded is not None
    assert loaded.phase == "active"
    assert len(loaded.state.players) == 6


@pytest.mark.anyio
async def test_coordinator_advances_result_to_next_hand(coordinator):
    await coordinator.tick()
    for _ in range(300):
        loaded = coordinator.runtime._tables["t1"]
        if loaded.state.terminal:
            break
        await coordinator.tick()
    else:
        pytest.fail("bot hand did not reach terminal state")

    await coordinator.tick()

    assert coordinator.runtime._tables["t1"].phase == "result"
    loaded = coordinator.runtime._tables["t1"]
    loaded.result_clear_at = coordinator.now()
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].phase == "countdown"
    loaded.next_hand_at = coordinator.now()
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].phase == "active"
