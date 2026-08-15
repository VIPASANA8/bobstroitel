import asyncio

import pytest
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
