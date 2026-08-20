"""A chat line is signed by a person, not by a database key."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import insert

from online.chat import ChatService
from online.schema import tenants, users


@pytest.fixture
def chat(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="Samo", acquisition_tenant_id="tenant"))
            await session.commit()

    asyncio.run(seed())
    return ChatService(db_session_factory)


@pytest.mark.anyio
async def test_a_message_carries_the_name_of_whoever_wrote_it(chat):
    """The client had nothing but user_id to show, so every line was signed
    with a thirty-two character hex string."""
    posted = await chat.post("t1", "u1", "раздавай уже")
    assert posted.display_name == "Samo"

    [row] = await chat.recent("t1")
    assert row.display_name == "Samo"
    assert row.user_id == "u1", "the id is still there for anything that needs it"


@pytest.mark.anyio
async def test_a_message_outlives_the_account_that_wrote_it(chat):
    """An outer join, so a deleted author leaves the log readable rather than
    dropping every line they ever wrote."""
    await chat.post("t1", "ghost", "кто здесь", enforce_rate_limit=False)
    names = {row.display_name for row in await chat.recent("t1")}
    assert names == {"Игрок"}


def test_the_client_renders_the_name_not_the_key():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "escapeHtml(row.display_name" in source
    assert "escapeHtml(row.user_id" not in source
