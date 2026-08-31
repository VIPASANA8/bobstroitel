"""Daily missions, and the two day counters they read.

Which mission a slot holds is derived from the player and the date, so nothing
has to be rolled and written before the first hand. A row appears only once
there is something to remember: progress, a completion, or the day's one
reroll.

full_table_hands and positions_mask live on the day row rather than being
counted from the hands, because both are a single write on a hand that is
already being recorded, and reading them back out of hand_players on every
profile visit is the version that stops working.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0011"
down_revision = "20260831_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("progress_days")}
    for name in ("full_table_hands", "positions_mask"):
        if name not in columns:
            op.add_column(
                "progress_days",
                sa.Column(name, sa.Integer(), nullable=False, server_default=sa.text("0")),
            )

    columns = {column["name"] for column in inspector.get_columns("play_sessions")}
    if "daily_xp" not in columns:
        op.add_column(
            "play_sessions",
            sa.Column("daily_xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )

    if "user_missions" not in set(inspector.get_table_names()):
        op.create_table(
            "user_missions",
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("day", sa.String(length=10), primary_key=True),
            sa.Column("slot", sa.String(length=32), primary_key=True),
            sa.Column("reroll_offset", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint("slot IN ('volume', 'session', 'variety')"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "user_missions" in set(inspector.get_table_names()):
        op.drop_table("user_missions")

    columns = {column["name"] for column in inspector.get_columns("play_sessions")}
    if "daily_xp" in columns:
        with op.batch_alter_table("play_sessions") as batch:
            batch.drop_column("daily_xp")

    columns = {column["name"] for column in inspector.get_columns("progress_days")}
    with op.batch_alter_table("progress_days") as batch:
        for name in ("positions_mask", "full_table_hands"):
            if name in columns:
                batch.drop_column(name)
