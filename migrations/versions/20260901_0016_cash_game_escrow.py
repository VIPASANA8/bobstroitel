"""Add exact CASH table parameters, seat escrow and hand amounts."""

from alembic import op
import sqlalchemy as sa

revision = "20260901_0016"
down_revision = "20260901_0015"
branch_labels = None
depends_on = None


def _columns(table):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table):
    return {check["name"] for check in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _foreign_keys(table):
    return {fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys(table)}


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "poker_tables" in tables:
        for name in ("small_blind_micros", "big_blind_micros", "chip_micros"):
            if name not in _columns("poker_tables"):
                op.add_column("poker_tables", sa.Column(name, sa.BigInteger(), nullable=True))

    if "table_seats" in tables:
        if "cash_escrow_account_id" not in _columns("table_seats"):
            op.add_column("table_seats", sa.Column("cash_escrow_account_id", sa.String(64)))
        if "stack_micros" not in _columns("table_seats"):
            op.add_column("table_seats", sa.Column(
                "stack_micros", sa.BigInteger(), nullable=False, server_default=sa.text("0"),
            ))
        if "fk_table_seats_cash_escrow" not in _foreign_keys("table_seats"):
            op.create_foreign_key(
                "fk_table_seats_cash_escrow", "table_seats", "cash_accounts",
                ["cash_escrow_account_id"], ["id"],
            )
        if "ck_table_seats_cash_stack_nonnegative" not in _checks("table_seats"):
            op.create_check_constraint(
                "ck_table_seats_cash_stack_nonnegative", "table_seats", "stack_micros >= 0",
            )
        if "ck_table_seats_one_escrow" not in _checks("table_seats"):
            op.create_check_constraint(
                "ck_table_seats_one_escrow", "table_seats",
                "NOT (escrow_account_id IS NOT NULL AND cash_escrow_account_id IS NOT NULL)",
            )

    if "hand_players" in tables:
        if not sa.inspect(bind).get_columns("hand_players"):
            return
        if not next(
            column["nullable"] for column in sa.inspect(bind).get_columns("hand_players")
            if column["name"] == "start_stack_units"
        ):
            op.alter_column("hand_players", "start_stack_units", existing_type=sa.BigInteger(), nullable=True)
        for name in ("start_stack_micros", "end_stack_micros", "net_micros"):
            if name not in _columns("hand_players"):
                op.add_column("hand_players", sa.Column(name, sa.BigInteger(), nullable=True))
        if "cash_escrow_account_id" not in _columns("hand_players"):
            op.add_column("hand_players", sa.Column("cash_escrow_account_id", sa.String(64)))
        if "fk_hand_players_cash_escrow" not in _foreign_keys("hand_players"):
            op.create_foreign_key(
                "fk_hand_players_cash_escrow", "hand_players", "cash_accounts",
                ["cash_escrow_account_id"], ["id"],
            )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if bind.dialect.name == "postgresql":
        for table in ("hand_players", "table_seats", "poker_tables"):
            if table in tables:
                bind.execute(sa.text(f'LOCK TABLE "{table}" IN ACCESS EXCLUSIVE MODE'))
    if "table_seats" in tables and "cash_escrow_account_id" in _columns("table_seats"):
        if bind.execute(sa.text(
            "SELECT 1 FROM table_seats WHERE cash_escrow_account_id IS NOT NULL OR stack_micros <> 0 LIMIT 1"
        )).first():
            raise RuntimeError("Refusing to remove CASH game schema while CASH seats exist")
    if "hand_players" in tables and "start_stack_micros" in _columns("hand_players"):
        if bind.execute(sa.text(
            "SELECT 1 FROM hand_players WHERE start_stack_micros IS NOT NULL LIMIT 1"
        )).first():
            raise RuntimeError("Refusing to remove CASH game schema while CASH hands exist")

    if "hand_players" in tables:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("hand_players") as batch:
                for name in ("cash_escrow_account_id", "start_stack_micros", "end_stack_micros", "net_micros"):
                    if name in _columns("hand_players"):
                        batch.drop_column(name)
                batch.alter_column("start_stack_units", existing_type=sa.BigInteger(), nullable=False)
        else:
            if "fk_hand_players_cash_escrow" in _foreign_keys("hand_players"):
                op.drop_constraint("fk_hand_players_cash_escrow", "hand_players", type_="foreignkey")
            for name in ("cash_escrow_account_id", "start_stack_micros", "end_stack_micros", "net_micros"):
                if name in _columns("hand_players"):
                    op.drop_column("hand_players", name)
            op.alter_column("hand_players", "start_stack_units", existing_type=sa.BigInteger(), nullable=False)

    if "table_seats" in tables:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("table_seats") as batch:
                for check in ("ck_table_seats_one_escrow", "ck_table_seats_cash_stack_nonnegative"):
                    if check in _checks("table_seats"):
                        batch.drop_constraint(check, type_="check")
                for name in ("cash_escrow_account_id", "stack_micros"):
                    if name in _columns("table_seats"):
                        batch.drop_column(name)
        else:
            for constraint, kind in (
                ("fk_table_seats_cash_escrow", "foreignkey"),
                ("ck_table_seats_one_escrow", "check"),
                ("ck_table_seats_cash_stack_nonnegative", "check"),
            ):
                present = _foreign_keys("table_seats") if kind == "foreignkey" else _checks("table_seats")
                if constraint in present:
                    op.drop_constraint(constraint, "table_seats", type_=kind)
            for name in ("cash_escrow_account_id", "stack_micros"):
                if name in _columns("table_seats"):
                    op.drop_column("table_seats", name)

    if "poker_tables" in tables:
        for name in ("small_blind_micros", "big_blind_micros", "chip_micros"):
            if name in _columns("poker_tables"):
                op.drop_column("poker_tables", name)
