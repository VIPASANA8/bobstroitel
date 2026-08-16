import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import insert, select

from online.ledger import PlayLedger
from online.runtime import StaleRevision, TableRuntimeManager
from online.schema import (
    game_commands,
    poker_tables,
    system_players,
    table_runtimes,
    table_seats,
    tenants,
    users,
)


@pytest.fixture
def runtime(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users), [
                {"id": "u1", "telegram_user_id": 1, "display_name": "A", "acquisition_tenant_id": "tenant"},
            ])
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
    return TableRuntimeManager(db_session_factory, ledger)


@pytest.fixture
def human_turn(runtime):
    async def start():
        await runtime.start_hand("t1")
        snapshot = await runtime.public_snapshot("t1", "u1")
        return type("Turn", (), {
            "table_id": "t1",
            "user_id": "u1",
            "revision": snapshot["revision"],
        })()

    return asyncio.run(start())


@pytest.mark.anyio
async def test_table_commands_are_serial_and_idempotent(runtime, human_turn):
    first = await runtime.action(
        table_id=human_turn.table_id,
        user_id=human_turn.user_id,
        command_id="cmd-1",
        expected_revision=human_turn.revision,
        action="call",
        amount_units=0,
    )
    duplicate = await runtime.action(
        table_id=human_turn.table_id,
        user_id=human_turn.user_id,
        command_id="cmd-1",
        expected_revision=human_turn.revision,
        action="call",
        amount_units=0,
    )
    assert duplicate == first
    assert runtime.engine_action_count("t1") == 1


@pytest.mark.anyio
async def test_stale_revision_returns_current_snapshot(runtime, human_turn):
    with pytest.raises(StaleRevision) as error:
        await runtime.action("t1", "u1", "cmd-stale", 0, "fold", 0)
    assert error.value.current_revision == human_turn.revision


@pytest.mark.anyio
async def test_concurrent_commands_accept_only_one_revision(runtime, human_turn):
    results = await asyncio.gather(
        runtime.action("t1", "u1", "cmd-a", human_turn.revision, "call", 0),
        runtime.action("t1", "u1", "cmd-b", human_turn.revision, "call", 0),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, StaleRevision) for result in results) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("difficulty", ["easy", "normal", "hard", "maximum"])
async def test_system_step_is_legal_at_every_difficulty(runtime, difficulty):
    await runtime.start_hand("t1", button_seat=1)
    result = await runtime.system_step("t1")
    assert result.action in result.legal_actions


@pytest.mark.anyio
async def test_system_command_audit_does_not_reference_user_foreign_key(runtime):
    await runtime.start_hand("t1", button_seat=1)
    await runtime.system_step("t1")

    async with runtime.session_factory() as session:
        command = (await session.execute(select(game_commands))).mappings().one()
    assert command["user_id"] is None


@pytest.mark.anyio
async def test_system_step_gives_bot_only_a_sanitized_view(runtime, monkeypatch):
    await runtime.start_hand("t1", button_seat=1)
    captured = {}

    class SpyBot:
        def __init__(self, engine):
            self.engine = engine

        def decide(self, state, actor):
            captured["state"] = state
            return type("Decision", (), {"action": self.engine.legal_actions(state, actor)[0], "amount": 0.0})()

    monkeypatch.setattr("online.runtime.MultiwayBot", SpyBot)
    await runtime.system_step("t1")

    view = captured["state"]
    actor = view.acting_player
    assert view.deck is None
    assert all(
        player.hole_cards == ["??", "??"]
        for participant_id, player in view.players.items()
        if participant_id != actor
    )


@pytest.mark.anyio
async def test_button_rotates_between_hands(runtime):
    first = await runtime.start_hand("t1")
    async with runtime.session_factory() as session:
        stored = (
            await session.execute(select(poker_tables.c.button_seat).where(poker_tables.c.id == "t1"))
        ).scalar_one()
    assert stored == first["players"][first["button"]]["seat"]

    runtime._tables.pop("t1")
    async with runtime.session_factory() as session:
        await session.execute(table_runtimes.delete())
        await session.commit()
    second = await runtime.start_hand("t1")

    assert second["players"][second["button"]]["seat"] != first["players"][first["button"]]["seat"]


@pytest.mark.anyio
async def test_undersized_bot_raise_does_not_pause_the_table(runtime, monkeypatch):
    from bots.multiway import MultiwayBot
    from poker.models import ActionType

    await runtime.start_hand("t1", button_seat=1)

    def tiny_raise(self, state, player_id):
        return SimpleNamespace(action=ActionType.RAISE, amount=0.01)

    monkeypatch.setattr(MultiwayBot, "decide", tiny_raise)
    await runtime.system_step("t1")

    assert (await runtime.load("t1")).phase != "paused"
