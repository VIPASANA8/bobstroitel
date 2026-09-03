"""Pilot player limits: one live withdrawal, and a break the user can impose."""
from alembic import op
import sqlalchemy as sa

revision = "20260903_0025"
down_revision = "20260903_0024"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
ACTIVE_WITHDRAWALS = (
    "status IN ('requested','reserved','approved','sending','submitted','unknown')"
)


def _columns(bind, table):
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _constraints(bind, table):
    return {item["name"] for item in sa.inspect(bind).get_check_constraints(table)}


def upgrade():
    bind = op.get_bind()
    if "until" not in _columns(bind, "cash_user_holds"):
        op.add_column("cash_user_holds", sa.Column("until", TS))
    # An operator hold keeps its operator; a self-imposed break has none, so the
    # column stops being mandatory and a check keeps every row owned by one or
    # the other rather than by nobody.
    op.alter_column("cash_user_holds", "operator_id", existing_type=sa.String(64), nullable=True)
    if "ck_cash_hold_owner" not in _constraints(bind, "cash_user_holds"):
        op.create_check_constraint(
            "ck_cash_hold_owner", "cash_user_holds",
            "operator_id IS NOT NULL OR until IS NOT NULL",
        )
    # One live withdrawal per user, enforced by the database and not only by the
    # service that creates them -- the same shape the RUB orders already use.
    if "uq_cash_withdrawal_active_user" not in _indexes(bind, "cash_withdrawals"):
        duplicates = bind.execute(sa.text(
            f"SELECT count(*) FROM (SELECT user_id FROM cash_withdrawals"
            f" WHERE {ACTIVE_WITHDRAWALS} GROUP BY user_id HAVING count(*) > 1) AS d"
        )).scalar()
        if duplicates:
            raise RuntimeError(
                f"Refusing to add the single-withdrawal rule: {duplicates} user(s) "
                "already have more than one live withdrawal; settle them first"
            )
        op.create_index(
            "uq_cash_withdrawal_active_user", "cash_withdrawals", ["user_id"], unique=True,
            postgresql_where=sa.text(ACTIVE_WITHDRAWALS),
            sqlite_where=sa.text(ACTIVE_WITHDRAWALS),
        )


def downgrade():
    bind = op.get_bind()
    if "uq_cash_withdrawal_active_user" in _indexes(bind, "cash_withdrawals"):
        op.drop_index("uq_cash_withdrawal_active_user", table_name="cash_withdrawals")
    # Restoring NOT NULL would silently drop every self-imposed break, so the
    # breaks have to be gone first. Nobody may lose one by running a downgrade.
    breaks = bind.execute(sa.text(
        "SELECT count(*) FROM cash_user_holds WHERE operator_id IS NULL"
    )).scalar()
    if breaks:
        raise RuntimeError(
            f"Refusing to drop self-imposed breaks: {breaks} account(s) are on one"
        )
    if "ck_cash_hold_owner" in _constraints(bind, "cash_user_holds"):
        op.drop_constraint("ck_cash_hold_owner", "cash_user_holds", type_="check")
    op.alter_column("cash_user_holds", "operator_id", existing_type=sa.String(64), nullable=False)
    if "until" in _columns(bind, "cash_user_holds"):
        op.drop_column("cash_user_holds", "until")
