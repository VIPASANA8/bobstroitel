"""Exercise both transaction orders, including a player's first mission row."""

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from online import missions
from online.asyncio_runner import run
from online.progression import advance_missions
from online.schema import metadata, tenants, users, xp_events


NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)
DAY = "2026-08-31"
DATABASES = ["sqlite", pytest.param("postgres", marks=pytest.mark.postgres)]


async def _database(database, tmp_path):
    url = os.environ.get("POKER8_TEST_DATABASE_URL") if database == "postgres" else (
        f"sqlite+aiosqlite:///{tmp_path / 'missions.sqlite3'}"
    )
    if not url:
        pytest.skip("POKER8_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    factory = async_sessionmaker(engine)
    # Pick a player whose replacement has a higher target: the old race would
    # complete 30/40 (or 20/30) and pay for the mission that was swapped away.
    while True:
        user_id = uuid.uuid4().hex
        original = missions.assigned(user_id, DAY, "volume")
        replacement = missions.assigned(user_id, DAY, "volume", offset=1)
        if replacement.target > original.target:
            break
    async with factory.begin() as session:
        await session.execute(tenants.insert().values(id=user_id, slug=user_id, name="Test"))
        await session.execute(users.insert().values(
            id=user_id, telegram_user_id=int(user_id[:12], 16),
            display_name="Player", acquisition_tenant_id=user_id,
        ))
    return engine, factory, user_id, original, replacement


@pytest.mark.parametrize("database", DATABASES)
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("first", ["settlement", "reroll"])
def test_reroll_and_settlement_use_one_mission_version(database, existing, first, tmp_path, monkeypatch):
    async def check():
        engine, factory, user_id, original, replacement = await _database(database, tmp_path)
        read, resume = asyncio.Event(), asyncio.Event()
        tasks = []
        try:
            if existing:
                async with factory.begin() as session:
                    await missions.advance(session, user_id=user_id, day=DAY, facts={"hands": 1}, now=NOW)
            # Pause only after a real database read. No SQL results are mocked;
            # a second connection is allowed to attempt the opposing write.
            hook = "state_for" if first == "settlement" else "rerolled_today"
            original_hook = getattr(missions, hook)

            async def pause_after_read(*args):
                result = await original_hook(*args)
                if asyncio.current_task().get_name() == first and not read.is_set():
                    read.set()
                    await resume.wait()
                return result

            monkeypatch.setattr(missions, hook, pause_after_read)

            async def settle():
                async with factory.begin() as session:
                    return await advance_missions(session, user_id, DAY, {"hands": original.target}, NOW)

            async def swap():
                async with factory.begin() as session:
                    return await missions.reroll(session, user_id, DAY, "volume", NOW)

            operations = {"settlement": settle, "reroll": swap}
            tasks.append(asyncio.create_task(operations[first](), name=first))
            await asyncio.wait_for(read.wait(), timeout=5)
            second = "reroll" if first == "settlement" else "settlement"
            tasks.append(asyncio.create_task(operations[second](), name=second))
            # Give the second transaction a chance to race; a correct writer
            # waits for the first transaction instead of using a stale read.
            await asyncio.wait([tasks[1]], timeout=0.2)
            resume.set()
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
            result = dict(zip((first, second), results))
            async with factory() as session:
                current = (await missions.state_for(session, user_id, DAY))["volume"]
                events = (await session.execute(select(xp_events.c.reference, xp_events.c.amount).where(
                    xp_events.c.user_id == user_id,
                ))).all()
            if first == "settlement":
                assert result == {"settlement": original.xp, "reroll": False}
                assert current["mission"] == original and current["completed_at"] is not None
                assert events == [(original.code, original.xp)]
            else:
                assert result == {"reroll": True, "settlement": 0}
                assert current["mission"] == replacement and current["completed_at"] is None
                assert current["progress"] == original.target
                assert events == []
                async with factory.begin() as session:
                    assert await advance_missions(session, user_id, DAY, {"hands": replacement.target}, NOW) == replacement.xp
                    assert await advance_missions(session, user_id, DAY, {"hands": replacement.target}, NOW) == 0
        finally:
            resume.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await engine.dispose()

    run(check())


@pytest.mark.parametrize("database", DATABASES)
def test_three_concurrent_rerolls_keep_one_replacement(database, tmp_path):
    async def check():
        engine, factory, user_id, _, _ = await _database(database, tmp_path)
        barrier = asyncio.Barrier(3)
        try:
            async def swap(slot):
                async with factory.begin() as session:
                    await barrier.wait()
                    return await missions.reroll(session, user_id, DAY, slot, NOW)

            results = await asyncio.wait_for(asyncio.gather(*(swap(slot) for slot in missions.SLOTS)), timeout=10)
            assert sorted(results) == [False, False, True]
            async with factory() as session:
                state = await missions.state_for(session, user_id, DAY)
                assert sum(item["rerolled"] for item in state.values()) == 1
        finally:
            await engine.dispose()

    run(check())
