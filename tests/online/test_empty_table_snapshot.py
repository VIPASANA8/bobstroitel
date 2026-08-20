"""A table that has never dealt a hand is an ordinary state, not a failure."""

import asyncio

import pytest
from sqlalchemy import insert

from online.ledger import PlayLedger
from online.runtime import EMPTY_SNAPSHOT, TableRuntimeManager
from online.schema import poker_tables, tenants


@pytest.fixture
def runtime(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables).values(
                id="fresh", scope="network", name="Fresh", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
            await session.commit()

    asyncio.run(seed())
    return TableRuntimeManager(db_session_factory, PlayLedger(db_session_factory))


@pytest.mark.anyio
async def test_a_table_with_no_hand_behind_it_renders_instead_of_raising(runtime):
    """Raising killed the websocket before it sent anything: the REST route
    caught it and drew an empty table, the socket did not, so a freshly opened
    room could only tell its owner "reconnecting" -- forever, since no amount
    of retrying makes a hand appear."""
    snapshot = await runtime.public_snapshot("fresh", "u1")

    assert snapshot["phase"] == "waiting"
    assert snapshot["players"] == {}
    assert snapshot["legal_actions"] == []
    assert snapshot["viewer_state"] == "spectator"
    for key in EMPTY_SNAPSHOT:
        assert key in snapshot
