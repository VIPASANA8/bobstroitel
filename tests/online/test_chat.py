import asyncio

import pytest
from sqlalchemy import insert

from online.chat import ChatRateLimited, ChatService
from online.schema import poker_tables, tenants, users


@pytest.fixture
def chat(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
            ))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            await session.commit()
    asyncio.run(seed())
    return ChatService(db_session_factory)


@pytest.mark.anyio
async def test_chat_returns_only_last_fifty_messages(chat):
    for index in range(55):
        await chat.post("t1", "u1", f"message {index}", now=index, enforce_rate_limit=False)
    rows = await chat.recent("t1")
    assert len(rows) == 50
    assert rows[0].text == "message 5"


@pytest.mark.anyio
async def test_chat_rejects_sixth_message_inside_ten_seconds(chat):
    for index in range(5):
        await chat.post("t1", "u1", f"ok {index}", now=100 + index)
    with pytest.raises(ChatRateLimited):
        await chat.post("t1", "u1", "too fast", now=109)
