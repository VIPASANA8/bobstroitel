from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select

from online.achievements import (
    ACHIEVEMENTS,
    AP_BY_RARITY,
    advance,
    comeback_codes,
    hand_class_code,
    is_seven_deuce,
    note_opponents,
    record_hand,
    tiers_completed,
)
from online.schema import tenants, user_achievements, users


NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def test_every_definition_is_ordered_and_priced():
    for code, definition in ACHIEVEMENTS.items():
        assert definition.code == code
        assert definition.tiers == tuple(sorted(definition.tiers)), code
        assert definition.tiers[0] > 0, code
        assert definition.rarity in AP_BY_RARITY, code
    assert tiers_completed((100, 500, 1000), 500) == 2
    assert tiers_completed((100, 500, 1000), 99) == 0


def test_a_royal_is_reported_as_a_royal_and_not_a_straight_flush():
    assert hand_class_code(["Ah", "Kh"], ["Qh", "Jh", "Th", "2c", "3d"]) == "royal_flush"
    assert hand_class_code(["9h", "8h"], ["7h", "6h", "5h", "2c", "3d"]) == "straight_flush"
    assert hand_class_code(["As", "Ah"], ["Ad", "Ac", "5h", "2c", "3d"]) == "quads"
    assert hand_class_code(["As", "Ah"], ["Ad", "5c", "5h", "2c", "3d"]) == "full_house"
    assert hand_class_code(["2h", "7d"], ["Ad", "5c", "9h", "Jc", "3d"]) is None
    # Nothing to read before the river.
    assert hand_class_code(["Ah", "Kh"], ["Qh", "Jh", "Th"]) is None


def test_seven_deuce_is_the_offsuit_one():
    assert is_seven_deuce(["7h", "2c"]) and is_seven_deuce(["2d", "7s"])
    assert not is_seven_deuce(["7h", "2h"]), "suited 72 is a different hand"
    assert not is_seven_deuce(["7h", "3c"])


def test_a_comeback_needs_the_recovery_to_follow_the_low():
    assert comeback_codes([40, 8, 20, 55]) == ["still_alive"]
    assert comeback_codes([40, 4, 20, 120]) == ["still_alive", "back_from_the_dead"]
    # Deep, felted, rebought: nothing was come back from.
    assert comeback_codes([120, 60, 3]) == []
    assert comeback_codes([60, 9]) == []
    assert comeback_codes([]) == []


@pytest.fixture
def two_players(db_session_factory):
    import asyncio

    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users), [
                {"id": "u1", "telegram_user_id": 1, "display_name": "A", "acquisition_tenant_id": "tenant"},
                {"id": "u2", "telegram_user_id": 2, "display_name": "B", "acquisition_tenant_id": "tenant"},
            ])
            await session.commit()

    asyncio.run(seed())
    return db_session_factory


@pytest.mark.anyio
async def test_a_tier_pays_once_and_progress_keeps_its_best(two_players):
    async with two_players() as session:
        async with session.begin():
            first = await advance(session, user_id="u1", code="big_pot", high_water=120, now=NOW)
            # A smaller pot afterwards is not a smaller achievement.
            second = await advance(session, user_id="u1", code="big_pot", high_water=90, now=NOW)
            third = await advance(session, user_id="u1", code="big_pot", high_water=260, now=NOW)
        row = (await session.execute(
            select(user_achievements).where(user_achievements.c.code == "big_pot")
        )).mappings().one()

    assert first == AP_BY_RARITY["epic"], "100 BB passed"
    assert second == 0, "and passing it again pays nothing"
    assert third == AP_BY_RARITY["epic"], "250 BB is the next tier"
    assert row["progress"] == 260 and row["tier"] == 2
    assert row["completed_at"] is None, "two of four tiers is not a finished achievement"


@pytest.mark.anyio
async def test_only_a_face_not_seen_before_moves_social(two_players):
    async with two_players() as session:
        async with session.begin():
            first = await note_opponents(session, user_id="u1", opponent_ids={"u2"}, now=NOW)
            again = await note_opponents(session, user_id="u1", opponent_ids={"u2"}, now=NOW)
            # A player is not their own opponent.
            self_only = await note_opponents(session, user_id="u1", opponent_ids={"u1"}, now=NOW)

    assert (first, again, self_only) == (1, 0, 0)


@pytest.mark.anyio
async def test_a_finished_hand_advances_what_it_earned_and_nothing_else(two_players):
    async with two_players() as session:
        async with session.begin():
            points = await record_hand(
                session,
                user_id="u1",
                hole_cards=["7h", "2c"],
                board=["7d", "7s", "2h", "9c", "Jd"],
                won=True,
                pot_bb=140.0,
                counts_results=True,
                opponent_ids={"u2"},
                now=NOW,
            )
        rows = {
            row["code"]: row
            for row in (await session.execute(select(user_achievements))).mappings().all()
        }

    assert rows["grind"]["progress"] == 1 and rows["grind"]["tier"] == 0
    assert rows["social"]["progress"] == 1
    assert rows["full_house"]["tier"] == 1, "sevens full of deuces"
    assert rows["big_pot"]["progress"] == 140 and rows["big_pot"]["tier"] == 1
    assert rows["seven_deuce"]["tier"] == 1
    assert "royal_flush" not in rows, "an achievement nobody earned gets no row"
    assert points == (
        AP_BY_RARITY["common"] + AP_BY_RARITY["epic"] * 2
    ), "full house, the pot and the seven-deuce"


@pytest.mark.anyio
async def test_a_room_hand_earns_the_volume_but_not_the_pot(two_players):
    async with two_players() as session:
        async with session.begin():
            await record_hand(
                session,
                user_id="u1",
                hole_cards=["Ah", "Kh"],
                board=["Qh", "Jh", "Th", "2c", "3d"],
                won=True,
                pot_bb=900.0,
                counts_results=False,
                opponent_ids={"u2"},
                now=NOW,
            )
        rows = {
            row["code"]: row
            for row in (await session.execute(select(user_achievements))).mappings().all()
        }

    assert rows["grind"]["progress"] == 1
    # The cards were really dealt, so the Royal stands.
    assert rows["royal_flush"]["tier"] == 1
    # The pot was not, so it does not.
    assert "big_pot" not in rows and "seven_deuce" not in rows
