"""A table that has never dealt a hand is an ordinary state, not a failure."""

import asyncio

import pytest
from sqlalchemy import insert

from online.ledger import PlayLedger
from online.runtime import EMPTY_SNAPSHOT, TableRuntimeManager
from online.schema import poker_tables, tenants


@pytest.fixture
def runtime(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(poker_tables).values(
                id="fresh", scope="network", name="Fresh", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
            await session.commit()

    asyncio.run(seed())
    return TableRuntimeManager(db_session_factory, PlayLedger(db_session_factory))


@pytest.mark.anyio
async def test_a_table_with_no_hand_behind_it_renders_instead_of_raising(runtime):
    """Raising killed the websocket before it sent anything: the REST route
    caught it and drew an empty table, the socket did not, so a freshly opened
    room could only tell its owner "reconnecting" -- forever, since no amount
    of retrying makes a hand appear."""
    snapshot = await runtime.public_snapshot("fresh", "u1")

    assert snapshot["phase"] == "waiting"
    assert snapshot["players"] == {}
    assert snapshot["legal_actions"] == []
    assert snapshot["viewer_state"] == "spectator"
    for key in EMPTY_SNAPSHOT:
        assert key in snapshot


@pytest.mark.anyio
async def test_a_player_who_has_just_sat_down_can_see_themselves(runtime, db_session_factory):
    """Before the first hand there is no runtime and no roster, so the ring is
    drawn from current_seats alone. Leaving it out made a player invisible to
    themselves in their own new room -- every place empty, and their own seat
    offered back to them, until a hand finally landed a minute or more later."""
    from sqlalchemy import insert

    from online.schema import table_seats, users

    async with db_session_factory() as session:
        await session.execute(insert(users).values(
            id="u1", telegram_user_id=1, display_name="Samo", acquisition_tenant_id="tenant"))
        await session.execute(insert(table_seats).values(
            id="s1", table_id="fresh", seat_no=3, occupant_kind="user",
            user_id="u1", stack_units=4_000, state="seated"))
        await session.commit()

    snapshot = await runtime.public_snapshot("fresh", "u1")

    assert snapshot["viewer_state"] == "seated"
    assert snapshot["viewer_player_id"] == "u1"
    seat = snapshot["current_seats"][3]
    assert seat["id"] == "u1" and seat["name"] == "Samo"
    assert seat["stack"] == 40, "and with the stack they actually brought"


@pytest.mark.anyio
async def test_a_spectator_at_the_same_table_still_sees_the_room(runtime, db_session_factory):
    snapshot = await runtime.public_snapshot("fresh", "nobody")
    assert snapshot["viewer_state"] == "spectator"
    assert snapshot["viewer_player_id"] is None
    assert snapshot["current_seats"] == {}
