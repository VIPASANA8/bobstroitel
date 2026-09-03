"""A second withdrawal rail: RUB P2P, paid by an operator's own hand."""
from alembic import op
import sqlalchemy as sa

revision = "20260903_0024"
down_revision = "20260903_0023"
branch_labels = None
depends_on = None


def _constraints(bind):
    return {item["name"] for item in sa.inspect(bind).get_check_constraints("cash_withdrawals")}


def upgrade():
    bind = op.get_bind()
    # A fresh database gets the table from the metadata, which already carries
    # both constraints; an existing one gets them here. Adding either twice is
    # an error, so both are checked rather than assumed.
    columns = {column["name"] for column in sa.inspect(bind).get_columns("cash_withdrawals")}
    if "fiat_kopecks" not in columns:
        op.add_column("cash_withdrawals", sa.Column("fiat_kopecks", sa.BIGINT()))
    present = _constraints(bind)
    if "ck_cash_withdrawal_fiat" not in present:
        op.create_check_constraint(
            "ck_cash_withdrawal_fiat", "cash_withdrawals",
            "fiat_kopecks IS NULL OR fiat_kopecks > 0",
        )
    # Every existing row is TRC20, so naming the rails now costs nothing and
    # stops a third one from arriving by typo later.
    if "ck_cash_withdrawal_network" not in present:
        op.create_check_constraint(
            "ck_cash_withdrawal_network", "cash_withdrawals",
            "network IN ('TRC20', 'P2P_RUB')",
        )


def downgrade():
    bind = op.get_bind()
    paid = bind.execute(sa.text(
        "SELECT count(*) FROM cash_withdrawals WHERE network = 'P2P_RUB'"
    )).scalar()
    if paid:
        raise RuntimeError(f"Refusing to drop the P2P rail: {paid} withdrawal(s) already use it")
    present = _constraints(bind)
    if "ck_cash_withdrawal_network" in present:
        op.drop_constraint("ck_cash_withdrawal_network", "cash_withdrawals", type_="check")
    if "ck_cash_withdrawal_fiat" in present:
        op.drop_constraint("ck_cash_withdrawal_fiat", "cash_withdrawals", type_="check")
    if "fiat_kopecks" in {c["name"] for c in sa.inspect(bind).get_columns("cash_withdrawals")}:
        op.drop_column("cash_withdrawals", "fiat_kopecks")
