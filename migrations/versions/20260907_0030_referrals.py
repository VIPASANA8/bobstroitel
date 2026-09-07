"""Referrals, their settlements, and the partner's share of Cube."""
from alembic import op
import sqlalchemy as sa

revision = "20260907_0030"
down_revision = "20260906_0029"
branch_labels = None
depends_on = None


#: The kinds a cash transaction may carry after this migration. Referral and
#: partner money each get their own, so a reward is never read back later as a
#: generic adjustment.
KINDS = (
    "'deposit', 'reserve', 'release', 'settlement', 'payout', 'adjustment', "
    "'referral_reward', 'referral_release', 'referral_reversal', "
    "'cube_profit_share', 'cube_profit_share_reversal', 'cube_adjustment'"
)
OLD_KINDS = "'deposit', 'reserve', 'release', 'settlement', 'payout', 'adjustment'"


def _timestamp():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True),
        nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _replace_kind_check(bind, kinds: str) -> None:
    """Widen (or narrow) what a cash transaction may be called.

    A fresh install builds the table from current metadata and already has the
    constraint under this name, an older one has the narrower version, so the
    old one is dropped only if it is actually there. SQLite cannot ALTER a
    constraint at all -- and never runs these migrations for real.
    """
    if bind.dialect.name != "postgresql":
        return
    existing = {
        constraint["name"] for constraint
        in sa.inspect(bind).get_check_constraints("cash_transactions")
    }
    if "ck_cash_transaction_kind" in existing:
        op.drop_constraint("ck_cash_transaction_kind", "cash_transactions", type_="check")
    op.create_check_constraint("ck_cash_transaction_kind", "cash_transactions", f"kind IN ({kinds})")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "internal" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column(
            "internal", sa.Boolean, nullable=False, server_default=sa.text("false"),
        ))

    _replace_kind_check(bind, KINDS)

    if "referral_codes" not in tables:
        op.create_table(
            "referral_codes",
            sa.Column("code", sa.String(32), primary_key=True),
            sa.Column(
                "user_id", sa.String(64), sa.ForeignKey("users.id"),
                nullable=False, unique=True,
            ),
            _timestamp(),
        )

    if "referrals" not in tables:
        op.create_table(
            "referrals",
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("referrer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("code", sa.String(32), nullable=False),
            sa.Column(
                "bound_at", sa.DateTime(timezone=True),
                nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("activated_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("user_id <> referrer_id", name="ck_referral_not_self"),
        )
        op.create_index("ix_referrals_referrer", "referrals", ["referrer_id"])

    if "referral_settlements" not in tables:
        op.create_table(
            "referral_settlements",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("referrer_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("source", sa.String(16), nullable=False),
            sa.Column("period_start", sa.Date, nullable=False),
            sa.Column("gross_micros", sa.BIGINT, nullable=False),
            sa.Column("carryover_before_micros", sa.BIGINT, nullable=False),
            sa.Column("carryover_after_micros", sa.BIGINT, nullable=False),
            sa.Column("base_micros", sa.BIGINT, nullable=False),
            sa.Column("amount_micros", sa.BIGINT, nullable=False),
            sa.Column("breakdown_json", sa.JSON, nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("released_at", sa.DateTime(timezone=True)),
            _timestamp(),
            sa.UniqueConstraint(
                "referrer_id", "source", "period_start", name="uq_referral_settlement_period",
            ),
            sa.CheckConstraint("source IN ('cube', 'poker')", name="ck_referral_settlement_source"),
            sa.CheckConstraint(
                "status IN ('pending', 'available', 'reversed')",
                name="ck_referral_settlement_status",
            ),
            sa.CheckConstraint(
                "amount_micros >= 0 AND base_micros >= 0", name="ck_referral_settlement_amount",
            ),
            sa.CheckConstraint(
                "carryover_before_micros <= 0 AND carryover_after_micros <= 0",
                name="ck_referral_settlement_carryover",
            ),
        )
        op.create_index(
            "ix_referral_settlements_due", "referral_settlements", ["status", "created_at"],
        )

    if "partner_shares" not in tables:
        op.create_table(
            "partner_shares",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("effective_from", sa.Date, nullable=False, unique=True),
            sa.Column("share_bps", sa.Integer, nullable=False),
            sa.Column("note", sa.String(200)),
            _timestamp(),
            sa.CheckConstraint("share_bps BETWEEN 0 AND 10000", name="ck_partner_share_range"),
        )

    if "cube_adjustments" not in tables:
        op.create_table(
            "cube_adjustments",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("occurred_on", sa.Date, nullable=False),
            sa.Column("amount_micros", sa.BIGINT, nullable=False),
            sa.Column("reason", sa.String(400), nullable=False),
            sa.Column("actor", sa.String(100), nullable=False),
            _timestamp(),
            sa.CheckConstraint("amount_micros <> 0", name="ck_cube_adjustment_nonzero"),
        )
        op.create_index("ix_cube_adjustments_day", "cube_adjustments", ["occurred_on"])

    if "partner_settlements" not in tables:
        op.create_table(
            "partner_settlements",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("period_kind", sa.String(8), nullable=False),
            sa.Column("period_start", sa.Date, nullable=False),
            sa.Column("period_end", sa.Date, nullable=False),
            sa.Column("gross_micros", sa.BIGINT, nullable=False),
            sa.Column("referral_cost_micros", sa.BIGINT, nullable=False),
            sa.Column("adjustment_micros", sa.BIGINT, nullable=False),
            sa.Column("net_micros", sa.BIGINT, nullable=False),
            sa.Column("carryover_before_micros", sa.BIGINT, nullable=False),
            sa.Column("carryover_after_micros", sa.BIGINT, nullable=False),
            sa.Column("share_bps", sa.Integer, nullable=False),
            sa.Column("amount_micros", sa.BIGINT, nullable=False),
            sa.Column("posted", sa.Boolean, nullable=False, server_default=sa.text("false")),
            _timestamp(),
            sa.UniqueConstraint("period_kind", "period_start", name="uq_partner_settlement_period"),
            sa.CheckConstraint("period_kind IN ('week', 'month')", name="ck_partner_settlement_kind"),
            sa.CheckConstraint("amount_micros >= 0", name="ck_partner_settlement_amount"),
            sa.CheckConstraint(
                "carryover_before_micros <= 0 AND carryover_after_micros <= 0",
                name="ck_partner_settlement_carryover",
            ),
        )


def downgrade():
    bind = op.get_bind()
    for table in ("referral_settlements", "partner_settlements"):
        settled = bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()
        if settled:
            raise RuntimeError(f"Refusing to drop {table}: {settled} settlement(s) already written")
    op.drop_table("partner_settlements")
    op.drop_index("ix_cube_adjustments_day", table_name="cube_adjustments")
    op.drop_table("cube_adjustments")
    op.drop_table("partner_shares")
    op.drop_index("ix_referral_settlements_due", table_name="referral_settlements")
    op.drop_table("referral_settlements")
    op.drop_index("ix_referrals_referrer", table_name="referrals")
    op.drop_table("referrals")
    op.drop_table("referral_codes")
    _replace_kind_check(bind, OLD_KINDS)
    op.drop_column("users", "internal")
