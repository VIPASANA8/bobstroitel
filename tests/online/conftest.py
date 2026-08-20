import asyncio

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from online.schema import metadata


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores foreign keys unless asked, and production is Postgres,
    # which does not. A write that referenced a row that was no longer being
    # created passed every test here and failed 23 times a minute on the live
    # site. The test database enforces them now, like the real one.
    @event.listens_for(engine.sync_engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def drop_schema():
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
        await engine.dispose()

    asyncio.run(create_schema())
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        asyncio.run(drop_schema())
