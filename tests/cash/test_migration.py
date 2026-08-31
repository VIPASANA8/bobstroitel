from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

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
