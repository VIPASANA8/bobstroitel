"""A bot borrows a name while it sits, and no two share one at the same time."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select

from online.bot_names import BOT_NAMES
from online.ledger import PlayLedger
from online.schema import poker_tables, system_players, table_seats, tenants, users
from online.seating import SeatingService


@pytest.fixture
def seating(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant"))
            await session.execute(insert(poker_tables), [
                {"id": table_id, "scope": "network", "name": table_id, "small_blind_units": 50,
                 "big_blind_units": 100, "min_buy_in_bb": 40, "max_buy_in_bb": 100, "max_seats": 6}
                for table_id in ("t1", "t2", "t3")
            ])
            await session.execute(insert(system_players), [
                {"id": f"bot-{i}", "name": f"seed-{i}", "difficulty": "normal", "active": True}
                for i in range(1, 21)
            ])
            await session.commit()

    asyncio.run(seed())
    ledger = PlayLedger(db_session_factory)
    asyncio.run(ledger.ensure_faucet())
    return SeatingService(db_session_factory, ledger), db_session_factory


async def _seated_bot_names(session_factory):
    async with session_factory() as session:
        return (await session.execute(
            select(system_players.c.name)
            .select_from(system_players.join(
                table_seats, table_seats.c.system_player_id == system_players.c.id))
            .where(table_seats.c.state != "empty")
        )).scalars().all()


@pytest.mark.anyio
async def test_a_bot_takes_a_name_from_the_pool_when_it_sits_down(seating):
    service, session_factory = seating
    await service.process_boundary("t1")

    names = await _seated_bot_names(session_factory)
    assert names, "bots sat down"
    assert all(name in BOT_NAMES for name in names), names
    assert not any(name.startswith("seed-") for name in names), "the placeholder is gone"


@pytest.mark.anyio
async def test_no_two_bots_anywhere_carry_the_same_name_at_once(seating):
    """Three tables filling at the same moment is the case that catches a pool
    picked per table instead of across the network."""
    service, session_factory = seating
    for table_id in ("t1", "t2", "t3"):
        await service.process_boundary(table_id)

    names = await _seated_bot_names(session_factory)
    assert len(names) >= 8, names
    assert len(set(names)) == len(names), f"a name is on two tables at once: {names}"


@pytest.mark.anyio
async def test_the_name_is_new_each_time_rather_than_the_bot_keeping_one(seating):
    """The same bot sitting down again is a different person to whoever is
    watching, which is the whole point of borrowing rather than owning."""
    service, session_factory = seating
    seen = set()
    for _ in range(6):
        await service.process_boundary("t1")
        seen.update(await _seated_bot_names(session_factory))
        # Empty the table so the next boundary seats a fresh set.
        async with session_factory() as session:
            await session.execute(table_seats.delete().where(table_seats.c.table_id == "t1"))
            await session.commit()

    assert len(seen) > 4, f"only ever {len(seen)} names appeared: {sorted(seen)}"


def test_the_pool_is_big_enough_for_a_full_network():
    """Six lobby tables plus rooms, four bots each -- the pool has to outlast
    them or two players end up sharing a name."""
    assert len(set(BOT_NAMES)) == len(BOT_NAMES), "the pool repeats a name"
    assert len(BOT_NAMES) >= 100


@pytest.mark.anyio
async def test_a_short_pool_runs_out_rather_than_issuing_a_name_twice(seating, monkeypatch):
    """Two people at one table under the same name is worse than a bot keeping
    the one it had, so an exhausted pool hands out nothing."""
    import online.seating as module

    monkeypatch.setattr(module, "BOT_NAMES", ("Один", "Два"))
    service, session_factory = seating

    await service.process_boundary("t1")
    await service.process_boundary("t2")

    names = await _seated_bot_names(session_factory)
    assert len(set(names)) == len(names), f"a borrowed name was lent twice: {names}"
    borrowed = [name for name in names if name in ("Один", "Два")]
    assert len(borrowed) == 2, "both pool names went out, and only once each"
