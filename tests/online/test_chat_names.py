"""A chat line is signed by a person, not by a database key."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import insert

from online.chat import ChatService
from online.schema import poker_tables, tenants, users


@pytest.fixture
def chat(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="Samo", acquisition_tenant_id="tenant"))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6))
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
async def test_a_line_always_has_an_author(chat, db_session_factory):
    """The outer join in recent() is defence, not a scenario: chat_messages
    requires a user_id and points it at users, so a message from an account
    that does not exist cannot be written at all. This asserted the opposite
    and only passed because SQLite was ignoring foreign keys in the tests."""
    import sqlalchemy.exc

    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await chat.post("t1", "ghost", "кто здесь", enforce_rate_limit=False)


@pytest.mark.anyio
async def test_a_message_may_be_as_long_as_the_app_accepts(chat, db_session_factory):
    """Formatting markers count against the limit, so the app takes 1000 --
    and the column was still 300, which Postgres enforces and the player saw
    as a 500."""
    from online.chat import CHAT_TEXT_MAX

    long_message = "и" * CHAT_TEXT_MAX
    posted = await chat.post("t1", "u1", long_message, enforce_rate_limit=False)
    assert len(posted.text) == CHAT_TEXT_MAX

    [row] = await chat.recent("t1")
    assert len(row.text) == CHAT_TEXT_MAX


def test_the_client_renders_the_name_not_the_key():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "escapeHtml(row.display_name" in source
    assert "escapeHtml(row.user_id" not in source
