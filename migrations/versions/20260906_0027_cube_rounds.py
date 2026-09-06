"""CUBE: one row per settled dice round, so a retried roll is answered, not redrawn."""
from alembic import op
import sqlalchemy as sa

revision = "20260906_0027"
down_revision = "20260904_0026"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "cube_rounds" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "cube_rounds",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(200), nullable=False),
        sa.Column("stake_units", sa.BIGINT, nullable=False),
        sa.Column("selected", sa.String(16), nullable=False),
        sa.Column("roll", sa.Integer, nullable=False),
        sa.Column("payout_units", sa.BIGINT, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("user_id", "request_id", name="uq_cube_round_request"),
        sa.CheckConstraint("roll BETWEEN 1 AND 6", name="ck_cube_round_face"),
        sa.CheckConstraint("stake_units > 0", name="ck_cube_round_stake"),
        sa.CheckConstraint("payout_units >= 0", name="ck_cube_round_payout"),
    )
    op.create_index("ix_cube_rounds_user_time", "cube_rounds", ["user_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    played = bind.execute(sa.text("SELECT count(*) FROM cube_rounds")).scalar()
    if played:
        raise RuntimeError(f"Refusing to drop cube_rounds: {played} round(s) already settled")
    op.drop_index("ix_cube_rounds_user_time", table_name="cube_rounds")
    op.drop_table("cube_rounds")
