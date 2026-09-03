"""Raise the withdrawal ceiling to match the C2C deposit one."""
from alembic import op
import sqlalchemy as sa

revision = "20260903_0023"
down_revision = "20260903_0022"
branch_labels = None
depends_on = None

CEILING = 100_000_000_000  # 100_000 USDT, the same bound C2C deposits use.
OLD_CEILING = 100_000_000
NAME = "ck_cash_withdrawal_amount"


def _swap(ceiling):
    op.drop_constraint(NAME, "cash_withdrawals", type_="check")
    op.create_check_constraint(NAME, "cash_withdrawals", f"amount_micros BETWEEN 10000 AND {ceiling}")


def upgrade():
    _swap(CEILING)


def downgrade():
    over = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM cash_withdrawals WHERE amount_micros > :ceiling"
    ), {"ceiling": OLD_CEILING}).scalar()
    if over:
        raise RuntimeError(
            f"Refusing to restore the withdrawal cap: {over} withdrawal(s) above "
            f"{OLD_CEILING // 1_000_000} USDT already exist"
        )
    _swap(OLD_CEILING)
