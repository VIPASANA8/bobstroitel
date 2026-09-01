"""Add durable mock C2C deposit and withdrawal workflows."""
from alembic import op
import sqlalchemy as sa

revision = "20260901_0017"
down_revision = "20260901_0016"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "cash_deposits" not in tables:
        op.create_table(
            "cash_deposits",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("request_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("network", sa.String(16), nullable=False),
            sa.Column("token_contract", sa.String(128), nullable=False),
            sa.Column("destination_address", sa.String(128), nullable=False),
            sa.Column("requested_micros", sa.BIGINT(), nullable=False),
            sa.Column("expected_micros", sa.BIGINT(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("expires_at", TS, nullable=False),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "request_key", name="uq_cash_deposit_request"),
            sa.UniqueConstraint("destination_address", "expected_micros", name="uq_cash_deposit_amount"),
            sa.CheckConstraint("requested_micros BETWEEN 1000000 AND 100000000", name="ck_cash_deposit_requested"),
            sa.CheckConstraint("expected_micros BETWEEN requested_micros AND 100000000", name="ck_cash_deposit_expected"),
            sa.CheckConstraint("status IN ('created','awaiting_transfer','confirmed','credited','expired','cancelled','review_required')", name="ck_cash_deposit_status"),
        )
    if "cash_payment_events" not in tables:
        op.create_table(
            "cash_payment_events",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("external_event_id", sa.String(200), nullable=False),
            sa.Column("event_hash", sa.String(64), nullable=False),
            sa.Column("tx_hash", sa.String(128), nullable=False),
            sa.Column("event_index", sa.Integer(), nullable=False),
            sa.Column("network", sa.String(16), nullable=False),
            sa.Column("token_contract", sa.String(128), nullable=False),
            sa.Column("destination_address", sa.String(128), nullable=False),
            sa.Column("amount_micros", sa.BIGINT(), nullable=False),
            sa.Column("occurred_at", TS, nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("deposit_id", sa.String(64), sa.ForeignKey("cash_deposits.id")),
            sa.Column("detail_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("processed_at", TS),
            sa.UniqueConstraint("provider", "external_event_id", name="uq_cash_payment_event_external"),
            sa.UniqueConstraint("provider", "tx_hash", "event_index", name="uq_cash_payment_event_chain"),
            sa.CheckConstraint("amount_micros > 0", name="ck_cash_payment_event_amount"),
            sa.CheckConstraint("status IN ('observed','processed','review_required')", name="ck_cash_payment_event_status"),
        )
    if "cash_withdrawals" not in tables:
        op.create_table(
            "cash_withdrawals",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("request_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("network", sa.String(16), nullable=False),
            sa.Column("destination_address", sa.String(128), nullable=False),
            sa.Column("amount_micros", sa.BIGINT(), nullable=False),
            sa.Column("fee_micros", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("reserve_account_id", sa.String(64), sa.ForeignKey("cash_accounts.id"), nullable=False),
            sa.Column("payout_id", sa.String(64), nullable=False, unique=True),
            sa.Column("tx_hash", sa.String(128)),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("detail", sa.String(500)),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("submitted_at", TS),
            sa.Column("confirmed_at", TS),
            sa.UniqueConstraint("user_id", "request_key", name="uq_cash_withdrawal_request"),
            sa.CheckConstraint("amount_micros BETWEEN 10000 AND 100000000", name="ck_cash_withdrawal_amount"),
            sa.CheckConstraint("fee_micros >= 0", name="ck_cash_withdrawal_fee"),
            sa.CheckConstraint("status IN ('requested','reserved','approved','sending','submitted','confirmed','rejected','cancelled','unknown')", name="ck_cash_withdrawal_status"),
        )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    names = [name for name in ("cash_payment_events", "cash_withdrawals", "cash_deposits") if name in tables]
    if bind.dialect.name == "postgresql" and names:
        bind.execute(sa.text("LOCK TABLE " + ", ".join(f'\"{name}\"' for name in names) + " IN ACCESS EXCLUSIVE MODE"))
    for name in names:
        if bind.execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1')).first():
            raise RuntimeError("Refusing to delete C2C payment history")
    for name in names:
        op.drop_table(name)
