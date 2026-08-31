import asyncio

import pytest
from sqlalchemy import insert, select

from online.ledger import PlayLedger
from online.progression import (
    DAILY_HAND_XP_CAP,
    LEVEL_XP,
    record_hand,
    level_for_xp,
    msk_day,
    rank_for_level,
    xp_for_hand,
    xp_to_next_level,
)
from online.missions import POOLS
from online.runtime import TableRuntimeManager
from online.schema import (
    poker_tables,
    progress_days,
    system_players,
    table_seats,
    tenants,
    user_progression,
    users,
    xp_events,
)
from datetime import datetime, timedelta, timezone

#: Every mission in the volume slot pays the same, which is what lets this
#: file talk about the cap without caring which one was drawn.
VOLUME_MISSION_XP = POOLS["volume"][0].xp


def test_the_soft_cap_bands_add_up_to_the_published_ceiling():
    assert sum(xp_for_hand(n) for n in range(1, 151)) == 150
    assert sum(xp_for_hand(n) for n in range(151, 301)) == 75
    assert sum(xp_for_hand(n) for n in range(1, 1000)) == DAILY_HAND_XP_CAP


def test_the_level_table_matches_the_published_anchors():
    anchors = {1: 0, 2: 150, 3: 350, 5: 900, 10: 3_000, 15: 5_500, 20: 9_000,
               25: 13_000, 30: 18_000, 35: 23_500, 40: 30_000, 45: 37_000, 50: 45_000}
    for level, total in anchors.items():
        assert LEVEL_XP[level - 1] == total
        assert level_for_xp(total) == level
        assert level == 1 or level_for_xp(total - 1) == level - 1
    # Every step costs more than the one before it, all the way up.
    steps = [b - a for a, b in zip(LEVEL_XP, LEVEL_XP[1:])]
    assert steps == sorted(steps)
    assert xp_to_next_level(0) == 150
    assert xp_to_next_level(45_000) is None
    assert rank_for_level(1) == "ROOKIE" and rank_for_level(50) == "VETERAN"


def test_a_day_boundary_is_msk_not_utc():
    # 22:30 UTC is already tomorrow in Moscow, which is the whole point of
    # fixing one clock for the cap and the idempotency key alike.
    assert msk_day(datetime(2026, 8, 30, 22, 30, tzinfo=timezone.utc)) == "2026-08-31"
    assert msk_day(datetime(2026, 8, 30, 20, 30, tzinfo=timezone.utc)) == "2026-08-30"


@pytest.mark.anyio
async def test_the_soft_cap_stops_paying_and_the_next_day_starts_over(db_session_factory):
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(users).values(
            id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
        ))
        await session.commit()

    day = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    async with db_session_factory() as session:
        async with session.begin():
            for hand in range(400):
                await record_hand(
                    session, owner_kind="user", owner_id="u1",
                    hand_id=f"hand-{hand}", net_units=0, big_blind_units=100,
                    counts_results=True, now=day,
                )
        day_row = (await session.execute(select(progress_days))).mappings().one()
        assert day_row["xp"] == DAILY_HAND_XP_CAP, "the cap is on what hands pay"
        assert day_row["hands"] == 400, "hands past the cap still count as played"
        # The volume mission finished somewhere in there and pays on top: the
        # cap holds down the grind, not the day.
        row = (await session.execute(
            select(user_progression).where(user_progression.c.user_id == "u1")
        )).mappings().one()
        assert row["xp"] == DAILY_HAND_XP_CAP + VOLUME_MISSION_XP
        assert row["level"] == level_for_xp(row["xp"])

    async with db_session_factory() as session:
        async with session.begin():
            await record_hand(
                session, owner_kind="user", owner_id="u1",
                hand_id="tomorrow", net_units=0, big_blind_units=100,
                counts_results=True, now=day + timedelta(days=1),
            )
        total = (await session.execute(
            select(user_progression.c.xp).where(user_progression.c.user_id == "u1")
        )).scalar_one()
        assert total == DAILY_HAND_XP_CAP + VOLUME_MISSION_XP + 1


@pytest.fixture
def table_with_one_human(db_session_factory):
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
    return TableRuntimeManager(db_session_factory, ledger)


@pytest.mark.anyio
async def test_a_settled_hand_pays_once_however_often_it_is_settled(table_with_one_human):
    runtime = table_with_one_human
    await runtime.start_hand("t1")
    snapshot = await runtime.public_snapshot("t1", "u1")
    await runtime.action("t1", "u1", "fold", snapshot["revision"], "fold", 0)

    await runtime.finish_and_settle("t1")
    # The same replay the settlement itself is built to survive.
    await runtime.finish_and_settle("t1")

    async with runtime.session_factory() as session:
        assert (await session.execute(
            select(user_progression.c.xp).where(user_progression.c.user_id == "u1")
        )).scalar_one() == 1
        assert (await session.execute(
            select(system_players.c.xp).where(system_players.c.id == "bot-1")
        )).scalar_one() == 1, "a bot at a table with a person keeps a level of its own"
        events = (await session.execute(select(xp_events.c.idempotency_key))).scalars().all()
        assert len(events) == 1 and events[0].startswith("hand:")
        assert (await session.execute(select(progress_days.c.hands))).scalars().all() == [1, 1]


@pytest.mark.anyio
async def test_a_room_hand_counts_as_played_but_not_as_a_result(db_session_factory):
    """§3: volume counts wherever it is played; big blinds only at a network
    table. Two accounts alone in a room they opened can otherwise write any
    result they like into their own statistics."""
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(users).values(
            id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
        ))
        await session.commit()

    day = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    async with db_session_factory() as session:
        async with session.begin():
            await record_hand(
                session, owner_kind="user", owner_id="u1", hand_id="network",
                net_units=250, big_blind_units=100, counts_results=True, now=day,
            )
            await record_hand(
                session, owner_kind="user", owner_id="u1", hand_id="room",
                net_units=1_000_000, big_blind_units=100, counts_results=False, now=day,
            )
        row = (await session.execute(select(progress_days))).mappings().one()

    assert row["hands"] == 2, "both were played"
    assert row["hands_won"] == 2, "and both were won"
    assert row["result_hands"] == 1, "only one of them may move a rate"
    assert row["net_bb_x100"] == 250, "+2.5 BB from the network table, and nothing else"
    assert row["xp"] == 2, "volume pays the same wherever it is played"
