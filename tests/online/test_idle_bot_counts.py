"""Two lobby tables show a different number of bots while nobody is there."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select

from online.catalogue import IDLE_BOT_COUNTS, Catalogue
from online.ledger import PlayLedger
from online.schema import system_players, table_seats, tenants, users
from online.seating import MAX_SYSTEM_BOTS, MIN_SYSTEM_BOTS, SeatingService

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def lobby(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(users).values(
                id="u2", telegram_user_id=2, display_name="B", acquisition_tenant_id="tenant"))
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(Catalogue(db_session_factory).seed_defaults())
    return SeatingService(db_session_factory, ledger), db_session_factory


async def _bots(session_factory, table_id):
    async with session_factory() as session:
        return len((await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == table_id,
                table_seats.c.occupant_kind == "system",
                table_seats.c.state == "seated")
        )).scalars().all())


async def _sit(session_factory, table_id, user_id, seat_no):
    """Put a person in a seat directly -- the queue is not what is under test."""
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id=f"{table_id}-{user_id}", table_id=table_id, seat_no=seat_no,
            occupant_kind="user", user_id=user_id, stack_units=4_000, state="seated"))
        await session.commit()


def test_the_two_named_tables_are_the_only_ones_that_differ():
    assert IDLE_BOT_COUNTS == {"low-b": 5, "mid-b": 6}


@pytest.mark.anyio
@pytest.mark.parametrize("table_id,expected", [("low-b", 5), ("mid-b", 6), ("micro-a", MAX_SYSTEM_BOTS)])
async def test_an_empty_table_shows_its_own_number(lobby, table_id, expected):
    seating, session_factory = lobby
    await seating.process_boundary(table_id, now=START)
    assert await _bots(session_factory, table_id) == expected


@pytest.mark.anyio
async def test_the_five_bot_table_is_full_once_you_join(lobby):
    """Five bots plus you is six. Nobody has to leave for that to happen.

    The first version clamped this to four the moment anyone sat down, so
    taking the one free seat made a bot leave and opened another -- the table
    could never actually be full, which is the entire point of it.
    """
    seating, session_factory = lobby
    await seating.process_boundary("low-b", now=START)
    assert await _bots(session_factory, "low-b") == 5

    await _sit(session_factory, "low-b", "u1", 5)  # the one seat no bot took
    await seating.process_boundary("low-b", now=START)
    assert await _bots(session_factory, "low-b") == 5, "a bot left a seat that was not needed"


@pytest.mark.anyio
async def test_a_full_table_gives_a_seat_back_when_somebody_sits_down(lobby):
    """Six bots is a game to watch, not a table you are locked out of."""
    seating, session_factory = lobby
    await seating.process_boundary("mid-b", now=START)
    assert await _bots(session_factory, "mid-b") == 6

    # A person takes seat 0 from the bot that was there.
    async with session_factory() as session:
        row = (await session.execute(
            select(table_seats).where(table_seats.c.table_id == "mid-b", table_seats.c.seat_no == 0)
        )).mappings().one()
        await session.execute(table_seats.delete().where(table_seats.c.id == row["id"]))
        await session.commit()
    await _sit(session_factory, "mid-b", "u1", 0)

    await seating.process_boundary("mid-b", now=START)
    assert await _bots(session_factory, "mid-b") == 5,         "one bot yields the seat -- and only one, because only one was needed"


@pytest.mark.anyio
async def test_a_second_person_costs_exactly_one_more_bot(lobby):
    seating, session_factory = lobby
    await seating.process_boundary("low-b", now=START)
    async with session_factory() as session:
        for seat_no in (0, 1):
            row = (await session.execute(
                select(table_seats).where(
                    table_seats.c.table_id == "low-b", table_seats.c.seat_no == seat_no)
            )).mappings().one()
            await session.execute(table_seats.delete().where(table_seats.c.id == row["id"]))
        await session.commit()
    await _sit(session_factory, "low-b", "u1", 0)
    await _sit(session_factory, "low-b", "u2", 1)

    await seating.process_boundary("low-b", now=START)
    assert await _bots(session_factory, "low-b") == MAX_SYSTEM_BOTS
    assert MIN_SYSTEM_BOTS < MAX_SYSTEM_BOTS < 5, "the whole point is that these are three tiers"
