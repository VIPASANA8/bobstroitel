"""A hand with nobody but bots in it is written down for no reader.

On the live database 908,238 of 908,696 recorded actions were bots, against 458
by people -- and nothing consults a bot's history. Not the history service, not
the profile, and not the bots, which do not model each other at all.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, insert, select

from online.catalogue import Catalogue
from online.coordinator import OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import (
    game_commands,
    hand_actions,
    hand_players,
    hands,
    poker_tables,
    system_players,
    table_seats,
    tenants,
    users,
)
from online.seating import SeatingService


class _Clock:
    def __init__(self, start): self.current = start
    def __call__(self): return self.current
    def advance(self, seconds): self.current += timedelta(seconds=seconds)


@pytest.fixture
def table(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"B{i}", "difficulty": "normal", "active": True}
                for i in range(1, 7)
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(ledger.grant("u1", 100_000, "grant:u1"))
    clock = _Clock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    runtime = TableRuntimeManager(db_session_factory, ledger, now=clock)
    seating = SeatingService(db_session_factory, ledger)
    coordinator = OnlineCoordinator(runtime, seating, Catalogue(db_session_factory), interval_seconds=0)
    return coordinator, clock, db_session_factory, ledger


async def _count(session_factory, table):
    async with session_factory() as session:
        return (await session.execute(select(func.count()).select_from(table))).scalar_one()


async def _play(coordinator, clock, rounds=60):
    for _ in range(rounds):
        clock.advance(13)
        await coordinator.tick()
        await asyncio.sleep(0)


@pytest.mark.anyio
async def test_a_table_of_bots_writes_no_history(table):
    coordinator, clock, session_factory, _ = table

    await _play(coordinator, clock)

    assert await _count(session_factory, hands) == 0
    assert await _count(session_factory, hand_players) == 0
    assert await _count(session_factory, hand_actions) == 0
    assert await _count(session_factory, game_commands) == 0


@pytest.mark.anyio
async def test_a_bot_stops_collecting_wins_off_other_bots(table):
    """331,757 hands and 74,406 wins had piled up across 36 of them, counting
    nothing and read by nothing."""
    coordinator, clock, session_factory, _ = table

    await _play(coordinator, clock)

    async with session_factory() as session:
        totals = (await session.execute(
            select(func.sum(system_players.c.hands_played), func.sum(system_players.c.wins))
        )).one()
    assert totals == (0, 0), totals


@pytest.mark.anyio
async def test_a_hand_with_a_person_in_it_is_recorded_whole(table):
    """Their opponents' moves are what makes the record worth having."""
    coordinator, clock, session_factory, ledger = table

    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="human", table_id="t1", seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=10_000, state="seated"))
        await session.commit()
    await ledger.reserve_buy_in("u1", "t1", 10_000, "buy:u1")

    # Ready up rather than letting the AFK deadline pass: a player sat out for
    # being slow is not in the hand, and then there is correctly nothing to
    # record. This test is about one who is.
    # Asserted every step rather than toggled once: starting a hand clears the
    # ready cycle, and a toggle that lands after that turns readiness back off.
    runtime = coordinator.runtime
    for _ in range(60):
        runtime._ready_seats.setdefault("t1", set()).add(0)
        clock.advance(6)
        await coordinator.tick()
        await asyncio.sleep(0)
        loaded = runtime._tables.get("t1")
        if loaded and "u1" in loaded.state.players:
            break
    else:
        pytest.fail("no hand dealt this player in")

    for _ in range(40):
        runtime._ready_seats.setdefault("t1", set()).add(0)
        clock.advance(6)
        await coordinator.tick()
        await asyncio.sleep(0)

    assert await _count(session_factory, hands) > 0, "the hand went unrecorded"
    async with session_factory() as session:
        bots_in_record = (await session.execute(
            select(func.count()).select_from(hand_players)
            .where(hand_players.c.system_player_id.is_not(None))
        )).scalar_one()
        human_hands = (await session.execute(
            select(users.c.hands_played).where(users.c.id == "u1")
        )).scalar_one()
    assert bots_in_record > 0, "the opponents were left out of the record"
    assert human_hands > 0, "the person's own tally still counts"
