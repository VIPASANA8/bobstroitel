"""Add server-owned table asset and authentication provenance."""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0015"
down_revision = "20260831_0014"
branch_labels = None
depends_on = None


def _columns(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table):
    return {check["name"] for check in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "poker_tables" in tables:
        if "asset" not in _columns("poker_tables"):
            op.add_column("poker_tables", sa.Column(
                "asset", sa.String(16), nullable=False, server_default=sa.text("'PLAY'"),
            ))
        if "ck_poker_tables_asset" not in _checks("poker_tables"):
            op.create_check_constraint(
                "ck_poker_tables_asset", "poker_tables", "asset IN ('PLAY', 'CASH_USDT')",
            )
        if op.get_bind().dialect.name == "postgresql":
            op.execute("""
                CREATE OR REPLACE FUNCTION poker8_keep_table_asset()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.asset IS DISTINCT FROM OLD.asset THEN
                        RAISE EXCEPTION 'table asset is immutable';
                    END IF;
                    RETURN NEW;
                END;
                $$
            """)
            op.execute("DROP TRIGGER IF EXISTS poker8_keep_table_asset ON poker_tables")
            op.execute("""
                CREATE TRIGGER poker8_keep_table_asset
                BEFORE UPDATE OF asset ON poker_tables
                FOR EACH ROW EXECUTE FUNCTION poker8_keep_table_asset()
            """)
    if "auth_sessions" in tables:
        if "auth_method" not in _columns("auth_sessions"):
            op.add_column("auth_sessions", sa.Column(
                "auth_method", sa.String(16), nullable=False, server_default=sa.text("'legacy'"),
            ))
        if "ck_auth_sessions_method" not in _checks("auth_sessions"):
            op.create_check_constraint(
                "ck_auth_sessions_method", "auth_sessions",
                "auth_method IN ('telegram', 'dev', 'guest', 'legacy')",
            )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "poker_tables" in tables and "asset" in _columns("poker_tables"):
        if bind.dialect.name == "postgresql":
            bind.execute(sa.text('LOCK TABLE "poker_tables" IN ACCESS EXCLUSIVE MODE'))
        if bind.execute(sa.text(
            "SELECT 1 FROM poker_tables WHERE asset='CASH_USDT' LIMIT 1"
        )).first():
            raise RuntimeError("Refusing to remove table asset while CASH tables exist")
    if bind.dialect.name == "postgresql" and "poker_tables" in tables:
        op.execute("DROP TRIGGER IF EXISTS poker8_keep_table_asset ON poker_tables")
        op.execute("DROP FUNCTION IF EXISTS poker8_keep_table_asset()")
    for table, column, constraint in (
        ("auth_sessions", "auth_method", "ck_auth_sessions_method"),
        ("poker_tables", "asset", "ck_poker_tables_asset"),
    ):
        if table not in tables or column not in _columns(table):
            continue
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch:
                if constraint in _checks(table):
                    batch.drop_constraint(constraint, type_="check")
                batch.drop_column(column)
        else:
            if constraint in _checks(table):
                op.drop_constraint(constraint, table, type_="check")
            op.drop_column(table, column)
