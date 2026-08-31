import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select, update

from online.ledger import PlayLedger
from online.runtime import TableRuntimeManager
from online.schema import play_sessions, poker_tables, system_players, table_seats, tenants, users
from online.seating import SeatingService


@pytest.fixture
def seated_player(db_session_factory):
    """One human and one bot, the human seated a while ago."""
    seated_at = datetime.now(timezone.utc) - timedelta(minutes=36)

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
                 "user_id": "u1", "system_player_id": None, "stack_units": 100_000,
                 "state": "seated", "seated_at": seated_at},
                {"id": "seat-bot", "table_id": "t1", "seat_no": 1, "occupant_kind": "system",
                 "user_id": None, "system_player_id": "bot-1", "stack_units": 100_000,
                 "state": "seated", "seated_at": None},
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(ledger.grant("u1", 100_000, "grant:u1"))
    asyncio.run(ledger.reserve_buy_in("u1", "t1", 100_000, "buyin:u1:t1"))
    asyncio.run(ledger.fund_system_seat("bot-1", "t1", 100_000, "system:t1:bot-1"))
    return (
        TableRuntimeManager(db_session_factory, ledger),
        SeatingService(db_session_factory, ledger, seat_idle_bots=False),
        db_session_factory,
        ledger,
    )


async def _play_one_folded_hand(runtime):
    await runtime.start_hand("t1")
    snapshot = await runtime.public_snapshot("t1", "u1")
    action = "fold" if "fold" in snapshot["legal_actions"] else "check"
    await runtime.action("t1", "u1", "hand-1", snapshot["revision"], action, 0)
    while not runtime._tables["t1"].state.terminal:
        await runtime.system_step("t1")
    await runtime.finish_and_settle("t1")


@pytest.mark.anyio
async def test_leaving_writes_the_report_the_lobby_reads(seated_player):
    runtime, seating, session_factory, _ = seated_player
    await _play_one_folded_hand(runtime)

    await seating.request_leave("u1", "t1", immediate=True)

    async with session_factory() as session:
        report = (await session.execute(select(play_sessions))).mappings().one()
        assert report["user_id"] == "u1" and report["table_id"] == "t1"
        assert report["hands"] == 1
        assert report["big_blind_units"] == 100
        assert report["net_units"] < 0, "folding the blind costs chips"
        assert report["biggest_pot_units"] > 0
        assert report["xp_earned"] == 1, "the hand's XP belongs to the session that played it"
        assert report["seen_at"] is None
        # The report has to outlive the seat: the seat row is blanked and
        # handed to the next player, and the lobby reads this afterwards.
        seat = (await session.execute(
            select(table_seats).where(table_seats.c.id == "seat-u1")
        )).mappings().one()
        assert seat["state"] == "empty" and seat["seated_at"] is None


@pytest.mark.anyio
async def test_a_player_who_played_nothing_gets_no_report(seated_player):
    _, seating, session_factory, _ = seated_player

    await seating.request_leave("u1", "t1", immediate=True)

    async with session_factory() as session:
        assert (await session.execute(select(play_sessions))).first() is None


@pytest.mark.anyio
async def test_a_second_sitting_does_not_inherit_the_first_ones_hands(seated_player):
    """Seat rows are reused, so the only thing separating two sessions at one
    table is when the second one began."""
    runtime, seating, session_factory, ledger = seated_player
    await _play_one_folded_hand(runtime)
    await seating.request_leave("u1", "t1", immediate=True)

    await ledger.reserve_buy_in("u1", "t1", 50_000, "buyin:u1:t1:second")
    async with session_factory() as session:
        async with session.begin():
            await session.execute(update(table_seats).where(table_seats.c.id == "seat-u1").values(
                occupant_kind="user", user_id="u1", stack_units=50_000, state="seated",
                seated_at=datetime.now(timezone.utc),
            ))
    await seating.request_leave("u1", "t1", immediate=True)

    async with session_factory() as session:
        reports = (await session.execute(select(play_sessions.c.hands))).scalars().all()
        assert reports == [1], "the empty second sitting reported nothing of the first"
