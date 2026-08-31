"""The index that actually holds the one-reroll-a-day rule.

The check in missions.reroll reads and then writes, so two requests arriving
together both saw an unused reroll and both kept theirs. A partial unique index
is where the rule belongs -- the same shape as uq_active_table_seat_user, and
for the same reason.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0012"
down_revision = "20260831_0011"
branch_labels = None
depends_on = None

INDEX = "uq_user_missions_daily_reroll"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_missions" not in set(inspector.get_table_names()):
        return
    if INDEX in {index["name"] for index in inspector.get_indexes("user_missions")}:
        return
    # A day that already has two rerolls on it would refuse the index. There
    # can only be one deployment-day's worth of those, and the later one is
    # the one the player is looking at.
    # A correlated scalar subquery rather than a row-value IN: this runs on
    # both SQLite and PostgreSQL and only one of them can be tried here.
    op.execute(sa.text(
        """
        UPDATE user_missions SET reroll_offset = 0
        WHERE reroll_offset <> 0 AND slot <> (
            SELECT MAX(kept.slot) FROM user_missions AS kept
            WHERE kept.user_id = user_missions.user_id
              AND kept.day = user_missions.day
              AND kept.reroll_offset <> 0
        )
        """
    ))
    op.create_index(
        INDEX, "user_missions", ["user_id", "day"], unique=True,
        postgresql_where=sa.text("reroll_offset <> 0"),
        sqlite_where=sa.text("reroll_offset <> 0"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_missions" not in set(inspector.get_table_names()):
        return
    if INDEX in {index["name"] for index in inspector.get_indexes("user_missions")}:
        op.drop_index(INDEX, table_name="user_missions")
