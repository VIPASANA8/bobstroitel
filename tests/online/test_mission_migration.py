"""Upgrade real historical mission tables, not the current create_all schema."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


config = Config()
config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
scripts = ScriptDirectory.from_config(config)
DATABASES = ["sqlite+aiosqlite://"]
if os.environ.get("POKER8_TEST_DATABASE_URL"):
    DATABASES.append(os.environ["POKER8_TEST_DATABASE_URL"])


@pytest.fixture
def anyio_backend():
    return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}


def migrate(connection, revision, direction="upgrade"):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(scripts.get_revision(revision).module, direction)()


def historical_schema(connection):
    # 0001 imports today's metadata, so explicitly provide its prerequisites
    # and let the historical progression migrations create their own tables.
    with Operations.context(MigrationContext.configure(connection)) as op:
        op.create_table(
            "users", sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("hands_played", sa.Integer(), nullable=False, server_default="0"),
        )
        for table in ("system_players", "poker_tables", "table_seats"):
            op.create_table(table, sa.Column("id", sa.String(64), primary_key=True))
    for revision in ("20260831_0008", "20260831_0009", "20260831_0010", "20260831_0011"):
        migrate(connection, revision)
    connection.execute(sa.text("INSERT INTO users (id) VALUES ('alice'), ('bob')"))
    connection.execute(sa.text("""
        INSERT INTO user_missions (user_id, day, slot, reroll_offset, progress, completed_at)
        VALUES
        ('alice', '2026-08-30', 'volume', 1, 12, NULL),
        ('alice', '2026-08-30', 'session', 2, 2, '2026-08-30 12:00:00'),
        ('alice', '2026-08-30', 'variety', 1, 4, '2026-08-30 12:00:00'),
        ('alice', '2026-08-31', 'volume', 0, 8, NULL),
        ('bob', '2026-08-30', 'session', 0, 1, NULL)
    """))
    connection.execute(sa.text("""
        INSERT INTO user_progression (user_id, xp) VALUES ('alice', 115)
    """))
    connection.execute(sa.text("""
        INSERT INTO xp_events (id, user_id, amount, source, reference, idempotency_key)
        VALUES ('paid-session', 'alice', 55, 'mission', 'session', 'paid-session'),
               ('paid-variety', 'alice', 60, 'mission', 'variety', 'paid-variety')
    """))


@pytest.fixture(params=DATABASES, ids=lambda url: url.split(":")[0])
async def historical_connection(request):
    engine = create_async_engine(request.param, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                if connection.dialect.name == "postgresql":
                    schema = "mission_migration_" + uuid4().hex
                    await connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
                    await connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(historical_schema)
                yield connection
                await connection.rollback()
    finally:
        await engine.dispose()


def snapshot(connection):
    return {
        "missions": connection.execute(sa.text("""
            SELECT user_id, day, slot, reroll_offset, progress, completed_at, updated_at
            FROM user_missions ORDER BY user_id, day, slot
        """)).all(),
        "xp": connection.execute(sa.text("SELECT * FROM xp_events ORDER BY id")).all(),
        "progression": connection.execute(sa.text("SELECT * FROM user_progression ORDER BY user_id")).all(),
        "days": connection.execute(sa.text("SELECT * FROM progress_days")).all(),
    }


@pytest.mark.anyio
async def test_0012_preserves_legacy_mission_choices(historical_connection):
    def check(connection):
        before = snapshot(connection)
        migrate(connection, "20260831_0012")
        assert snapshot(connection) == before

    await historical_connection.run_sync(check)


def check_quota(connection):
    claims = connection.execute(sa.text("""
        SELECT user_id, day, COUNT(*) FROM user_missions WHERE reroll_claimed
        GROUP BY user_id, day
    """)).all()
    assert claims == [("alice", "2026-08-30", 1)]
    assert connection.execute(sa.text("""
        SELECT COUNT(*) FROM user_missions WHERE reroll_offset <> 0
    """)).scalar_one() >= 1
    # The quota index protects a day even when the other mission already has
    # a legacy offset. Only the new flag participates in uniqueness.
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.execute(sa.text("""
                UPDATE user_missions SET reroll_claimed = true
                WHERE user_id = 'alice' AND day = '2026-08-30' AND NOT reroll_claimed
            """))
    connection.execute(sa.text("""
        UPDATE user_missions SET reroll_claimed = true, reroll_offset = 1
        WHERE user_id = 'alice' AND day = '2026-08-31'
    """))
    connection.execute(sa.text("""
        UPDATE user_missions SET reroll_claimed = true, reroll_offset = 1
        WHERE user_id = 'bob' AND day = '2026-08-30'
    """))


@pytest.mark.anyio
async def test_fresh_upgrade_preserves_choices_and_enforces_quota(historical_connection):
    def check(connection):
        before = snapshot(connection)
        migrate(connection, "20260831_0012")
        migrate(connection, "20260831_0013")
        assert snapshot(connection) == before
        assert connection.execute(sa.text("""
            SELECT COUNT(*) FROM user_missions WHERE reroll_offset <> 0
        """)).scalar_one() == 3
        # A repeated upgrade cannot rewrite choices or create missing rows.
        migrate(connection, "20260831_0013")
        assert snapshot(connection) == before
        check_quota(connection)

    await historical_connection.run_sync(check)


@pytest.mark.anyio
async def test_forward_upgrade_from_applied_old_0012(historical_connection):
    def check(connection):
        # Reproduce the shipped migration's destructive state and old index.
        # A forward upgrade cannot guess the erased offsets back into being.
        connection.execute(sa.text("""
            UPDATE user_missions SET reroll_offset = 0
            WHERE reroll_offset <> 0 AND slot <> (
                SELECT MAX(kept.slot) FROM user_missions AS kept
                WHERE kept.user_id = user_missions.user_id
                  AND kept.day = user_missions.day AND kept.reroll_offset <> 0
            )
        """))
        connection.execute(sa.text("""
            CREATE UNIQUE INDEX uq_user_missions_daily_reroll
            ON user_missions (user_id, day) WHERE reroll_offset <> 0
        """))
        before = snapshot(connection)
        migrate(connection, "20260831_0013")
        assert snapshot(connection) == before
        # Existing offsets can coexist once the index only guards the claim.
        connection.execute(sa.text("""
            UPDATE user_missions SET reroll_offset = 2
            WHERE user_id = 'alice' AND day = '2026-08-30' AND slot = 'session'
        """))
        check_quota(connection)
        before_downgrade = snapshot(connection)
        migrate(connection, "20260831_0013", "downgrade")
        migrate(connection, "20260831_0012", "downgrade")
        assert snapshot(connection) == before_downgrade
        assert "reroll_claimed" not in {
            column["name"] for column in sa.inspect(connection).get_columns("user_missions")
        }
        migrate(connection, "20260831_0012")
        migrate(connection, "20260831_0013")
        assert snapshot(connection) == before_downgrade

    await historical_connection.run_sync(check)
