import asyncio

import pytest
from sqlalchemy import insert, select, update

from online.ledger import PlayLedger
from online.schema import poker_tables, system_players, table_seats, tenants, users
from online.seating import AlreadySeated, SeatingService


@pytest.fixture
def user_a():
    return "u1"


@pytest.fixture
def user_b():
    return "u2"


@pytest.fixture
def table_id():
    return "t1"


@pytest.fixture
def second_table_id():
    return "t2"


@pytest.fixture
def ledger(db_session_factory, user_a, user_b, table_id, second_table_id):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users), [
                {"id": user_a, "telegram_user_id": 1, "display_name": "A", "acquisition_tenant_id": "tenant"},
                {"id": user_b, "telegram_user_id": 2, "display_name": "B", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(insert(system_players), [
                {"id": f"bot-{index}", "name": f"Room Player {index}", "difficulty": "normal", "active": True}
                for index in range(1, 7)
            ])
            await session.execute(insert(poker_tables), [
                {"id": table_id, "scope": "network", "name": "One", "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100, "max_seats": 6},
                {"id": second_table_id, "scope": "network", "name": "Two", "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100, "max_seats": 6},
            ])
            await session.commit()

    asyncio.run(seed())
    service = PlayLedger(db_session_factory)
    asyncio.run(service.ensure_faucet())
    asyncio.run(service.grant(user_a, 100_000, "grant:u1"))
    asyncio.run(service.grant(user_b, 100_000, "grant:u2"))
    return service


@pytest.fixture
def seating(db_session_factory, ledger):
    return SeatingService(db_session_factory, ledger)


@pytest.mark.anyio
async def test_ready_appends_fifo_and_reserves_nothing(seating, ledger, user_a, table_id):
    request = await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    assert request.state == "waiting"
    assert await ledger.available_units(user_a) == 100_000


@pytest.mark.anyio
async def test_boundary_seats_first_request_and_replaces_system_player(seating, table_id, user_a, user_b):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.ready(user_b, table_id, seat_no=2, buy_in_units=4_000)
    result = await seating.process_boundary(table_id)
    assert result.seated_user_ids == [user_a]
    assert result.removed_system_player_ids


@pytest.mark.anyio
async def test_same_user_cannot_hold_two_network_seats(seating, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    with pytest.raises(AlreadySeated):
        await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)


@pytest.mark.anyio
async def test_boundary_removes_zero_stack_user_so_they_can_rejoin(seating, db_session_factory, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(
                update(table_seats)
                .where(table_seats.c.table_id == table_id, table_seats.c.user_id == user_a)
                .values(stack_units=0, state="held")
            )

    await seating.process_boundary(table_id)

    async with db_session_factory() as session:
        row = (await session.execute(
            select(table_seats.c.state, table_seats.c.user_id)
            .where(table_seats.c.table_id == table_id, table_seats.c.seat_no == 2)
        )).mappings().one()
    assert row["user_id"] is None
    assert (await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)).state == "waiting"
