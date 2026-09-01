import asyncio
import os
import re
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from online.schema import (
    cash_accounts, cash_operators, metadata, play_accounts, tenants, users,
)


@pytest.fixture
def anyio_backend():
    return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}


@pytest.fixture
def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def setup():
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    asyncio.run(setup())
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        async def teardown():
            async with engine.begin() as connection:
                await connection.run_sync(metadata.drop_all)
            await engine.dispose()
        asyncio.run(teardown())


@pytest.fixture
async def cash_db(request, anyio_backend):
    raw_url = os.environ.get("POKER8_CASH_TEST_DATABASE_URL")
    if not raw_url:
        pytest.fail("Set POKER8_CASH_TEST_DATABASE_URL to the local postgres_test service")
    url = make_url(raw_url)
    if not (
        url.drivername == "postgresql+psycopg"
        and url.host in {"localhost", "127.0.0.1", "::1"}
        and url.port == 5433 and url.database == "poker8_test"
        and not url.query  # libpq query parameters can override host/port.
    ):
        pytest.fail("Refusing a database outside the local postgres_test target")
    schema = "cash_test_" + uuid4().hex
    schema_state = getattr(request, "param", "current")
    engine = create_async_engine(
        url, poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        if schema_state == "empty":
            yield factory
            return
        async with engine.begin() as conn:
            selected = [tenants, users, play_accounts] if schema_state == "historical" else None
            await conn.run_sync(lambda sync: metadata.create_all(sync, tables=selected))
            await conn.execute(tenants.insert().values(id="tenant", slug="cash-test", name="Test"))
            await conn.execute(tenants.insert().values(id="tenant-other", slug="other", name="Other"))
            await conn.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await conn.execute(play_accounts.insert().values(
                id="play-sentinel", owner_kind="user", owner_id="alice",
                account_kind="wallet", balance_units=12345,
            ))
            if schema_state == "current":
                await conn.execute(cash_accounts.insert(), [
                    {"id": "external", "kind": "clearing", "user_id": None, "reference_id": "mock"},
                    {"id": "alice-wallet", "kind": "available", "user_id": "alice", "reference_id": "alice"},
                    {"id": "bob-wallet", "kind": "available", "user_id": "bob", "reference_id": "bob"},
                    {"id": "alice-seat", "kind": "escrow", "user_id": "alice", "reference_id": "occupancy-1"},
                    {"id": "alice-withdraw", "kind": "withdrawal", "user_id": "alice", "reference_id": "withdrawal-1"},
                ])
                await conn.execute(cash_operators.insert(), [
                    {"id": "operator", "telegram_user_id": 1001, "tenant_id": "tenant", "role": "operator"},
                    {"id": "reviewer", "telegram_user_id": 1002, "tenant_id": "tenant", "role": "reviewer"},
                    {"id": "other-operator", "telegram_user_id": 1003, "tenant_id": "tenant-other", "role": "operator"},
                    {"id": "global-admin", "telegram_user_id": 1004, "tenant_id": None, "role": "admin"},
                ])
        yield factory
    finally:
        if not re.fullmatch(r"cash_test_[0-9a-f]{32}", schema):
            raise RuntimeError("unsafe test schema cleanup target")
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            await engine.dispose()
