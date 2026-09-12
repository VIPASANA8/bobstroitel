"""The RUB rate an operator sets, and the RUB a P2P withdrawal was quoted at.

A player withdrawing to a card is promised roubles, not USDT, so the rate has
to exist before the form can say a number. It is a dated row, not a setting:
the quote on every withdrawal is what the rate was when the player pressed the
button, and a later rate change must not move it.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0032"
down_revision = "20260907_0031"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "cash_rub_rates" not in inspector.get_table_names():
        op.create_table(
            "cash_rub_rates",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("kopecks_per_usdt", sa.BIGINT, nullable=False),
            sa.Column("note", sa.String(200)),
            sa.Column("actor", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("kopecks_per_usdt > 0", name="ck_cash_rub_rate_positive"),
        )
        op.create_index("ix_cash_rub_rates_created", "cash_rub_rates", ["created_at"])
    columns = {column["name"] for column in inspector.get_columns("cash_withdrawals")}
    if "quote_kopecks" not in columns:
        # NULL on every TRC20 row: a crypto payout is quoted in nothing but itself.
        op.add_column("cash_withdrawals", sa.Column("quote_kopecks", sa.BIGINT))


def downgrade():
    op.drop_column("cash_withdrawals", "quote_kopecks")
    op.drop_index("ix_cash_rub_rates_created", table_name="cash_rub_rates")
    op.drop_table("cash_rub_rates")
