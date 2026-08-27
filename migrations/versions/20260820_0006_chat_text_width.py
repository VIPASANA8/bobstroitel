"""Widen a chat message to the length the app already accepts.

Formatting markers count against the limit -- a fenced block around eight lines
is most of the old 300 -- so the app was raised to 1000. The column was not,
and Postgres rejected anything longer than 300 with the player getting a 500.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0006"
down_revision = "20260820_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table so SQLite, which cannot ALTER a column type, rewrites
    # the table instead.
    with op.batch_alter_table("chat_messages") as batch:
        batch.alter_column(
            "text",
            existing_type=sa.String(length=300),
            type_=sa.String(length=1000),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Anything already longer than 300 would not survive the narrowing, so it
    # is truncated rather than failing the migration halfway through.
    op.execute("UPDATE chat_messages SET text = substr(text, 1, 300) WHERE length(text) > 300")
    with op.batch_alter_table("chat_messages") as batch:
        batch.alter_column(
            "text",
            existing_type=sa.String(length=1000),
            type_=sa.String(length=300),
            existing_nullable=False,
        )
