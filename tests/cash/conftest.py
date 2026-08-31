import asyncio
import os
import re
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from online.schema import (
    cash_accounts, metadata, play_accounts, tenants, users,
)


@pytest.fixture
def anyio_backend():
    return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}


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
    ):
        pytest.fail("Refusing a database outside the local postgres_test target")
    schema = "cash_test_" + uuid4().hex
    historical = getattr(request, "param", "current") == "historical"
    engine = create_async_engine(
        url, poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            selected = [tenants, users, play_accounts] if historical else None
            await conn.run_sync(lambda sync: metadata.create_all(sync, tables=selected))
            await conn.execute(tenants.insert().values(id="tenant", slug="cash-test", name="Test"))
            await conn.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await conn.execute(play_accounts.insert().values(
                id="play-sentinel", owner_kind="user", owner_id="alice",
                account_kind="wallet", balance_units=12345,
            ))
            if not historical:
                await conn.execute(cash_accounts.insert(), [
                    {"id": "external", "kind": "clearing", "user_id": None, "reference_id": "mock"},
                    {"id": "alice-wallet", "kind": "available", "user_id": "alice", "reference_id": "alice"},
                    {"id": "bob-wallet", "kind": "available", "user_id": "bob", "reference_id": "bob"},
                    {"id": "alice-seat", "kind": "escrow", "user_id": "alice", "reference_id": "occupancy-1"},
                    {"id": "alice-withdraw", "kind": "withdrawal", "user_id": "alice", "reference_id": "withdrawal-1"},
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
