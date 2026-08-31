"""Account progression: XP, level, and the day counter the soft cap reads.

Three tables and one column. The day counter is keyed the polymorphic way
play_accounts already is, because bots need the counter and nothing else that
will eventually live in that row.

Existing players are grandfathered from users.hands_played rather than starting
over: the profile has shown a level since the first release, and waking every
player at level 1 is a worse first impression than a level that is roughly
earned. The cap keeps the oldest accounts from arriving near the top.

Grandfathered rows keep level 1 in the column and are not backfilled. The level
a player is shown is derived from their XP on every read, and the column is
brought into line by their next settled hand -- which is the whole reason a
migration here does not import application code to compute it.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0008"
down_revision = "20260823_0007"
branch_labels = None
depends_on = None

GRANDFATHERED_XP_CAP = 5000


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_progression" not in tables:
        op.create_table(
            "user_progression",
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("level", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("achievement_points", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint("xp >= 0"),
        )

    if "xp_events" not in tables:
        op.create_table(
            "xp_events",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("reference", sa.String(length=128)),
            sa.Column("idempotency_key", sa.String(length=200), nullable=False, unique=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint("amount > 0"),
        )

    if "progress_days" not in tables:
        op.create_table(
            "progress_days",
            sa.Column("owner_kind", sa.String(length=32), primary_key=True),
            sa.Column("owner_id", sa.String(length=64), primary_key=True),
            sa.Column("day", sa.String(length=10), primary_key=True),
            sa.Column("hands", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("hands_won", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("result_hands", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("net_bb_x100", sa.BIGINT(), nullable=False, server_default=sa.text("0")),
            sa.CheckConstraint("owner_kind IN ('user', 'system')"),
        )

    columns = {column["name"] for column in inspector.get_columns("system_players")}
    if "xp" not in columns:
        op.add_column(
            "system_players",
            sa.Column("xp", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )

    op.execute(sa.text(
        """
        INSERT INTO user_progression (user_id, xp, level)
        SELECT id, MIN(hands_played, :cap), 1 FROM users
        WHERE id NOT IN (SELECT user_id FROM user_progression)
        """
        if bind.dialect.name == "sqlite" else
        """
        INSERT INTO user_progression (user_id, xp, level)
        SELECT id, LEAST(hands_played, :cap), 1 FROM users
        WHERE id NOT IN (SELECT user_id FROM user_progression)
        """
    ).bindparams(cap=GRANDFATHERED_XP_CAP))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    columns = {column["name"] for column in inspector.get_columns("system_players")}
    if "xp" in columns:
        with op.batch_alter_table("system_players") as batch:
            batch.drop_column("xp")

    for name in ("progress_days", "xp_events", "user_progression"):
        if name in tables:
            op.drop_table(name)
