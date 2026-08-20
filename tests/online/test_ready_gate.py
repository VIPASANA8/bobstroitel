import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, insert, select

from online.catalogue import Catalogue
from online.coordinator import OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, table_seats, tenants, users
from online.seating import SeatingService


class _ControllableClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def two_humans(db_session_factory):
    """Two seated humans, no bots pre-seeded -- process_boundary will still
    top the table up on the first tick, but neither of those extra seats
    counts toward the ready gate (bots are implicitly ready)."""

    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users), [
                {"id": "u1", "telegram_user_id": 1, "display_name": "A", "acquisition_tenant_id": "tenant"},
                {"id": "u2", "telegram_user_id": 2, "display_name": "B", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"Bot {i}", "difficulty": "normal", "active": True}
                for i in range(1, 7)
            ])
            await session.execute(insert(table_seats), [
                {"id": "seat-u1", "table_id": "t1", "seat_no": 0, "occupant_kind": "user",
                 "user_id": "u1", "stack_units": 100_000, "state": "seated"},
                {"id": "seat-u2", "table_id": "t1", "seat_no": 1, "occupant_kind": "user",
                 "user_id": "u2", "stack_units": 100_000, "state": "seated"},
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    clock = _ControllableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    runtime = TableRuntimeManager(db_session_factory, ledger, now=clock)
    seating = SeatingService(db_session_factory, ledger)
    coordinator = OnlineCoordinator(runtime, seating, Catalogue(db_session_factory), interval_seconds=0)
    return coordinator, clock


@pytest.mark.anyio
async def test_hand_waits_for_every_seated_human_to_ready_up(two_humans):
    coordinator, clock = two_humans
    for _ in range(10):
        await coordinator.tick()
    assert coordinator.runtime._tables.get("t1") is None or coordinator.runtime._tables["t1"].phase != "active"

    await coordinator.runtime.toggle_ready("t1", 0)
    await coordinator.tick()
    assert coordinator.runtime._tables.get("t1") is None or coordinator.runtime._tables["t1"].phase != "active"

    await coordinator.runtime.toggle_ready("t1", 1)
    await coordinator.tick()  # both humans in, but the table's bots confirm on their own beat
    assert coordinator.runtime._tables.get("t1") is None or coordinator.runtime._tables["t1"].phase != "active"

    clock.advance(6)
    await coordinator.tick()  # bots have now confirmed: arms the 5s pre-deal beat, doesn't deal yet
    assert coordinator.runtime._tables.get("t1") is None or coordinator.runtime._tables["t1"].phase != "active"

    clock.advance(6)
    await coordinator.tick()
    loaded = coordinator.runtime._tables["t1"]
    assert loaded.phase == "active"
    assert {"u1", "u2"}.issubset(loaded.state.players)


@pytest.mark.anyio
async def test_readiness_resets_once_the_hand_actually_starts(two_humans):
    coordinator, clock = two_humans
    await coordinator.runtime.toggle_ready("t1", 0)
    await coordinator.runtime.toggle_ready("t1", 1)
    await coordinator.tick()
    clock.advance(6)     # the bots' own ready beats land
    await coordinator.tick()
    clock.advance(6)     # then the 5s pre-deal beat
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].phase == "active"

    # Cleared for everyone, bots included -- their slots are re-rolled next hand.
    assert coordinator.runtime.ready_seats("t1") == set()
    assert coordinator.runtime.ready_deadline("t1") is None
    assert coordinator.runtime.hand_starts_at("t1") is None


@pytest.mark.anyio
async def test_an_afk_human_is_sat_out_after_the_deadline_not_evicted(two_humans):
    """The player who never clicked ready must still hold their seat and
    stack afterwards -- only excluded from this one hand, per the AFK
    timeout design note in coordinator.py's _may_start_hand."""
    coordinator, clock = two_humans
    await coordinator.runtime.toggle_ready("t1", 0)  # only seat 0 readies up
    await coordinator.tick()  # arms the 30s AFK deadline for seat 1

    clock.advance(31)
    await coordinator.tick()

    loaded = coordinator.runtime._tables["t1"]
    assert loaded.phase == "active"
    assert "u1" in loaded.state.players
    assert "u2" not in loaded.state.players  # sat out of this hand

    async with coordinator.runtime.session_factory() as session:
        row = (await session.execute(
            select(table_seats.c.state, table_seats.c.stack_units).where(table_seats.c.id == "seat-u2")
        )).one()
    assert row.state == "seated"
    assert row.stack_units == 100_000


@pytest.mark.anyio
async def test_a_table_with_nobody_at_it_seats_no_bots_and_deals_nothing(two_humans):
    """Bots are there to give a person opponents. With nobody to give them to
    they used to deal to each other around the clock, which is how one of them
    piled up a stack in the millions -- and why a player who had just opened a
    room walked into a hand already under way instead of their own table."""
    coordinator, clock = two_humans
    async with coordinator.runtime.session_factory() as session:
        await session.execute(delete(table_seats).where(table_seats.c.table_id == "t1"))
        await session.commit()

    for _ in range(5):
        clock.advance(60)
        await coordinator.tick()

    async with coordinator.runtime.session_factory() as session:
        occupied = (await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == "t1", table_seats.c.state != "empty")
        )).scalars().all()
    assert occupied == [], "no bot sat down at an empty table"
    loaded = coordinator.runtime._tables.get("t1")
    assert loaded is None or loaded.phase != "active", "and no hand was dealt"
