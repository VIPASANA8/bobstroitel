"""The player's @username, so a support card can name them the way an operator
would look them up."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0034"
down_revision = "20260912_0033"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "username" not in columns:
        op.add_column("users", sa.Column("username", sa.String(64)))


def downgrade():
    op.drop_column("users", "username")
