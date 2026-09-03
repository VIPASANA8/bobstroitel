"""Model B: store the pservice order UUID on a fiat order."""
from alembic import op
import sqlalchemy as sa

revision = "20260904_0026"
down_revision = "20260903_0025"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("cash_fiat_orders")}
    if "pservice_order_id" not in columns:
        op.add_column("cash_fiat_orders", sa.Column("pservice_order_id", sa.String(64)))
        op.create_unique_constraint(
            "uq_cash_fiat_order_pservice", "cash_fiat_orders", ["pservice_order_id"],
        )


def downgrade():
    bind = op.get_bind()
    live = bind.execute(sa.text(
        "SELECT count(*) FROM cash_fiat_orders WHERE pservice_order_id IS NOT NULL"
    )).scalar()
    if live:
        raise RuntimeError(
            f"Refusing to drop pservice_order_id: {live} order(s) already carry one"
        )
    if "uq_cash_fiat_order_pservice" in {
        c["name"] for c in sa.inspect(bind).get_unique_constraints("cash_fiat_orders")
    }:
        op.drop_constraint("uq_cash_fiat_order_pservice", "cash_fiat_orders", type_="unique")
    op.drop_column("cash_fiat_orders", "pservice_order_id")
