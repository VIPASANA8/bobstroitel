"""Add durable CASE8-compatible RUB P2P orders and event cursor."""
from alembic import op
import sqlalchemy as sa

revision = "20260902_0019"
down_revision = "20260901_0018"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "cash_fiat_orders" not in tables:
        op.create_table(
            "cash_fiat_orders",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("request_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("partner_order_id", sa.BIGINT(), unique=True),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("requested_micros", sa.BIGINT(), nullable=False),
            sa.Column("fiat_amount", sa.BIGINT()),
            sa.Column("requisites", sa.String(500)),
            sa.Column("trader_username", sa.String(100)),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("detail", sa.String(500)),
            sa.Column("expires_at", TS),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "request_key", name="uq_cash_fiat_order_request"),
            sa.CheckConstraint("currency = 'RUB'", name="ck_cash_fiat_order_currency"),
            sa.CheckConstraint("requested_micros BETWEEN 20000000 AND 1000000000", name="ck_cash_fiat_order_amount"),
            sa.CheckConstraint(
                "status IN ('requesting','unavailable','awaiting_user','waiting_trader','clarifying','credited','expired','cancelled','review_required')",
                name="ck_cash_fiat_order_status",
            ),
        )
    if "cash_fiat_events" not in tables:
        op.create_table(
            "cash_fiat_events",
            sa.Column("provider", sa.String(32), primary_key=True),
            sa.Column("event_id", sa.BIGINT(), primary_key=True),
            sa.Column("partner_order_id", sa.BIGINT(), nullable=False),
            sa.Column("fiat_order_id", sa.String(64), sa.ForeignKey("cash_fiat_orders.id")),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("detail", sa.String(500)),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("processed_at", TS),
            sa.CheckConstraint("status IN ('observed','processed','review_required')", name="ck_cash_fiat_event_status"),
        )
    if "cash_partner_cursors" not in tables:
        op.create_table(
            "cash_partner_cursors",
            sa.Column("provider", sa.String(32), primary_key=True),
            sa.Column("offset", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("offset >= 0", name="ck_cash_partner_cursor_offset"),
        )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    names = [name for name in ("cash_fiat_events", "cash_partner_cursors", "cash_fiat_orders") if name in tables]
    if bind.dialect.name == "postgresql" and names:
        bind.execute(sa.text("LOCK TABLE " + ", ".join(f'\"{name}\"' for name in names) + " IN ACCESS EXCLUSIVE MODE"))
    for name in names:
        if bind.execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1')).first():
            raise RuntimeError("Refusing to delete fiat P2P history or cursor")
    for name in names:
        op.drop_table(name)
