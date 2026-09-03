"""Raise the CASH stakes to 0.05/0.10 and give a table a rake."""
from alembic import op
import sqlalchemy as sa

revision = "20260903_0021"
down_revision = "20260902_0020"
branch_labels = None
depends_on = None

CASH_TABLE = "cash-micro-test"

OLD = {"small_blind_units": 1, "big_blind_units": 2,
       "small_blind_micros": 10_000, "big_blind_micros": 20_000, "rake_bps": 0}
NEW = {"small_blind_units": 5, "big_blind_units": 10,
       "small_blind_micros": 50_000, "big_blind_micros": 100_000, "rake_bps": 1_000}


def _assert_table_is_idle(bind) -> None:
    """Blinds may not move under a seated player, and money may not be stranded.

    Changing the big blind rewrites the buy-in bounds, so a stack bought in at
    the old table would be inside the new limits only by accident. Refusing is
    the whole point: an operator empties the table first.
    """
    seated = bind.execute(sa.text(
        "SELECT 1 FROM table_seats WHERE table_id = :t AND state <> 'empty' LIMIT 1"
    ), {"t": CASH_TABLE}).first()
    if seated:
        raise RuntimeError(
            f"Refusing to change the stakes of {CASH_TABLE} while a seat is taken"
        )
    held = bind.execute(sa.text(
        "SELECT 1 FROM cash_accounts WHERE kind = 'escrow' AND balance_micros <> 0 LIMIT 1"
    )).first()
    if held:
        raise RuntimeError("Refusing to change the stakes while a CASH escrow holds money")


def _move(bind, values: dict) -> None:
    bind.execute(sa.text(
        "UPDATE poker_tables SET small_blind_units = :sbu, big_blind_units = :bbu,"
        " small_blind_micros = :sbm, big_blind_micros = :bbm, rake_bps = :rake"
        " WHERE id = :t"
    ), {"sbu": values["small_blind_units"], "bbu": values["big_blind_units"],
        "sbm": values["small_blind_micros"], "bbm": values["big_blind_micros"],
        "rake": values["rake_bps"], "t": CASH_TABLE})


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "rake_bps" not in {column["name"] for column in inspector.get_columns("poker_tables")}:
        op.add_column("poker_tables", sa.Column(
            "rake_bps", sa.Integer(), nullable=False, server_default=sa.text("0"),
        ))
    if bind.execute(sa.text("SELECT 1 FROM poker_tables WHERE id = :t"), {"t": CASH_TABLE}).first():
        _assert_table_is_idle(bind)
        _move(bind, NEW)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.execute(sa.text("SELECT 1 FROM poker_tables WHERE id = :t"), {"t": CASH_TABLE}).first():
        _assert_table_is_idle(bind)
        _move(bind, OLD)
    if "rake_bps" in {column["name"] for column in inspector.get_columns("poker_tables")}:
        op.drop_column("poker_tables", "rake_bps")
