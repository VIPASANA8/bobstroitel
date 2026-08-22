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


def test_record_ready_outcome_evicts_only_on_the_third_miss_running(two_humans):
    """PokerStars gives an AFK player 15 minutes or two full orbits of missed
    blinds before it acts at all -- nothing close to one 30s sit-out. This is
    the harder consequence, and it needs several misses running, not one."""
    coordinator, _clock = two_humans
    runtime = coordinator.runtime
    for expected_evict, call in ((set(), 1), (set(), 2), ({1}, 3)):
        evict = runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})
        assert evict == expected_evict, f"miss #{call}"


def test_readying_up_once_resets_the_streak(two_humans):
    coordinator, _clock = two_humans
    runtime = coordinator.runtime
    runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})
    runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})
    # Ready this time -- not in sit_out at all.
    evict = runtime.record_ready_outcome("t1", {0, 1}, sit_out=set())
    assert evict == set()
    # Two more misses land on a fresh count, not the two from before the reset.
    assert runtime.record_ready_outcome("t1", {0, 1}, sit_out={1}) == set()
    assert runtime.record_ready_outcome("t1", {0, 1}, sit_out={1}) == set()
    assert runtime.record_ready_outcome("t1", {0, 1}, sit_out={1}) == {1}


def test_standing_up_drops_the_streak_not_just_the_seat(two_humans):
    """A seat that is no longer occupied has nothing left to track -- someone
    new sitting there later starts at zero, not wherever the last person
    left off."""
    coordinator, _clock = two_humans
    runtime = coordinator.runtime
    runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})
    runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})
    # Seat 1 is gone from the table entirely on this render.
    runtime.record_ready_outcome("t1", {0}, sit_out=set())
    # Seat 1 is occupied again (a new player) and immediately misses once --
    # if the old streak had survived, this alone would already evict them.
    assert runtime.record_ready_outcome("t1", {0, 1}, sit_out={1}) == set()


@pytest.mark.anyio
async def test_an_afk_human_is_evicted_after_three_hands_running(two_humans):
    """Three consecutive misses -- not one -- convert the seat to spectator
    and hand the stack back, the same pipeline as clicking "leave". Seeding
    the streak to one below the threshold exercises the real coordinator path
    for the crossing itself without needing three full hands played out."""
    coordinator, clock = two_humans
    ledger = coordinator.seating.ledger
    start = await ledger.available_units("u2")
    # The fixture seats u2 by inserting the row directly, which -- unlike the
    # real seating.ready() path -- never moves the stack into the table's
    # escrow, and a freshly created test user has nothing in their wallet to
    # move it from either. Funding both the way ready() would is what makes
    # the eviction's stack return below a real, checkable transfer rather
    # than a transfer from accounts that were never credited.
    await ledger.grant("u2", 100_000, "test-fund-wallet-u2")
    await ledger.reserve_buy_in("u2", "t1", 100_000, "test-fund-seat-u2")

    coordinator.runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})
    coordinator.runtime.record_ready_outcome("t1", {0, 1}, sit_out={1})

    await coordinator.runtime.toggle_ready("t1", 0)  # only seat 0 readies up
    await coordinator.tick()  # arms the 30s AFK deadline for seat 1
    clock.advance(31)
    await coordinator.tick()  # the third miss -- crosses AFK_EVICT_STREAK

    loaded = coordinator.runtime._tables["t1"]
    assert loaded.phase == "active"
    assert "u1" in loaded.state.players
    assert "u2" not in loaded.state.players

    async with coordinator.runtime.session_factory() as session:
        row = (await session.execute(
            select(table_seats.c.state, table_seats.c.occupant_kind, table_seats.c.stack_units)
            .where(table_seats.c.id == "seat-u2")
        )).one()
    assert row.state == "empty"
    assert row.occupant_kind == "empty"
    assert row.stack_units == 0
    # Granted, spent into escrow, then returned -- back to the grant, not zero.
    assert await ledger.available_units("u2") == start + 100_000


@pytest.mark.anyio
async def test_a_lobby_table_stays_populated_with_nobody_at_it(two_humans):
    """The six lobby tables are the shop window, and Quick Play exists to drop
    you into a game already running -- so they keep their bots whether or not
    anyone is there. A player's room is the opposite; test_bot_arrivals covers
    that side. What made an always-populated table dangerous was a bot's stack
    growing without bound, and the ceiling in _cap_system_stacks fixed that."""
    coordinator, clock = two_humans
    async with coordinator.runtime.session_factory() as session:
        await session.execute(delete(table_seats).where(table_seats.c.table_id == "t1"))
        await session.commit()

    await coordinator.tick()  # seats bots via process_boundary
    await coordinator.tick()  # nothing to wait on, so the hand starts

    async with coordinator.runtime.session_factory() as session:
        occupied = (await session.execute(
            select(table_seats.c.id).where(
                table_seats.c.table_id == "t1", table_seats.c.state != "empty")
        )).scalars().all()
    assert occupied, "the shop window is not left empty"
    loaded = coordinator.runtime._tables.get("t1")
    assert loaded is not None and loaded.phase == "active"


@pytest.mark.anyio
async def test_the_table_does_not_ask_to_deal_to_one_player(two_humans):
    """The seat count included the very people about to be sat out for being
    slow. With one bot arrived and the only human asleep, start_hand was asked
    to deal to a single player, refused, and the tick logged a traceback four
    times a second until somebody else sat down -- 139 of them in four minutes
    on the live site."""
    coordinator, clock = two_humans

    # One human, one bot: enough seats to pass the range check, not enough
    # players once the human misses the deadline.
    async with coordinator.runtime.session_factory() as session:
        await session.execute(delete(table_seats).where(table_seats.c.id == "seat-u2"))
        await session.execute(insert(table_seats).values(
            id="lone-bot", table_id="t1", seat_no=4, occupant_kind="system",
            system_player_id="bot-1", stack_units=10_000, state="seated"))
        await session.commit()

    should_start, _, _ = await coordinator._may_start_hand("t1", coordinator.now())
    assert should_start is False

    clock.advance(31)
    should_start, sit_out, _ = await coordinator._may_start_hand("t1", coordinator.now())
    assert should_start is False, f"asked to deal to {2 - len(sit_out)} player(s)"

    # And it starts as soon as a second player is actually there.
    async with coordinator.runtime.session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="second-bot", table_id="t1", seat_no=5, occupant_kind="system",
            system_player_id="bot-2", stack_units=10_000, state="seated"))
        await session.commit()
    clock.advance(31)
    should_start, _, _ = await coordinator._may_start_hand("t1", coordinator.now())
    assert should_start is True
