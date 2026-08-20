"""Walking out should not cost a hand you are not even in."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from online.catalogue import Catalogue
from online.coordinator import OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, table_seats, tenants, users
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
    return coordinator, runtime, seating, clock, db_session_factory


async def _seat_state(session_factory):
    async with session_factory() as session:
        return (await session.execute(
            select(table_seats.c.state).where(table_seats.c.user_id == "u1")
        )).scalar_one_or_none()


@pytest.mark.anyio
async def test_somebody_not_in_the_running_hand_leaves_at_once(table):
    """Sit down, change your mind, stand back up -- there is no hand of yours
    to finish, so the seat should not wait for one."""
    coordinator, runtime, seating, clock, session_factory = table

    await coordinator.tick()  # bots fill and start a hand
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="latecomer", table_id="t1", seat_no=5, occupant_kind="user",
            user_id="u1", stack_units=4_000, state="seated"))
        await session.commit()
    await seating.ledger.reserve_buy_in("u1", "t1", 4_000, "buy:u1")

    loaded = runtime._tables["t1"]
    assert loaded.phase == "active" and "u1" not in loaded.state.players, \
        "they sat down after the cards were dealt"

    in_hand = await runtime.mark_leaving("t1", "u1")
    await seating.request_leave("u1", "t1", immediate=not in_hand)

    assert in_hand is False
    assert await _seat_state(session_factory) is None, "the seat went back straight away"
    assert await seating.ledger.available_units("u1") == 100_000, "and so did the stack"


@pytest.mark.anyio
async def test_a_player_in_the_hand_is_folded_the_moment_it_is_their_turn(table):
    """They still have to wait for the hand to settle, but not for their own
    clock -- thirty seconds on every street they are still owed is what made
    walking out take the best part of a minute."""
    coordinator, runtime, seating, clock, session_factory = table

    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="player", table_id="t1", seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=10_000, state="seated"))
        await session.commit()
    await seating.ledger.reserve_buy_in("u1", "t1", 10_000, "buy:u1")

    # Ready up rather than letting the AFK deadline pass: a player sat out for
    # being slow is not in the hand, and this test is about one who is.
    for _ in range(30):
        await coordinator.tick()
        await runtime.toggle_ready("t1", 0)
        if runtime.ready_seats("t1") >= {0}:
            break
    for _ in range(30):
        clock.advance(6)
        await coordinator.tick()
        loaded = runtime._tables.get("t1")
        if loaded and loaded.phase == "active" and "u1" in loaded.state.players:
            break
    else:
        pytest.fail("no hand dealt this player in")

    assert await runtime.mark_leaving("t1", "u1") is True
    assert runtime.is_leaving("t1", "u1")

    # The engine still reaches them, but the hand must not stop there. Five
    # simulated seconds a tick: on the old path their thirty-second clock held
    # it for six ticks or more on every street they were still owed.
    stalled = longest = 0
    for _ in range(400):
        loaded = runtime._tables.get("t1")
        if loaded is None or loaded.phase != "active":
            break
        stalled = stalled + 1 if loaded.state.acting_player == "u1" else 0
        longest = max(longest, stalled)
        clock.advance(5)
        await coordinator.tick()
    else:
        pytest.fail("the hand never finished")

    assert longest <= 2,         f"the hand waited {longest} ticks on a player who had already left"


@pytest.mark.anyio
async def test_the_note_does_not_outlive_the_hand(table):
    coordinator, runtime, seating, clock, session_factory = table

    await coordinator.tick()
    runtime._tables["t1"].leaving_participants.add("someone")
    await runtime.prepare_next_hand("t1")
    assert runtime._tables["t1"].leaving_participants == set()


def test_the_page_does_not_wait_on_the_leave_request():
    """Folding a hand out took the server 3.4 seconds on the live site, and
    the page sat on it before navigating. Nothing in the answer is needed."""
    from pathlib import Path

    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    table = Path("static/online-table.js").read_text(encoding="utf-8")

    assert "leaveInBackground" in transport
    assert "keepalive: true" in transport, "or the navigation cancels it"

    body = table[table.index("async function leaveTable()"):]
    body = body[:body.index("\n  }")]
    assert "leaveInBackground()" in body
    assert "await window.Poker8Transport.leave()" not in body
