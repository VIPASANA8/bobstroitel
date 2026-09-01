"""Add scoped CASH operators and immutable decision audit."""
from alembic import op
import sqlalchemy as sa

revision = "20260901_0018"
down_revision = "20260901_0017"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def _checks(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "cash_operators" not in tables:
        op.create_table(
            "cash_operators",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("telegram_user_id", sa.BIGINT(), nullable=False, unique=True),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id")),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("role IN ('reviewer','operator','admin')", name="ck_cash_operator_role"),
            sa.CheckConstraint("role = 'admin' OR tenant_id IS NOT NULL", name="ck_cash_operator_scope"),
        )
    if "cash_audit_events" not in tables:
        op.create_table(
            "cash_audit_events",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("operator_id", sa.String(64), sa.ForeignKey("cash_operators.id"), nullable=False),
            sa.Column("actor_telegram_user_id", sa.BIGINT(), nullable=False),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id")),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("target_type", sa.String(32), nullable=False),
            sa.Column("target_id", sa.String(64), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("before_json", sa.JSON(), nullable=False),
            sa.Column("after_json", sa.JSON(), nullable=False),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("operator_id", "idempotency_key", name="uq_cash_audit_operator_key"),
            sa.CheckConstraint("length(reason) >= 3", name="ck_cash_audit_reason"),
        )
        op.create_index("ix_cash_audit_tenant_time", "cash_audit_events", ["tenant_id", "created_at"])
    if "cash_payment_events" in tables:
        if "ck_cash_payment_event_status" in _checks("cash_payment_events"):
            op.drop_constraint("ck_cash_payment_event_status", "cash_payment_events", type_="check")
        op.create_check_constraint(
            "ck_cash_payment_event_status", "cash_payment_events",
            "status IN ('observed','processed','review_required','resolved_credited','resolved_rejected')",
        )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    targets = [name for name in ("cash_audit_events", "cash_operators") if name in tables]
    if bind.dialect.name == "postgresql" and targets:
        bind.execute(sa.text("LOCK TABLE " + ", ".join(f'\"{name}\"' for name in targets) + " IN ACCESS EXCLUSIVE MODE"))
    for name in targets:
        if bind.execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1')).first():
            raise RuntimeError("Refusing to delete CASH operator audit or roles")
    if "cash_payment_events" in tables:
        if bind.execute(sa.text(
            "SELECT 1 FROM cash_payment_events WHERE status LIKE 'resolved_%' LIMIT 1"
        )).first():
            raise RuntimeError("Refusing to remove resolved payment review history")
        if "ck_cash_payment_event_status" in _checks("cash_payment_events"):
            op.drop_constraint("ck_cash_payment_event_status", "cash_payment_events", type_="check")
        op.create_check_constraint(
            "ck_cash_payment_event_status", "cash_payment_events",
            "status IN ('observed','processed','review_required')",
        )
    for name in targets:
        op.drop_table(name)
