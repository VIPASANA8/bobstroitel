from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from online.schema import metadata

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


def migrate(conn, direction):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
    module = ScriptDirectory.from_config(config).get_revision("20260901_0016").module
    with Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


async def test_cash_game_schema_upgrade_repeat_and_guarded_downgrade(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            columns = await conn.run_sync(lambda sync: {
                table: {row["name"]: row for row in sa.inspect(sync).get_columns(table)}
                for table in ("poker_tables", "table_seats", "hand_players")
            })
            assert "chip_micros" not in columns["poker_tables"]
            assert "cash_escrow_account_id" not in columns["table_seats"]
            assert columns["hand_players"]["start_stack_units"]["nullable"] is False

            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))
            columns = await conn.run_sync(lambda sync: {
                table: {row["name"]: row for row in sa.inspect(sync).get_columns(table)}
                for table in ("poker_tables", "table_seats", "hand_players")
            })
            assert {"small_blind_micros", "big_blind_micros", "chip_micros"} <= columns["poker_tables"].keys()
            assert {"cash_escrow_account_id", "stack_micros"} <= columns["table_seats"].keys()
            assert columns["hand_players"]["start_stack_units"]["nullable"] is True

            await session.execute(sa.text("""
                INSERT INTO poker_tables (
                    id, scope, asset, name, small_blind_units, big_blind_units,
                    small_blind_micros, big_blind_micros, chip_micros,
                    min_buy_in_bb, max_buy_in_bb, max_seats
                ) VALUES (
                    'cash-migration', 'network', 'CASH_USDT', 'Cash Migration', 0, 0,
                    10000, 20000, 10000, 40, 100, 6
                )
            """))
            await session.execute(sa.text("""
                INSERT INTO table_seats (
                    id, table_id, seat_no, occupant_kind, user_id,
                    cash_escrow_account_id, stack_micros, state
                ) VALUES (
                    'cash-seat-migration', 'cash-migration', 0, 'user', 'alice',
                    'alice-seat', 1, 'seated'
                )
            """))
            with pytest.raises(RuntimeError, match="CASH seats exist"):
                await conn.run_sync(lambda sync: migrate(sync, "downgrade"))
            await session.execute(sa.text("DELETE FROM table_seats WHERE id='cash-seat-migration'"))
            await conn.run_sync(lambda sync: migrate(sync, "downgrade"))


async def test_cash_game_migration_matches_metadata(cash_db):
    async with cash_db() as session:
        async with session.begin():
            conn = await session.connection()
            await conn.run_sync(lambda sync: migrate(sync, "upgrade"))

            def differences(sync):
                selected = {"poker_tables", "table_seats", "hand_players"}
                new_checks = {
                    "ck_table_seats_cash_stack_nonnegative", "ck_table_seats_one_escrow",
                }
                new_fks = {"fk_table_seats_cash_escrow", "fk_hand_players_cash_escrow"}

                def include(obj, name, type_, reflected, compare_to):
                    if type_ == "table":
                        return name in selected
                    if type_ == "check_constraint":
                        return name in new_checks
                    if type_ == "foreign_key_constraint":
                        return name in new_fks
                    table = getattr(obj, "table", None)
                    return table is None or table.name in selected

                context = MigrationContext.configure(sync, opts={
                    "include_object": include,
                    "compare_server_default": True,
                })
                return compare_metadata(context, metadata)

            assert await conn.run_sync(differences) == []
