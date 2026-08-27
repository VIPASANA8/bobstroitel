import asyncio
from dataclasses import dataclass

import pytest
from sqlalchemy import insert

from online.history import HandRecord, HandParticipantRecord, HistoryService
from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import poker_tables, system_players, table_seats, tenants, users


@dataclass
class CompletedHand:
    table_id: str
    hand_id: str
    starting_total_units: int


@pytest.fixture
def settlement_context(db_session_factory):
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
    asyncio.run(ledger.reserve_buy_in("u1", "t1", 100_000, "buyin:u1:t1"))
    asyncio.run(ledger.fund_system_seat("bot-1", "t1", 100_000, "system:t1:bot-1"))
    return TableRuntimeManager(db_session_factory, ledger), ledger


@pytest.mark.anyio
async def test_terminal_hand_posts_one_balanced_settlement(settlement_context):
    runtime, ledger = settlement_context
    await runtime.start_hand("t1")
    snapshot = await runtime.public_snapshot("t1", "u1")
    await runtime.action("t1", "u1", "fold", snapshot["revision"], "fold", 0)
    completed = CompletedHand("t1", runtime._tables["t1"].state.hand_id, 200_000)

    first = await runtime.finish_and_settle(completed.table_id)
    again = await runtime.finish_and_settle(completed.table_id)

    assert again.idempotency_key == f"settlement:{completed.hand_id}"
    assert first.transaction_id == again.transaction_id
    assert sum(await ledger.escrow_balances(completed.table_id)) == completed.starting_total_units
    history = await HistoryService(runtime.session_factory).last_hands("u1")
    own = next(player for player in history[0]["players"] if player["participant_id"] == "u1")
    assert len(own["hole_cards"]) == 2


@pytest.mark.anyio
async def test_seated_user_can_play_the_next_hand_without_double_payout(settlement_context):
    runtime, ledger = settlement_context
    await runtime.start_hand("t1")

    while not runtime._tables["t1"].state.terminal:
        state = runtime._tables["t1"].state
        actor = state.acting_player
        if actor == "u1":
            snapshot = await runtime.public_snapshot("t1", "u1")
            # The button rotates, so u1 is not always the player facing a bet.
            action = "fold" if "fold" in snapshot["legal_actions"] else "check"
            await runtime.action("t1", "u1", f"fold:{snapshot['revision']}", snapshot["revision"], action, 0)
        else:
            await runtime.system_step("t1")
    await runtime.finish_and_settle("t1")

    await runtime.prepare_next_hand("t1")
    await runtime.start_hand("t1")
    while not runtime._tables["t1"].state.terminal:
        state = runtime._tables["t1"].state
        actor = state.acting_player
        if actor == "u1":
            snapshot = await runtime.public_snapshot("t1", "u1")
            # The button rotates, so u1 is not always the player facing a bet.
            action = "fold" if "fold" in snapshot["legal_actions"] else "check"
            await runtime.action("t1", "u1", f"fold:next:{snapshot['revision']}", snapshot["revision"], action, 0)
        else:
            await runtime.system_step("t1")
    await runtime.finish_and_settle("t1")

    assert await ledger.available_units("u1") == 0
    assert sum(await ledger.escrow_balances("t1")) == 200_000


@pytest.mark.anyio
async def test_positive_net_counts_as_win_but_tie_does_not(db_session_factory):
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(users), [
            {"id": "u1", "telegram_user_id": 1, "display_name": "A", "acquisition_tenant_id": "tenant"},
            {"id": "u2", "telegram_user_id": 2, "display_name": "B", "acquisition_tenant_id": "tenant"},
        ])
        # The hand below references this table. SQLite used to let that slide.
        await session.execute(insert(poker_tables).values(
            id="t1", scope="network", name="One", small_blind_units=50,
            big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
        await session.commit()
    history = HistoryService(db_session_factory)
    await history.record(HandRecord(
        hand_id="hand-1", table_id="t1", participants=[
            HandParticipantRecord("u1", None, 0, 500, ["As", "Ah"], True),
            HandParticipantRecord("u2", None, 1, -500, ["Kd", "Kc"], False),
        ],
    ))
    await history.record(HandRecord(
        hand_id="tie-hand", table_id="t1", participants=[
            HandParticipantRecord("u1", None, 0, 0, ["As", "Ah"], True),
            HandParticipantRecord("u2", None, 1, 0, ["Kd", "Kc"], True),
        ],
    ))
    profile = await history.profile("u1")
    assert profile.wins == 1
    assert profile.hands_played == 2

    hands = await history.last_hands("u1")
    first = next(item for item in hands if item["hand_id"] == "hand-1")
    opponent = next(item for item in first["players"] if item["participant_id"] == "u2")
    assert opponent.get("hole_cards") is None


def test_split_pot_rounding_cannot_unbalance_a_settlement():
    from types import SimpleNamespace

    from online.runtime import TableRuntimeManager

    # A three-way tie lands the stacks on thirds of a big blind.
    pot = 3.0 + 1.0 + 1.0
    players = {
        "a": SimpleNamespace(stack=10.0 - 3.0 + pot / 3),
        "b": SimpleNamespace(stack=10.0 - 1.0 + pot / 3),
        "c": SimpleNamespace(stack=10.0 - 1.0 + pot / 3),
    }
    state = SimpleNamespace(players=players, starting_stacks={"a": 10.0, "b": 10.0, "c": 10.0})

    starts, ends = TableRuntimeManager._settlement_units(state, 100)

    assert sum(ends[pid] - starts[pid] for pid in players) == 0
