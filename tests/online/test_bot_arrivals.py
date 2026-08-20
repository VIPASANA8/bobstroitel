"""Bots walk into a player's room one at a time, not all four at once."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from online.catalogue import Catalogue
from online.ledger import PlayLedger
from online.schema import system_players, table_seats, tenants, users
from online.seating import (
    BOT_ARRIVAL_WINDOW,
    BOT_FIRST_ARRIVAL,
    MAX_SYSTEM_BOTS,
    SeatingService,
)


@pytest.fixture
def room(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"N{i}", "difficulty": "normal", "active": True}
                for i in range(1, 9)
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    catalogue = Catalogue(db_session_factory)
    seating = SeatingService(db_session_factory, ledger)

    async def make(visibility="public"):
        created = await catalogue.create_room("u1", f"Стол {visibility}", "micro", visibility)
        await _sit(db_session_factory, created.id)
        return created.id

    return seating, make, db_session_factory


async def _sit(session_factory, table_id):
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id=f"owner-{table_id}", table_id=table_id, seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=4_000, state="seated"))
        await session.commit()


async def _bot_count(session_factory, table_id):
    async with session_factory() as session:
        return len((await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
                table_seats.c.state == "seated")
        )).scalars().all())


@pytest.mark.anyio
async def test_they_arrive_one_at_a_time_across_the_window(room):
    seating, make, session_factory = room
    table_id = await make("public")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    await seating.process_boundary(table_id, now=start)
    assert await _bot_count(session_factory, table_id) == 0, "the room is yours alone at first"

    # Nobody may be seated before the earliest the first one could turn up.
    await seating.process_boundary(table_id, now=start + BOT_FIRST_ARRIVAL[0] - timedelta(seconds=1))
    assert await _bot_count(session_factory, table_id) == 0

    await seating.process_boundary(table_id, now=start + BOT_FIRST_ARRIVAL[1])
    assert await _bot_count(session_factory, table_id) == 1, "one, not the whole table"

    await seating.process_boundary(table_id, now=start + BOT_ARRIVAL_WINDOW)
    assert await _bot_count(session_factory, table_id) == MAX_SYSTEM_BOTS


@pytest.mark.anyio
async def test_a_link_only_room_is_left_for_the_people_you_invited(room):
    seating, make, session_factory = room
    table_id = await make("link")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    for minutes in (0, 1, 5, 30):
        await seating.process_boundary(table_id, now=start + timedelta(minutes=minutes))
        assert await _bot_count(session_factory, table_id) == 0, \
            "a bot in one of those seats is taking it from an invited player"


@pytest.mark.anyio
async def test_the_wait_starts_over_for_the_next_person_to_open_the_room(room):
    """A schedule left behind would let the next arrival be instant."""
    seating, make, session_factory = room
    table_id = await make("public")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    await seating.process_boundary(table_id, now=start)  # draws the schedule
    await seating.process_boundary(table_id, now=start + BOT_ARRIVAL_WINDOW)
    assert await _bot_count(session_factory, table_id) == MAX_SYSTEM_BOTS

    async with session_factory() as session:
        await session.execute(table_seats.delete().where(table_seats.c.id == f"owner-{table_id}"))
        await session.commit()
    later = start + BOT_ARRIVAL_WINDOW + timedelta(minutes=1)
    await seating.process_boundary(table_id, now=later)
    assert await _bot_count(session_factory, table_id) == 0, "they leave with the last person"

    await _sit(session_factory, table_id)
    await seating.process_boundary(table_id, now=later)
    assert await _bot_count(session_factory, table_id) == 0, "and the wait begins again"


@pytest.mark.anyio
async def test_they_do_not_all_turn_up_together(room):
    """Independent draws across the window bunch: three arriving at once is the
    thing the wait exists to avoid, so each gets a slot of its own."""
    seating, make, session_factory = room
    table_id = await make("public")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    await seating.process_boundary(table_id, now=start)
    seen = []
    for second in range(0, int(BOT_ARRIVAL_WINDOW.total_seconds()) + 30, 15):
        await seating.process_boundary(table_id, now=start + timedelta(seconds=second))
        seen.append((second, await _bot_count(session_factory, table_id)))

    assert seen[-1][1] == MAX_SYSTEM_BOTS, "everyone is in by the end"
    steps = [b - a for (_, a), (_, b) in zip(seen, seen[1:])]
    assert max(steps) == 1, f"two or more walked in on the same beat: {seen}"

    # And the last one is genuinely late, not merely last.
    full_at = next(second for second, count in seen if count == MAX_SYSTEM_BOTS)
    assert full_at > BOT_ARRIVAL_WINDOW.total_seconds() * 0.6, \
        f"the room filled in {full_at}s, which is not a five-minute fill"
