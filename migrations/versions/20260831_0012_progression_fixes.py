"""Retire the unsafe offset-based daily-reroll index.

The original upgrade reset extra reroll_offset values to fit a unique index,
changing mission identities underneath their saved progress and completions.
Fresh upgrades must leave those choices untouched; 0013 enforces the quota
separately and replaces the index on databases that already applied old 0012.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0012"
down_revision = "20260831_0011"
branch_labels = None
depends_on = None

INDEX = "uq_user_missions_daily_reroll"


def upgrade() -> None:
    pass


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_missions" not in set(inspector.get_table_names()):
        return
    if INDEX in {index["name"] for index in inspector.get_indexes("user_missions")}:
        op.drop_index(INDEX, table_name="user_missions")
