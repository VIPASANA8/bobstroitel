import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from online.catalogue import Catalogue
from online.coordinator import OnlineCoordinator
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, table_seats, tenants
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
async def test_bot_moves_are_paced_not_instant(coordinator):
    """Coordinator.tick() used to call system_step unconditionally, so a bot
    acted on every ~250ms poll -- a uniform, obviously-robotic beat. A bot
    move must now wait out its think-time delay before the next one lands."""
    await coordinator.tick()  # seats bots, starts the hand
    await coordinator.tick()  # first bot decision: its own gate was still None
    revision_after_first_move = coordinator.runtime._tables["t1"].revision
    assert revision_after_first_move >= 1

    # Ticking again at the *same instant* must not produce a second bot move.
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].revision == revision_after_first_move

    # The slowest possible band (max jitter * hardest-difficulty * river factor)
    # is under 4s; 5s comfortably clears it regardless of which street/bot acted.
    coordinator.runtime.clock.advance(5)
    await coordinator.tick()
    assert coordinator.runtime._tables["t1"].revision > revision_after_first_move
