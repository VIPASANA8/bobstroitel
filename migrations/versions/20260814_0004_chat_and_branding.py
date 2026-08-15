"""Add bounded table chat and tenant branding metadata."""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0004"
down_revision = "20260814_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tenant_columns = {column["name"] for column in sa.inspect(bind).get_columns("tenants")}
    if "branding_json" not in tenant_columns:
        op.add_column("tenants", sa.Column("branding_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    if "support_url" not in tenant_columns:
        op.add_column("tenants", sa.Column("support_url", sa.String(length=500), nullable=True))
    inspector = sa.inspect(bind)
    created_chat = not inspector.has_table("chat_messages")
    if created_chat:
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("table_id", sa.String(length=64), sa.ForeignKey("poker_tables.id"), nullable=False),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("text", sa.String(length=300), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if created_chat or not any(index["name"] == "ix_chat_messages_table_time" for index in inspector.get_indexes("chat_messages")):
        op.create_index("ix_chat_messages_table_time", "chat_messages", ["table_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("chat_messages"):
        op.drop_index("ix_chat_messages_table_time", table_name="chat_messages", if_exists=True)
        op.drop_table("chat_messages")
    tenant_columns = {column["name"] for column in sa.inspect(bind).get_columns("tenants")}
    if "support_url" in tenant_columns:
        op.drop_column("tenants", "support_url")
    if "branding_json" in tenant_columns:
        op.drop_column("tenants", "branding_json")
