import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from online.catalogue import Catalogue
from online.coordinator import OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, tenants
from online.seating import MAX_SYSTEM_BOTS, SeatingService


class _ControllableClock:
    """A settable clock, so a tick-loop can fast-forward past a bot's paced
    think-time delay (online/runtime.py's bot_think_delay) without an actual
    real-time sleep -- real time would make these tests slow and flaky."""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def coordinator(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"Bot {i}", "difficulty": "normal", "active": True}
                for i in range(1, 7)
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    clock = _ControllableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    runtime = TableRuntimeManager(db_session_factory, ledger, now=clock)
    seating = SeatingService(db_session_factory, ledger)
    return OnlineCoordinator(runtime, seating, Catalogue(db_session_factory), interval_seconds=0)


@pytest.mark.anyio
async def test_coordinator_fills_table_and_starts_bot_hand(coordinator):
    await coordinator.tick()
    loaded = await coordinator.runtime.load("t1")

    assert loaded is not None
    assert loaded.phase == "active"
    # The table seats a bounded number of bots and leaves the rest for players.
    assert 2 <= len(loaded.state.players) <= 6
    assert sum(1 for player in loaded.state.players.values() if player.is_bot) <= MAX_SYSTEM_BOTS


@pytest.mark.anyio
async def test_coordinator_advances_result_to_next_hand(coordinator):
    await coordinator.tick()
    for _ in range(300):
        loaded = coordinator.runtime._tables["t1"]
        if loaded.state.terminal:
            break
        # Clears the paced think-time gate every iteration (see
        # bot_think_delay) so this exercises hand progression, not pacing --
        # pacing itself has its own dedicated test below.
        coordinator.runtime.clock.advance(5)
        await coordinator.tick()
    else:
        pytest.fail("bot hand did not reach terminal state")

    await coordinator.tick()

    assert coordinator.runtime._tables["t1"].phase == "result"
    loaded = coordinator.runtime._tables["t1"]
    loaded.result_clear_at = coordinator.now()
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].phase == "countdown"
    loaded.next_hand_at = coordinator.now()
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].phase == "active"


@pytest.mark.anyio
async def test_coordinator_notifies_on_every_state_change(coordinator):
    """Bot moves and hand boundaries only reach viewers through this callback."""
    seen: list[str] = []
    coordinator.on_change = lambda table_id: _record(seen, table_id)

    await coordinator.tick()
    assert seen == ["t1"]

    before = coordinator.runtime._tables["t1"].revision
    for _ in range(20):
        coordinator.runtime.clock.advance(5)
        await coordinator.tick()
        if coordinator.runtime._tables["t1"].revision != before:
            break
    else:
        pytest.fail("no bot action advanced the table")

    assert len(seen) > 1


@pytest.mark.anyio
async def test_coordinator_stays_quiet_when_nothing_changes(coordinator):
    seen: list[str] = []
    await coordinator.tick()
    coordinator.runtime._tables["t1"].state.acting_player = None
    coordinator.on_change = lambda table_id: _record(seen, table_id)

    await coordinator.tick()

    assert seen == []


async def _record(seen: list[str], table_id: str) -> None:
    seen.append(table_id)


@pytest.mark.anyio
async def test_coordinator_recovers_a_paused_table_instead_of_leaving_it_stuck(coordinator):
    await coordinator.tick()
    loaded = coordinator.runtime._tables["t1"]
    await coordinator.runtime._pause_after_failure("t1", loaded, "synthetic failure for the test")
    assert (await coordinator.runtime.load("t1")).phase == "paused"

    await coordinator.tick()

    assert (await coordinator.runtime.load("t1")).phase != "paused"
    # The table must actually resume, not just stop being marked "paused".
    for _ in range(5):
        await coordinator.tick()
    assert coordinator.runtime._tables["t1"].phase in {"active", "result", "countdown", "waiting"}


@pytest.mark.anyio
async def test_a_countdown_with_no_timer_deals_instead_of_stalling_forever(coordinator):
    """A countdown that lost its next_hand_at was a permanent dead end.

    Nothing else advances that phase, so the table never dealt again -- and
    because the next hand is also what runs process_boundary, it stopped
    picking up seat and bot-count changes too. Found live on mid-a after the
    host was hard-killed mid-transition: the row survived as countdown with a
    NULL timer and sat there.

    The result phase one block above already re-settles itself when its own
    timestamps are missing; this is the same guard on the phase that follows.
    """
    await coordinator.tick()
    loaded = coordinator.runtime._tables["t1"]
    loaded.phase = "countdown"
    loaded.next_hand_at = None

    await coordinator.tick()

    assert coordinator.runtime._tables["t1"].phase != "countdown", (
        "a countdown with no timer never leaves it"
    )


@pytest.mark.anyio
async def test_bot_moves_are_paced_not_instant(coordinator):
    """Coordinator.tick() used to call system_step unconditionally, so a bot
    acted on every ~250ms poll -- a uniform, obviously-robotic beat. A move
    waits out its think time, and the clock is the only thing that releases it.

    A move is a task now, so settling one takes several ticks: one to start it,
    one for it to finish, one to collect it and arm the next delay."""
    async def settle():
        for _ in range(6):
            await coordinator.tick()
            await asyncio.sleep(0)

    await coordinator.tick()  # seats bots, starts the hand
    await settle()
    revision_after_first_move = coordinator.runtime._tables["t1"].revision
    assert revision_after_first_move >= 1

    # However many times it is polled at the *same instant*, nothing more moves.
    await settle()
    assert coordinator.runtime._tables["t1"].revision == revision_after_first_move

    # The slowest possible band (max jitter * hardest difficulty * river factor,
    # and a tank on top) is under the cap; 13s clears it whichever bot acted.
    coordinator.runtime.clock.advance(13)
    await settle()
    assert coordinator.runtime._tables["t1"].revision > revision_after_first_move


@pytest.mark.anyio
async def test_a_thinking_bot_does_not_hold_up_the_tick(coordinator):
    """The whole point of the move being a task. Awaiting it inside the tick
    made the tick as long as the thinking -- 571ms measured on the live site
    against a 250ms interval, because a Monte Carlo estimate takes up to 268ms
    and several tables ask at once.

    A move that will never finish stands in for a slow one: the tick has to
    come back anyway, and leave it alone to finish on its own."""
    await coordinator.tick()  # seats bots, starts the hand

    still_thinking = asyncio.create_task(asyncio.sleep(30))
    coordinator._bot_moves["t1"] = still_thinking
    try:
        started = time.perf_counter()
        await coordinator.tick()
        elapsed = time.perf_counter() - started

        assert elapsed < 1.0, f"the tick waited {elapsed:.1f}s for a bot to think"
        assert coordinator._bot_moves.get("t1") is still_thinking, "and left it running"
    finally:
        still_thinking.cancel()
        coordinator._bot_moves.pop("t1", None)


@pytest.mark.anyio
async def test_a_bot_move_tells_viewers_itself(coordinator):
    """The tick that starts it sees no change and the tick that collects it
    sees a state that already changed, so neither would broadcast."""
    seen: list[str] = []
    coordinator.on_change = lambda table_id: _record(seen, table_id)

    await coordinator.tick()
    for _ in range(10):
        coordinator.runtime.clock.advance(5)
        await coordinator.tick()
        await asyncio.sleep(0)

    assert len(seen) > 1, "moves after the first were never announced"
