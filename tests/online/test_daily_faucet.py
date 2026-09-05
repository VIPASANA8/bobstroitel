"""Running out of practice chips must not be a dead end -- and must not be a
tap either. Once a day, and only for somebody who cannot sit down anywhere.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from online.faucet import FLOOR_UNITS, REFILL_EVERY, WELCOME_UNITS, refill_if_broke
from online.ledger import PlayLedger
from online.schema import poker_tables, table_seats, tenants, users


#: play_transactions.created_at is written by the database, not by the caller,
#: so "when was the last grant" is always real wall-clock time. Only `now` is
#: injectable, and these tests move it relative to that.
START = datetime.now(timezone.utc)


@pytest.fixture
def wallet(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(poker_tables).values(
                id="micro-a", scope="network", asset="PLAY", name="Micro A",
                small_blind_units=50, big_blind_units=100,
                min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    asyncio.run(ledger.ensure_user_wallet("u1"))
    return ledger, db_session_factory


async def _refill(wallet, now=START):
    ledger, session_factory = wallet
    return await refill_if_broke(session_factory, ledger, "u1", now=now)


@pytest.mark.anyio
async def test_a_player_who_cannot_afford_a_seat_is_put_back_in(wallet):
    ledger, _ = wallet
    available, refill_at = await _refill(wallet)
    assert available == WELCOME_UNITS
    # Nothing to wait for once they have chips again.
    assert refill_at is None
    assert await ledger.available_units("u1") == WELCOME_UNITS


@pytest.mark.anyio
async def test_a_player_who_can_still_sit_down_gets_nothing(wallet):
    """The floor is one buy-in, not zero: a short stack is a game, not a dead
    end, and topping it up would make the number meaningless."""
    ledger, _ = wallet
    await ledger.grant("u1", FLOOR_UNITS, "seed:u1")
    available, refill_at = await _refill(wallet)
    assert (available, refill_at) == (FLOOR_UNITS, None)


@pytest.mark.anyio
async def test_the_second_stack_of_the_day_is_refused(wallet):
    ledger, _ = wallet
    await _refill(wallet)
    # Spend it all and come back an hour later.
    await ledger.reserve_buy_in("u1", "micro-a", WELCOME_UNITS, "spend:u1")
    later = START + timedelta(hours=1)
    available, refill_at = await refill_if_broke(*_svc(wallet), "u1", now=later)
    assert available == 0
    assert later < refill_at <= START + REFILL_EVERY + timedelta(minutes=1)


@pytest.mark.anyio
async def test_the_faucet_opens_again_a_day_later(wallet):
    ledger, _ = wallet
    await _refill(wallet)
    await ledger.reserve_buy_in("u1", "micro-a", WELCOME_UNITS, "spend:u1")
    tomorrow = START + REFILL_EVERY + timedelta(hours=1)
    available, refill_at = await refill_if_broke(*_svc(wallet), "u1", now=tomorrow)
    assert (available, refill_at) == (WELCOME_UNITS, None)


@pytest.mark.anyio
async def test_chips_in_front_of_them_at_a_table_are_still_theirs(wallet):
    """An empty wallet is not the same as being broke: sitting down with the
    last of a stack would otherwise read as ruin and mint a second one."""
    ledger, session_factory = wallet
    async with session_factory() as session:
        await session.execute(insert(table_seats).values(
            id="seat-1", table_id="micro-a", seat_no=0, occupant_kind="user",
            user_id="u1", stack_units=WELCOME_UNITS, state="seated"))
        await session.commit()
    available, refill_at = await _refill(wallet)
    assert (available, refill_at) == (0, None)


def _svc(wallet):
    ledger, session_factory = wallet
    return session_factory, ledger
