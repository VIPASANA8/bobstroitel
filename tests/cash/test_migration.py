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


def migrate(conn, direction, revision="20260831_0014"):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    module = ScriptDirectory.from_config(config).get_revision(revision).module
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
            type_ != "table" or name in {"cash_accounts", "cash_transactions", "cash_entries"},
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
            for name in ("cash_accounts", "cash_transactions", "cash_entries", "cash_deposits", "cash_payment_events", "cash_withdrawals", "cash_operators", "cash_audit_events"):
                assert await session.scalar(sa.text(f'SELECT count(*) FROM "{name}"')) == 0


async def test_c2c_downgrade_refuses_payment_history(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await session.execute(sa.text("""
                INSERT INTO cash_deposits
                    (id, user_id, tenant_id, request_key, request_hash, network, token_contract,
                     destination_address, requested_micros, expected_micros, status, expires_at)
                VALUES
                    ('deposit-probe', 'alice', 'tenant', 'probe', repeat('a', 64), 'TRC20',
                     'mock-usdt', 'mock-address', 1000000, 1000000, 'awaiting_transfer', CURRENT_TIMESTAMP)
            """))
            with pytest.raises(RuntimeError, match="payment history"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade", "20260901_0017"))
            assert await session.scalar(sa.text("SELECT count(*) FROM cash_deposits")) == 1


async def test_operator_downgrade_refuses_roles_even_before_first_decision(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            with pytest.raises(RuntimeError, match="audit or roles"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade", "20260901_0018"))
            assert await session.scalar(sa.text("SELECT count(*) FROM cash_operators")) == 4


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
