"""Bots seeded before the roster existed still carry their old name tag."""

import pytest
from sqlalchemy import insert, select

from online.catalogue import BOT_NAMES, Catalogue
from online.schema import system_players, tenants


@pytest.mark.anyio
async def test_an_already_seeded_bot_is_renamed_in_place(db_session_factory):
    """In place, keeping the id: the persona, the seat and every hand of
    history are all attached to it."""
    async with db_session_factory() as session:
        await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
        await session.execute(insert(system_players), [
            {"id": f"system-{n:02d}", "name": f"Room Player {n:02d}",
             "difficulty": "normal", "active": True}
            for n in (1, 5, 36)
        ])
        await session.commit()

    await Catalogue(db_session_factory).seed_defaults()

    async with db_session_factory() as session:
        rows = dict((await session.execute(
            select(system_players.c.id, system_players.c.name)
        )).all())

    assert not any(name.startswith("Room Player") for name in rows.values())
    assert rows["system-01"] == BOT_NAMES[0]
    assert rows["system-05"] == BOT_NAMES[4]
    assert rows["system-36"] == BOT_NAMES[35]
    assert len(set(rows.values())) == len(rows), "and no two ended up sharing one"
