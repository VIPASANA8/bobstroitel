from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from online.schema import auth_sessions, metadata, poker_tables

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


def migrate(conn, direction):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    module = ScriptDirectory.from_config(config).get_revision("20260901_0015").module
    with Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


async def test_table_asset_and_auth_method_backfill_are_repeatable(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(poker_tables.insert().values(
                id="custom-room", scope="network", asset="PLAY", name="Legacy Room",
                small_blind_units=50, big_blind_units=100,
                min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            now = datetime.now(timezone.utc)
            await session.execute(auth_sessions.insert().values(
                id="legacy-session", user_id="alice", tenant_id="tenant",
                token_hash="a" * 64, auth_method="legacy", expires_at=now + timedelta(hours=1),
            ))
            await session.execute(sa.text("ALTER TABLE poker_tables DROP COLUMN asset CASCADE"))
            await session.execute(sa.text("ALTER TABLE auth_sessions DROP COLUMN auth_method CASCADE"))
            conn = await session.connection()
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            assert await session.scalar(sa.text("SELECT asset FROM poker_tables WHERE id='custom-room'")) == "PLAY"
            assert await session.scalar(sa.text("SELECT auth_method FROM auth_sessions WHERE id='legacy-session'")) == "legacy"
            checks = await conn.run_sync(lambda sync: {
                table: {row["name"] for row in sa.inspect(sync).get_check_constraints(table)}
                for table in ("poker_tables", "auth_sessions")
            })
            assert "ck_poker_tables_asset" in checks["poker_tables"]
            assert "ck_auth_sessions_method" in checks["auth_sessions"]
            with pytest.raises(sa.exc.DBAPIError, match="table asset is immutable"):
                async with session.begin_nested():
                    await session.execute(sa.text(
                        "UPDATE poker_tables SET asset='CASH_USDT' WHERE id='custom-room'"
                    ))
            assert await session.scalar(sa.text(
                "SELECT asset FROM poker_tables WHERE id='custom-room'"
            )) == "PLAY"
            await session.execute(sa.text("""
                INSERT INTO poker_tables (
                    id, scope, asset, name, small_blind_units, big_blind_units,
                    min_buy_in_bb, max_buy_in_bb, max_seats
                ) VALUES (
                    'cash-room', 'network', 'CASH_USDT', 'Cash Room', 1000, 2000,
                    40, 100, 6
                )
            """))
            with pytest.raises(RuntimeError, match="CASH tables exist"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            assert await session.scalar(sa.text(
                "SELECT asset FROM poker_tables WHERE id='cash-room'"
            )) == "CASH_USDT"
            await session.execute(sa.text("DELETE FROM poker_tables WHERE id='cash-room'"))
            await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            columns = await conn.run_sync(lambda sync: {
                table: {row["name"] for row in sa.inspect(sync).get_columns(table)}
                for table in ("poker_tables", "auth_sessions")
            })
            assert "asset" not in columns["poker_tables"]
            assert "auth_method" not in columns["auth_sessions"]


async def test_fresh_metadata_and_migration_definitions_match(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            def differences(sync):
                selected = {"poker_tables", "auth_sessions"}
                new_checks = {"ck_poker_tables_asset", "ck_auth_sessions_method"}
                def include(obj, name, type_, reflected, compare_to):
                    if type_ == "table":
                        return name in selected
                    if type_ == "check_constraint":
                        return name in new_checks
                    table = getattr(obj, "table", None)
                    return table is None or table.name in selected
                context = MigrationContext.configure(sync, opts={
                    "include_object": include,
                    "compare_server_default": True,
                })
                return compare_metadata(context, metadata)
            assert await conn.run_sync(differences) == []
