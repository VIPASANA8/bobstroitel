import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from online.missions import (
    COMPLETION_XP,
    POOLS,
    SLOTS,
    advance,
    assigned,
    next_reset,
    position_bit,
    positions_played,
    reroll,
    rerolled_today,
    state_for,
)
from online.progression import advance_missions
from online.schema import tenants, user_missions, user_progression, users, xp_events


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
DAY = "2026-08-31"


def test_no_mission_asks_for_a_result():
    """§70 in one assertion: a daily rewards activity or notices something that
    happened anyway. The moment one pays for winning, it is worth playing badly
    for."""
    allowed = {"hands", "sessions", "tables", "full_table_hands", "positions", "longest_session"}
    for slot, pool in POOLS.items():
        assert pool, slot
        for mission in pool:
            assert mission.slot == slot
            assert mission.source in allowed, mission.code
            assert mission.target > 0 and mission.xp > 0


def test_the_same_day_always_draws_the_same_three():
    first = [assigned("u1", DAY, slot).code for slot in SLOTS]
    assert first == [assigned("u1", DAY, slot).code for slot in SLOTS]
    # A reroll moves along the pool rather than re-rolling into the same one.
    for slot in SLOTS:
        if len(POOLS[slot]) > 1:
            assert assigned("u1", DAY, slot, offset=1).code != assigned("u1", DAY, slot).code


def test_the_countdown_points_at_the_next_msk_midnight():
    # 22:30 UTC is 01:30 MSK, so the next reset is 22.5 hours away, not 1.5.
    assert next_reset(datetime(2026, 8, 30, 22, 30, tzinfo=timezone.utc)) == datetime(
        2026, 8, 31, 21, 0, tzinfo=timezone.utc
    )


def test_positions_are_counted_once_each_and_heads_up_is_the_button():
    mask = position_bit("BTN") | position_bit("SB") | position_bit("BTN")
    assert positions_played(mask) == 2
    assert position_bit("BTN / SB") == position_bit("BTN"), "one seat is one position"
    assert position_bit("") == 0


@pytest.fixture
def player(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
            ))
            await session.commit()

    asyncio.run(seed())
    return db_session_factory


@pytest.mark.anyio
async def test_a_mission_pays_once_and_only_when_it_lands(player):
    volume = assigned("u1", DAY, "volume")
    async with player() as session:
        async with session.begin():
            short = await advance_missions(session, "u1", DAY, {"hands": volume.target - 1}, NOW)
            landed = await advance_missions(session, "u1", DAY, {"hands": volume.target}, NOW)
            # More hands afterwards are not a second completion.
            again = await advance_missions(session, "u1", DAY, {"hands": volume.target + 50}, NOW)
        events = (await session.execute(select(xp_events.c.amount, xp_events.c.source))).all()
        xp = (await session.execute(
            select(user_progression.c.xp).where(user_progression.c.user_id == "u1")
        )).scalar_one()

    assert (short, landed, again) == (0, volume.xp, 0), "paid on the hand that landed it, once"
    assert events == [(volume.xp, "daily")]
    assert xp == volume.xp


@pytest.mark.anyio
async def test_finishing_all_three_pays_the_completion_on_top(player):
    drawn = {slot: assigned("u1", DAY, slot) for slot in SLOTS}
    facts = {mission.source: mission.target for mission in drawn.values()}
    async with player() as session:
        async with session.begin():
            await advance_missions(session, "u1", DAY, facts, NOW)
        xp = (await session.execute(
            select(user_progression.c.xp).where(user_progression.c.user_id == "u1")
        )).scalar_one()
        keys = set((await session.execute(select(xp_events.c.idempotency_key))).scalars().all())

    assert xp == sum(m.xp for m in drawn.values()) + COMPLETION_XP
    assert f"daily:u1:{DAY}:complete" in keys
    assert len(keys) == 4, "three missions and the completion, once each"


@pytest.mark.anyio
async def test_a_second_pass_over_the_same_facts_pays_nothing(player):
    drawn = {slot: assigned("u1", DAY, slot) for slot in SLOTS}
    facts = {mission.source: mission.target for mission in drawn.values()}
    async with player() as session:
        async with session.begin():
            await advance_missions(session, "u1", DAY, facts, NOW)
            await advance_missions(session, "u1", DAY, facts, NOW)
        total = (await session.execute(select(xp_events.c.amount))).scalars().all()

    assert len(total) == 4


@pytest.mark.anyio
async def test_one_reroll_a_day_and_never_a_finished_one(player):
    async with player() as session:
        async with session.begin():
            first = await reroll(session, "u1", DAY, "volume", NOW)
            # The day's one swap is spent, whichever slot asks next.
            second = await reroll(session, "u1", DAY, "variety", NOW)
        assert (first, second) == (True, False)
        assert await rerolled_today(session, "u1", DAY)
        state = await state_for(session, "u1", DAY)
        assert state["volume"]["mission"].code == assigned("u1", DAY, "volume", offset=1).code
        assert state["volume"]["rerolled"] is True
        assert state["variety"]["rerolled"] is False

    # Tomorrow is a fresh one.
    tomorrow = "2026-09-01"
    async with player() as session:
        async with session.begin():
            assert await reroll(session, "u1", tomorrow, "volume", NOW + timedelta(days=1))


@pytest.mark.anyio
async def test_a_finished_mission_cannot_be_swapped_away(player):
    volume = assigned("u1", DAY, "volume")
    async with player() as session:
        async with session.begin():
            await advance(session, user_id="u1", day=DAY, facts={"hands": volume.target}, now=NOW)
            swapped = await reroll(session, "u1", DAY, "volume", NOW)
        row = (await session.execute(
            select(user_missions).where(user_missions.c.slot == "volume")
        )).mappings().one()

    assert swapped is False
    assert row["completed_at"] is not None and row["reroll_offset"] == 0


@pytest.mark.anyio
async def test_the_day_gives_out_exactly_one_reroll_even_under_a_race(player):
    """Two requests arriving together both read an unused reroll and both kept
    theirs. The unique index is what actually holds the rule."""
    from sqlalchemy.exc import IntegrityError

    async with player() as session:
        async with session.begin():
            assert await reroll(session, "u1", DAY, "volume", NOW)
        # What the losing request does when it skips the read and writes anyway.
        with pytest.raises(IntegrityError):
            async with session.begin():
                await session.execute(user_missions.insert().values(
                    user_id="u1", day=DAY, slot="variety", reroll_offset=1,
                    reroll_claimed=True, updated_at=NOW,
                ))

    async with player() as session:
        kept = (await session.execute(
            select(user_missions.c.slot).where(user_missions.c.reroll_offset != 0)
        )).scalars().all()
    assert kept == ["volume"]


@pytest.mark.anyio
async def test_a_mission_finished_mid_reroll_keeps_its_completion(player):
    """The read said unfinished, the mission landed, and the write reset the
    progress underneath it -- leaving a different mission marked complete at
    zero."""
    volume = assigned("u1", DAY, "volume")
    async with player() as session:
        async with session.begin():
            # Somebody else's transaction gets there first.
            await advance(session, user_id="u1", day=DAY, facts={"hands": volume.target}, now=NOW)
            swapped = await reroll(session, "u1", DAY, "volume", NOW)
        row = (await session.execute(
            select(user_missions).where(user_missions.c.slot == "volume")
        )).mappings().one()

    assert swapped is False
    assert row["completed_at"] is not None
    assert row["progress"] == volume.target, "the completion kept its progress"
    assert row["reroll_offset"] == 0
