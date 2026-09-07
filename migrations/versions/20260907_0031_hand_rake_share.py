"""Whose money each hand's rake came out of.

The share cannot be worked out later: `hands.result_json` keeps the winners and
the rake of each pot, but not who contributed to which layer. So it is written
at settlement, from the hand that is still in memory, and this column is what
a Poker referral share is later computed from.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260907_0031"
down_revision = "20260907_0030"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("hand_players")}
    if "rake_micros" not in columns:
        # Nullable, and left NULL for every hand already played: zero would
        # claim those hands were rake-free, which is a different statement.
        op.add_column("hand_players", sa.Column("rake_micros", sa.BIGINT))


def downgrade():
    op.drop_column("hand_players", "rake_micros")
