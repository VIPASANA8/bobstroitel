import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from online.ledger import PlayLedger
from online.scheduler import TableScheduler
from online.schema import poker_tables, system_players, table_seats, tenants, users
from online.runtime import TableRuntimeManager


class FakeClock:
    def __init__(self):
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def scheduler(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
            ))
            await session.execute(insert(system_players).values(
                id="bot-1", name="Room Player", difficulty="normal", active=True,
            ))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.execute(insert(table_seats), [
                {"id": "seat-u1", "table_id": "t1", "seat_no": 0, "occupant_kind": "user",
                 "user_id": "u1", "system_player_id": None, "stack_units": 100_000, "state": "seated"},
                {"id": "seat-bot", "table_id": "t1", "seat_no": 1, "occupant_kind": "system",
                 "user_id": None, "system_player_id": "bot-1", "stack_units": 100_000, "state": "seated"},
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(ledger.grant("u1", 100_000, "grant:u1"))
    clock = FakeClock()
    manager = TableRuntimeManager(db_session_factory, ledger)
    return TableScheduler(manager, clock=clock)


@pytest.mark.anyio
async def test_human_turn_deadline_is_thirty_seconds(scheduler):
    await scheduler.start_hand("t1")
    assert scheduler.action_deadline == scheduler.now_plus(seconds=30)


@pytest.mark.anyio
async def test_timeout_checks_when_check_is_legal(scheduler):
    await scheduler.start_hand("t1")
    state = scheduler.runtime._tables["t1"].state
    state.current_bet = state.players["u1"].street_invested
    state.acting_player = "u1"
    state.pending_actions = {"u1"}
    await scheduler.advance(30)
    assert scheduler.last_action == "check"


@pytest.mark.anyio
async def test_repeated_timeout_callback_applies_once(scheduler):
    await scheduler.start_hand("t1")
    await scheduler.fire_timeout("t1")
    await scheduler.fire_timeout("t1")
    assert scheduler.action_count == 1


@pytest.mark.anyio
async def test_result_clears_at_four_and_deals_at_seven(scheduler):
    await scheduler.start_hand("t1")
    await scheduler.mark_terminal("t1")
    await scheduler.advance(3.99)
    assert scheduler.phases["t1"] == "result"
    await scheduler.advance(0.01)
    assert scheduler.phases["t1"] == "countdown"
    assert scheduler.public_state_has_cards is False
    await scheduler.advance(3.0)
    assert scheduler.new_hand_count == 1
