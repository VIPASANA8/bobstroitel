from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from online.schema import metadata

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


def migrate(conn, direction):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    module = ScriptDirectory.from_config(config).get_revision("20260831_0014").module
    with Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


@pytest.mark.parametrize("cash_db", ["historical"], indirect=True)
async def test_upgrade_preserves_play_and_downgrade_refuses_cash_rows(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            names = await conn.run_sync(lambda sync: set(sa.inspect(sync).get_table_names()))
            assert {"cash_accounts", "cash_transactions", "cash_entries"} <= names
            assert await session.scalar(sa.text("SELECT balance_units FROM play_accounts WHERE id='play-sentinel'")) == 12345
            assert await session.scalar(sa.text("SELECT count(*) FROM cash_accounts")) == 0
            await conn.run_sync(assert_cash_schema_matches_metadata)
            await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            names = await conn.run_sync(lambda sync: set(sa.inspect(sync).get_table_names()))
            assert "cash_accounts" not in names
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            # A fresh install may already contain these tables because historical
            # migration 0001 uses current metadata; this upgrade must tolerate it.
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            await session.execute(sa.text("""
                INSERT INTO cash_accounts (id, kind, reference_id)
                VALUES ('probe', 'clearing', 'mock-probe')
            """))
            with pytest.raises(RuntimeError, match="cash data"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            assert await session.scalar(sa.text("SELECT count(*) FROM cash_accounts")) == 1


def assert_cash_schema_matches_metadata(conn):
    context = MigrationContext.configure(conn, opts={
        "include_object": lambda obj, name, type_, reflected, compare_to:
            type_ != "table" or name.startswith("cash_"),
        "compare_server_default": True,
    })
    assert compare_metadata(context, metadata) == []


@pytest.mark.parametrize("cash_db", ["empty"], indirect=True)
async def test_all_upgrades_on_empty_schema_keep_cash_disabled(cash_db):
    def upgrade_all(conn):
        scripts = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "migrations"))
        with Operations.context(MigrationContext.configure(conn)):
            for revision in reversed(list(scripts.walk_revisions())):
                revision.module.upgrade()
        assert_cash_schema_matches_metadata(conn)

    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(upgrade_all)
            for name in ("cash_accounts", "cash_transactions", "cash_entries"):
                assert await session.scalar(sa.text(f'SELECT count(*) FROM "{name}"')) == 0


async def test_downgrade_blocks_writers_before_checking_for_cash_data(cash_db):
    async with cash_db() as migration_session:
        async with migration_session.begin():
            conn = await migration_session.connection()
            with pytest.raises(RuntimeError, match="cash data"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            # Keep the migration transaction open: a concurrent first deposit
            # must not slip between its empty check and its table drops.
            with pytest.raises(sa.exc.OperationalError) as blocked:
                async with cash_db() as writer:
                    async with writer.begin():
                        await writer.execute(sa.text("SET LOCAL lock_timeout = '200ms'"))
                        await writer.execute(sa.text("""
                            INSERT INTO cash_accounts (id, kind, reference_id)
                            VALUES ('concurrent', 'clearing', 'concurrent')
                        """))
            assert blocked.value.orig.sqlstate == "55P03"
