"""The dashboard has to describe the network that exists."""

import pytest
from sqlalchemy import insert

from online.schema import poker_tables, table_runtimes, tenants


@pytest.fixture
def seeded(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables), [
                {"id": "live", "scope": "network", "name": "Live", "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100,
                 "max_seats": 6, "status": "open"},
                {"id": "retired", "scope": "network", "name": "Retired", "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100,
                 "max_seats": 6, "status": "closed", "created_by": "u1"},
            ])
            # A retired room keeps its runtime row, frozen where it died.
            await session.execute(insert(table_runtimes), [
                {"table_id": "live", "phase": "waiting", "revision": 0, "state_json": {}},
                {"table_id": "retired", "phase": "active", "revision": 7, "state_json": {}},
            ])
            await session.commit()

    return seed


@pytest.mark.anyio
async def test_a_retired_room_is_not_counted_as_a_live_table(seeded, db_session_factory):
    """Counting every runtime row reported seven active tables on a network
    with six, and the number grew with every room anyone had ever opened."""
    import asyncio

    from sqlalchemy import func, select

    await seeded()
    async with db_session_factory() as session:
        phases = dict((await session.execute(
            select(table_runtimes.c.phase, func.count())
            .select_from(table_runtimes.join(poker_tables, poker_tables.c.id == table_runtimes.c.table_id))
            .where(poker_tables.c.status == "open")
            .group_by(table_runtimes.c.phase)
        )).all())
        total = (await session.execute(
            select(func.count()).select_from(poker_tables).where(poker_tables.c.status == "open")
        )).scalar_one()

    assert total == 1, "one open table"
    assert phases == {"waiting": 1}, f"the retired room's frozen 'active' leaked in: {phases}"


def test_the_endpoint_asks_the_same_question():
    from pathlib import Path

    source = Path("app/routers/health.py").read_text(encoding="utf-8")
    metrics = source[source.index("async def metrics("):]
    assert metrics.count('poker_tables.c.status == "open"') >= 3, \
        "tables, phases and seats all have to be scoped to open tables"
