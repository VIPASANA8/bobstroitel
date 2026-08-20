"""A player's room is retired once it has sat without a human long enough."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, insert, select

from online.catalogue import Catalogue
from online.coordinator import ROOM_IDLE_TTL, OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import play_accounts, play_entries, poker_tables, system_players, table_seats, tenants, users
from online.seating import (
    BOT_ARRIVAL_WINDOW,
    BOT_FIRST_ARRIVAL,
    MAX_SYSTEM_BOTS,
    SeatingService,
)


class _ControllableClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


@pytest.fixture
def room(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"Bot {i}", "difficulty": "normal", "active": True}
                for i in range(1, 7)
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    clock = _ControllableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    catalogue = Catalogue(db_session_factory)
    runtime = TableRuntimeManager(db_session_factory, ledger, now=clock)
    seating = SeatingService(db_session_factory, ledger)
    coordinator = OnlineCoordinator(runtime, seating, catalogue, interval_seconds=0)
    created = asyncio.run(catalogue.create_room("u1", "Вечерний стол", "micro"))
    return coordinator, catalogue, clock, created.id, db_session_factory, seating, ledger


@pytest.mark.anyio
async def test_an_empty_room_is_retired_only_after_the_full_wait(room):
    coordinator, catalogue, clock, table_id, session_factory, seating, ledger = room

    await coordinator.tick()
    clock.advance(ROOM_IDLE_TTL - timedelta(minutes=1))
    await coordinator.tick()
    assert table_id in {row.id for row in await catalogue.list_tables(per_page=100)}, \
        "still open a minute short of the wait"

    clock.advance(timedelta(minutes=2))
    await coordinator.tick()
    assert table_id not in {row.id for row in await catalogue.list_tables(per_page=100)}


@pytest.mark.anyio
async def test_closing_a_room_you_are_sitting_in_gives_your_chips_back(room):
    """A closed table stops being advanced, so a stack left on it would stay
    locked in the table's escrow for good. The owner closing a room they are
    still sitting in is the one way that happens -- an idle room has nobody on
    it by definition."""
    coordinator, catalogue, clock, table_id, session_factory, seating, ledger = room

    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="owner", table_id=table_id, seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=4_000, state="seated"))
        await session.commit()
    await ledger.grant("u1", 4_000, "grant:u1")
    await ledger.reserve_buy_in("u1", table_id, 4_000, "buy:u1")
    before = await ledger.available_units("u1")

    await seating.evict_table(table_id)
    await catalogue.close_room(table_id, "u1")

    async with session_factory() as session:
        left = (await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == table_id, table_seats.c.state != "empty")
        )).scalars().all()
        escrow = (await session.execute(
            select(play_accounts.c.balance_units).where(
                play_accounts.c.owner_kind == "table",
                play_accounts.c.owner_id == table_id,
                play_accounts.c.account_kind == "escrow")
        )).scalar_one_or_none()
    assert left == [], "every seat was emptied"
    assert (escrow or 0) == 0, "and the table's escrow with it"
    assert await ledger.available_units("u1") == before + 4_000, "the stack went home"


@pytest.mark.anyio
async def test_the_clock_restarts_when_somebody_sits_down(room):
    coordinator, catalogue, clock, table_id, session_factory, seating, ledger = room

    await coordinator.tick()
    clock.advance(ROOM_IDLE_TTL - timedelta(minutes=1))
    await coordinator.tick()

    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="human", table_id=table_id, seat_no=5, occupant_kind="user",
            user_id="u1", stack_units=4_000, state="seated"))
        await session.commit()
    await coordinator.tick()  # occupied: the wait is forgotten

    async with session_factory() as session:
        await session.execute(
            table_seats.delete().where(table_seats.c.id == "human"))
        await session.commit()
    clock.advance(timedelta(minutes=2))
    await coordinator.tick()

    assert table_id in {row.id for row in await catalogue.list_tables(per_page=100)}, \
        "the wait starts over from when it emptied, not from when it opened"


@pytest.mark.anyio
async def test_a_new_room_stays_empty_until_its_owner_sits_down(room):
    """Seating bots the moment a room opens meant its creator walked into a
    hand already under way instead of their own table."""
    coordinator, catalogue, clock, table_id, session_factory, seating, ledger = room

    for _ in range(3):
        clock.advance(timedelta(seconds=30))
        await coordinator.tick()

    async with session_factory() as session:
        occupied = (await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == table_id, table_seats.c.state != "empty")
        )).scalars().all()
    assert occupied == [], "nobody is at the table, so no bot sat down"

    # And they do arrive once there is somebody to play against -- not at once,
    # but over the next few minutes, the way a real room fills.
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="owner", table_id=table_id, seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=4_000, state="seated"))
        await session.commit()
    await coordinator.tick()

    async def seated_bots():
        async with session_factory() as session:
            return (await session.execute(
                select(table_seats.c.id).where(
                    table_seats.c.table_id == table_id,
                    table_seats.c.occupant_kind == "system",
                    table_seats.c.state == "seated")
            )).scalars().all()

    assert await seated_bots() == [], "nobody is there the moment you sit down"

    clock.advance(BOT_FIRST_ARRIVAL[1])
    await coordinator.tick()
    assert len(await seated_bots()) >= 1, "the first one wanders in within the minute"

    clock.advance(BOT_ARRIVAL_WINDOW)
    await coordinator.tick()
    assert len(await seated_bots()) == MAX_SYSTEM_BOTS, "and the room is full by the end of the window"


@pytest.mark.anyio
async def test_closing_a_room_in_the_middle_of_a_hand_leaves_the_books_square(room):
    """A seat's stack_units only moves at settlement, so mid-hand it still reads
    the pre-hand number while the wagered chips sit in the table's escrow.
    Emptying the table then has to drain that escrow exactly -- neither leaving
    the pot behind nor handing back more than went in."""
    coordinator, catalogue, clock, table_id, session_factory, seating, ledger = room

    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="owner", table_id=table_id, seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=10_000, state="seated"))
        await session.commit()
    await ledger.grant("u1", 10_000, "grant:u1")
    await ledger.reserve_buy_in("u1", table_id, 10_000, "buy:u1")

    # Fill the room, then run until chips are actually in the middle.
    for _ in range(40):
        clock.advance(timedelta(seconds=30))
        await coordinator.tick()
        loaded = coordinator.runtime._tables.get(table_id)
        if loaded is not None and loaded.phase == "active" and loaded.state.pot > 0:
            break
    else:
        pytest.fail("no hand with a live pot to interrupt")

    total_before = await _total_balance(session_factory)
    await seating.evict_table(table_id)
    await catalogue.close_room(table_id, "u1")

    assert await _total_balance(session_factory) == total_before, "no chips minted or burned"
    async with session_factory() as session:
        stranded = (await session.execute(
            select(play_accounts.c.balance_units).where(
                play_accounts.c.account_kind == "escrow",
                play_accounts.c.balance_units != 0)
        )).scalars().all()
        mismatched = (await session.execute(
            select(play_accounts.c.id).where(
                play_accounts.c.balance_units != select(
                    func.coalesce(func.sum(play_entries.c.amount_units), 0)
                ).where(play_entries.c.account_id == play_accounts.c.id).scalar_subquery())
        )).scalars().all()
    assert stranded == [], "the pot went home with the players, not into a closed table"
    assert mismatched == [], "and every account still matches its own entries"


async def _total_balance(session_factory):
    async with session_factory() as session:
        return (await session.execute(select(func.sum(play_accounts.c.balance_units)))).scalar_one()
