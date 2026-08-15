import asyncio

import pytest
from sqlalchemy import insert

from online.catalogue import Catalogue
from online.schema import tenants, users


@pytest.fixture
def user_id():
    return "u1"


@pytest.fixture
def catalogue(db_session_factory, user_id):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id=user_id,
                telegram_user_id=1,
                display_name="Player",
                acquisition_tenant_id="tenant",
            ))
            await session.commit()

    asyncio.run(seed())
    return Catalogue(db_session_factory)


@pytest.mark.anyio
async def test_seed_creates_exactly_six_network_tables(catalogue):
    await catalogue.seed_defaults()
    rows = await catalogue.list_tables(page=1, per_page=6)
    assert [(row.small_blind_units, row.big_blind_units) for row in rows] == [
        (50, 100), (50, 100),
        (100, 200), (100, 200),
        (500, 1_000), (500, 1_000),
    ]
    assert all(row.scope == "network" and row.max_seats == 6 for row in rows)


@pytest.mark.anyio
async def test_quick_play_prefers_most_occupied_affordable_lowest_stake(catalogue, user_id):
    await catalogue.seed_defaults()
    chosen = await catalogue.quick_play(user_id=user_id, available_units=8_000)
    assert chosen.big_blind_units == 100
    assert chosen.min_buy_in_units == 4_000
