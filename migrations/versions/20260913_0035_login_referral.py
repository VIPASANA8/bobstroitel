"""What a browser login carries until it is claimed.

The referral code the page was opened with, and the @handle the bot saw on
the confirming person. Both belong to the account, and the account is only
made when the code is claimed -- making it any earlier, to note the handle,
would make it without the invitation.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260913_0035"
down_revision = "20260912_0034"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("auth_login_requests")}
    if "referral_code" not in columns:
        op.add_column("auth_login_requests", sa.Column("referral_code", sa.String(16)))
    if "username" not in columns:
        op.add_column("auth_login_requests", sa.Column("username", sa.String(64)))


def downgrade():
    op.drop_column("auth_login_requests", "username")
    op.drop_column("auth_login_requests", "referral_code")
