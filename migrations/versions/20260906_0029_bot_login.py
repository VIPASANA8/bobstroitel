"""Signing in through the bot: one short-lived code per attempt."""
from alembic import op
import sqlalchemy as sa

revision = "20260906_0029"
down_revision = "20260906_0028"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "auth_login_requests" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "auth_login_requests",
        sa.Column("nonce", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("telegram_user_id", sa.BIGINT),
        sa.Column("display_name", sa.String(200)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_login_requests_expiry", "auth_login_requests", ["expires_at"])


def downgrade():
    # Nothing here outlives ten minutes, so there is nothing to refuse to drop.
    op.drop_index("ix_auth_login_requests_expiry", table_name="auth_login_requests")
    op.drop_table("auth_login_requests")
