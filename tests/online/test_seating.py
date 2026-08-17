import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select, update

from online.ledger import PlayLedger
from online.schema import poker_tables, seat_queue, system_players, table_seats, tenants, users
from online.seating import MAX_SYSTEM_BOTS, READY_TTL, AlreadySeated, SeatingService


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
async def test_boundary_seats_both_requests_without_overfilling(seating, db_session_factory, table_id, user_a, user_b):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.ready(user_b, table_id, seat_no=2, buy_in_units=4_000)
    result = await seating.process_boundary(table_id)
    # FIFO: the first request wins seat 2, the second falls back to another seat.
    assert result.seated_user_ids == [user_a, user_b]
    # The table keeps a bounded number of bots, so both players fit on free
    # seats and no system player has to be evicted to make room.
    async with db_session_factory() as session:
        seats = (await session.execute(select(table_seats).where(
            table_seats.c.table_id == table_id, table_seats.c.state == "seated",
        ))).mappings().all()
    assert sum(1 for seat in seats if seat["occupant_kind"] == "system") <= MAX_SYSTEM_BOTS
    assert len(seats) <= 6


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


async def seat_states(session_factory, user_id):
    async with session_factory() as session:
        return (
            await session.execute(select(table_seats.c.state).where(table_seats.c.user_id == user_id))
        ).scalars().all()


@pytest.mark.anyio
async def test_boundary_releases_a_seat_whose_hold_expired(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    now = datetime.now(timezone.utc)
    await seating.mark_disconnected(user_a, table_id, now - timedelta(minutes=5))

    await seating.process_boundary(table_id, now=now)

    assert await seat_states(db_session_factory, user_a) == []


@pytest.mark.anyio
async def test_disconnect_does_not_undo_a_pending_leave(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.request_leave(user_a, table_id)
    await seating.mark_disconnected(user_a, table_id, datetime.now(timezone.utc))

    assert await seat_states(db_session_factory, user_a) == ["leaving"]


@pytest.mark.anyio
async def test_user_can_sit_down_again_after_leaving(seating, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.request_leave(user_a, table_id)
    await seating.process_boundary(table_id)

    request = await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)

    assert request.state == "waiting"


@pytest.mark.anyio
async def test_ready_request_outlives_a_running_hand(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    boundary = datetime.now(timezone.utc) + READY_TTL - timedelta(seconds=1)

    await seating.process_boundary(table_id, now=boundary)

    async with db_session_factory() as session:
        assert (await session.execute(select(seat_queue.c.state))).scalars().all() == ["seated"]


@pytest.mark.anyio
async def test_request_for_a_taken_seat_falls_back(seating, db_session_factory, user_a, user_b, table_id):
    await seating.ready(user_b, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)

    result = await seating.process_boundary(table_id)

    assert result.seated_user_ids == [user_a]
    assert await seat_states(db_session_factory, user_a) == ["seated"]


@pytest.mark.anyio
async def test_restart_holds_seats_so_they_can_be_released(seating, db_session_factory, user_a, table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)
    now = datetime.now(timezone.utc)

    await seating.hold_all_users(now)
    await seating.process_boundary(table_id, now=now + timedelta(minutes=1))

    assert await seat_states(db_session_factory, user_a) == []


@pytest.mark.anyio
async def test_blocked_ready_reports_where_the_user_is_seated(seating, user_a, table_id, second_table_id):
    await seating.ready(user_a, table_id, seat_no=2, buy_in_units=4_000)
    await seating.process_boundary(table_id)

    with pytest.raises(AlreadySeated) as error:
        await seating.ready(user_a, second_table_id, seat_no=1, buy_in_units=4_000)

    assert error.value.table_id == table_id
    assert error.value.seat_state == "seated"
