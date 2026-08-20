"""Trimming the same bot to the same size twice must clear both overshoots."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select, update

from online.ledger import PlayLedger
from online.schema import (
    play_accounts,
    poker_tables,
    system_players,
    table_seats,
    tenants,
    users,
)
from online.seating import SeatingService


@pytest.fixture
def table(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
            await session.execute(insert(system_players).values(
                id="bot-1", name="N", difficulty="normal", active=True))
            # Bots only stay at a table that has somebody to play against.
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(table_seats).values(
                id="seat-human", table_id="t1", seat_no=5, occupant_kind="user",
                user_id="u1", stack_units=10_000, state="seated"))
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    return SeatingService(db_session_factory, ledger), ledger, db_session_factory


async def _escrow(session_factory, system_player_id):
    async with session_factory() as session:
        return (await session.execute(
            select(play_accounts.c.balance_units).where(
                play_accounts.c.owner_kind == "system",
                play_accounts.c.owner_id == system_player_id,
                play_accounts.c.account_kind == "escrow")
        )).scalar_one_or_none() or 0


async def _win_up_to(session_factory, ledger, amount, label):
    """Books and seat both move, the way a won pot moves them."""
    async with session_factory() as session:
        current = (await session.execute(
            select(table_seats.c.stack_units).where(table_seats.c.id == "seat-bot")
        )).scalar_one()
    await ledger.fund_system_seat("bot-1", "t1", amount - current, f"win:{label}")
    async with session_factory() as session:
        await session.execute(
            update(table_seats).where(table_seats.c.id == "seat-bot").values(stack_units=amount))
        await session.commit()


@pytest.mark.anyio
async def test_a_second_overshoot_to_the_same_size_is_not_swallowed(table):
    """The key was built from the stack being trimmed, so winning back to
    exactly the same number looked to the ledger like the trim already posted.
    The seat was cut anyway, and the difference stayed in escrow for good."""
    seating, ledger, session_factory = table
    ceiling = 100 * 100  # big_blind_units * max_buy_in_bb

    await ledger.fund_system_seat("bot-1", "t1", ceiling, "seed")
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="seat-bot", table_id="t1", seat_no=0, occupant_kind="system",
            system_player_id="bot-1", stack_units=ceiling, state="seated"))
        await session.commit()

    for attempt in range(2):
        await _win_up_to(session_factory, ledger, ceiling + 2_000, attempt)
        await seating.process_boundary("t1", now=datetime(2026, 1, 1, tzinfo=timezone.utc))

        async with session_factory() as session:
            stack = (await session.execute(
                select(table_seats.c.stack_units).where(table_seats.c.id == "seat-bot")
            )).scalar_one()
        assert stack == ceiling, "the seat is trimmed to the table's ceiling"
        assert await _escrow(session_factory, "bot-1") == ceiling, \
            "and the books follow it -- every time, not just the first"
