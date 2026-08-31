"""Add cash accounting tables without enabling cash operations."""
from alembic import op
import sqlalchemy as sa

revision = "20260831_0014"
down_revision = "20260831_0013"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "cash_accounts" not in tables:
        op.create_table(
            "cash_accounts",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id")),
            sa.Column("reference_id", sa.String(100), nullable=False),
            sa.Column("balance_micros", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("kind", "reference_id", name="uq_cash_account_reference"),
            sa.CheckConstraint("kind IN ('available', 'escrow', 'withdrawal', 'clearing')", name="ck_cash_account_kind"),
            sa.CheckConstraint("(kind = 'clearing' AND user_id IS NULL) OR (kind <> 'clearing' AND user_id IS NOT NULL)", name="ck_cash_account_owner"),
            sa.CheckConstraint("kind = 'clearing' OR balance_micros >= 0", name="ck_cash_nonnegative"),
        )
    if "cash_transactions" not in tables:
        op.create_table(
            "cash_transactions",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("scope", sa.String(64), nullable=False),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("reference_id", sa.String(100), nullable=False),
            sa.Column("actor", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("scope", "idempotency_key", name="uq_cash_transaction_key"),
            sa.CheckConstraint("kind IN ('deposit', 'reserve', 'release', 'settlement', 'payout', 'adjustment')", name="ck_cash_transaction_kind"),
        )
    if "cash_entries" not in tables:
        op.create_table(
            "cash_entries",
            sa.Column("transaction_id", sa.String(32), sa.ForeignKey("cash_transactions.id"), primary_key=True),
            sa.Column("account_id", sa.String(64), sa.ForeignKey("cash_accounts.id"), primary_key=True),
            sa.Column("amount_micros", sa.BIGINT(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("amount_micros <> 0", name="ck_cash_nonzero_entry"),
        )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("cash_entries")}
    if "ix_cash_entries_account" not in indexes:
        op.create_index("ix_cash_entries_account", "cash_entries", ["account_id"])


def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    names = ("cash_entries", "cash_transactions", "cash_accounts")
    for name in names:
        if name in tables and op.get_bind().execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1')).first():
            raise RuntimeError("Refusing to delete cash data; disable the feature and keep its journal")
    for name in names:
        if name in tables:
            op.drop_table(name)
