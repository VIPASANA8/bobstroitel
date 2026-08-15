import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import insert

from online.amounts import from_units, to_units
from online.ledger import InsufficientPlayBalance, PlayLedger
from online.schema import poker_tables, tenants, users


@pytest.fixture
def user_id():
    return "u1"


@pytest.fixture
def table_id():
    return "t1"


@pytest.fixture
def ledger(db_session_factory, user_id, table_id):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id=user_id,
                telegram_user_id=1,
                display_name="Player",
                acquisition_tenant_id="tenant",
            ))
            await session.execute(insert(poker_tables).values(
                id=table_id,
                scope="network",
                name="Test",
                small_blind_units=50,
                big_blind_units=100,
                min_buy_in_bb=40,
                max_buy_in_bb=100,
                max_seats=6,
            ))
            await session.commit()

    asyncio.run(seed())
    return PlayLedger(db_session_factory)


def test_play_amounts_use_integer_hundredths():
    assert to_units(Decimal("0.50")) == 50
    assert from_units(128000) == Decimal("1280.00")


@pytest.mark.anyio
async def test_repeating_faucet_request_posts_once(ledger, user_id):
    first = await ledger.grant(user_id, 100_000, "grant:u1:first")
    second = await ledger.grant(user_id, 100_000, "grant:u1:first")
    assert first.transaction_id == second.transaction_id
    assert await ledger.available_units(user_id) == 100_000


@pytest.mark.anyio
async def test_buy_in_cannot_overdraw_wallet(ledger, user_id, table_id):
    await ledger.grant(user_id, 4_000, "grant:u1:small")
    with pytest.raises(InsufficientPlayBalance):
        await ledger.reserve_buy_in(user_id, table_id, 4_001, "buyin:u1:t1")


@pytest.mark.anyio
async def test_return_stack_reuses_the_original_transaction(ledger, user_id, table_id):
    await ledger.grant(user_id, 1_000, "grant:u1:return")
    await ledger.reserve_buy_in(user_id, table_id, 1_000, "buyin:u1:return")
    first = await ledger.return_stack(user_id, table_id, "return:u1:t1")
    second = await ledger.return_stack(user_id, table_id, "return:u1:t1")
    assert first.transaction_id == second.transaction_id
    assert await ledger.available_units(user_id) == 1_000
