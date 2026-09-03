"""Pilot deposit limits: RUB narrows to 20-300 USDT, C2C stops being capped."""
from alembic import op
import sqlalchemy as sa

revision = "20260903_0022"
down_revision = "20260903_0021"
branch_labels = None
depends_on = None

C2C_CEILING = 100_000_000_000  # 100_000 USDT: the uniqueness nudge needs a finite range.
OLD_C2C_CEILING = 100_000_000
RUB_CEILING = 300_000_000
OLD_RUB_CEILING = 500_000_000


def _swap(table, name, condition):
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, condition)


def _rub_orders_above(bind, ceiling):
    return bind.execute(sa.text(
        "SELECT count(*) FROM cash_fiat_orders WHERE requested_micros > :ceiling"
    ), {"ceiling": ceiling}).scalar()


def upgrade():
    bind = op.get_bind()
    # Narrowing a money bound can orphan rows that were legal when written.
    # Refusing beats a half-applied constraint an operator finds later.
    stale = _rub_orders_above(bind, RUB_CEILING)
    if stale:
        raise RuntimeError(
            f"Refusing to narrow the RUB deposit ceiling: {stale} order(s) above "
            f"{RUB_CEILING // 1_000_000} USDT already exist"
        )
    _swap("cash_fiat_orders", "ck_cash_fiat_order_amount",
          f"requested_micros BETWEEN 20000000 AND {RUB_CEILING}")
    _swap("cash_deposits", "ck_cash_deposit_requested",
          f"requested_micros BETWEEN 1000000 AND {C2C_CEILING}")
    _swap("cash_deposits", "ck_cash_deposit_expected",
          f"expected_micros BETWEEN requested_micros AND {C2C_CEILING}")


def downgrade():
    bind = op.get_bind()
    over = bind.execute(sa.text(
        "SELECT count(*) FROM cash_deposits WHERE requested_micros > :ceiling"
    ), {"ceiling": OLD_C2C_CEILING}).scalar()
    if over:
        raise RuntimeError(
            f"Refusing to restore the C2C cap: {over} deposit(s) above "
            f"{OLD_C2C_CEILING // 1_000_000} USDT already exist"
        )
    _swap("cash_deposits", "ck_cash_deposit_expected",
          f"expected_micros BETWEEN requested_micros AND {OLD_C2C_CEILING}")
    _swap("cash_deposits", "ck_cash_deposit_requested",
          f"requested_micros BETWEEN 1000000 AND {OLD_C2C_CEILING}")
    _swap("cash_fiat_orders", "ck_cash_fiat_order_amount",
          f"requested_micros BETWEEN 20000000 AND {OLD_RUB_CEILING}")
