"""Hold a CASH account by hand, and remember who confirmed a payment."""
from alembic import op
import sqlalchemy as sa

revision = "20260902_0020"
down_revision = "20260902_0019"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "cash_user_holds" not in tables:
        op.create_table(
            "cash_user_holds",
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("operator_id", sa.String(64), sa.ForeignKey("cash_operators.id"), nullable=False),
            sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "cash_fiat_orders" in tables:
        columns = {column["name"] for column in inspector.get_columns("cash_fiat_orders")}
        if "user_confirmed" not in columns:
            op.add_column("cash_fiat_orders", sa.Column(
                "user_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false"),
            ))


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "cash_user_holds" in tables:
        if bind.dialect.name == "postgresql":
            bind.execute(sa.text("LOCK TABLE cash_user_holds IN ACCESS EXCLUSIVE MODE"))
        if bind.execute(sa.text("SELECT 1 FROM cash_user_holds LIMIT 1")).first():
            raise RuntimeError("Refusing to release held CASH accounts")
        op.drop_table("cash_user_holds")
    if "cash_fiat_orders" in tables:
        op.drop_column("cash_fiat_orders", "user_confirmed")
