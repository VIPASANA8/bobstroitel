"""The session report, and the stamp it is measured from.

A session is one occupancy of one seat. The report has to outlive the seat --
it is read from the lobby, after the seat row has been blanked and handed to
somebody else -- so it gets a row of its own rather than being derived on
demand from a seat that no longer says anything.

Seats occupied when this runs have no seated_at and so close without a report.
That is one report missed per player, once, rather than a report measured from
a start nobody recorded.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0009"
down_revision = "20260831_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("table_seats")}
    if "seated_at" not in columns:
        op.add_column("table_seats", sa.Column("seated_at", sa.DateTime(timezone=True)))

    if "play_sessions" not in set(inspector.get_table_names()):
        op.create_table(
            "play_sessions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("table_id", sa.String(length=64), sa.ForeignKey("poker_tables.id"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "ended_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("hands", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("net_units", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("big_blind_units", sa.BIGINT(), nullable=False),
            sa.Column("biggest_pot_units", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.Column("xp_earned", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("seen_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_play_sessions_unseen", "play_sessions", ["user_id", "seen_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "play_sessions" in set(inspector.get_table_names()):
        op.drop_index("ix_play_sessions_unseen", table_name="play_sessions")
        op.drop_table("play_sessions")

    columns = {column["name"] for column in inspector.get_columns("table_seats")}
    if "seated_at" in columns:
        with op.batch_alter_table("table_seats") as batch:
            batch.drop_column("seated_at")
