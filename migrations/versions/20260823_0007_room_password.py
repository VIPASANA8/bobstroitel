"""Replace link-only rooms with a password gate.

A link-only room was reachable by anyone who had the URL, with no check at
all on the join path -- pure obscurity. A password is a real gate: stored
salted with the room's own id (see online/catalogue.py), checked on
SeatingService.ready(). The visibility column and its constraint are left
alone; new rooms always write "public" now, so it goes unused rather than
needing a rewrite to drop.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260823_0007"
down_revision = "20260820_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("poker_tables")}
    if "password_hash" not in columns:
        op.add_column(
            "poker_tables",
            sa.Column("password_hash", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("poker_tables")}
    if "password_hash" in columns:
        with op.batch_alter_table("poker_tables") as batch:
            batch.drop_column("password_hash")
