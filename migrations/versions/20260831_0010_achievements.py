"""Achievement progress, and the opponents SOCIAL counts.

Definitions stay in online/achievements.py. Only what a player has actually
done is worth a row: thresholds change with a release, and a release is a
safer place to read them from than a table nothing updates.

user_opponents exists because a count cannot answer the question SOCIAL asks.
Knowing somebody is new needs the set, not its size.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0010"
down_revision = "20260831_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "user_achievements" not in tables:
        op.create_table(
            "user_achievements",
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("code", sa.String(length=64), primary_key=True),
            sa.Column("progress", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("tier", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    if "user_opponents" not in tables:
        op.create_table(
            "user_opponents",
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("opponent_id", sa.String(length=64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column(
                "first_played_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for name in ("user_opponents", "user_achievements"):
        if name in tables:
            op.drop_table(name)
