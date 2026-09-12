"""Support tickets: a player writes from the site, an operator answers in the bot."""
from alembic import op
import sqlalchemy as sa

revision = "20260912_0033"
down_revision = "20260912_0032"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "support_tickets" not in tables:
        op.create_table(
            "support_tickets",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("topic", sa.String(16), nullable=False),
            sa.Column("reference_kind", sa.String(16)),
            sa.Column("reference_id", sa.String(64)),
            sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("closed_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("topic IN ('finance', 'support')", name="ck_support_ticket_topic"),
            sa.CheckConstraint("status IN ('open', 'answered', 'closed')", name="ck_support_ticket_status"),
        )
        op.create_index("ix_support_tickets_user", "support_tickets", ["user_id", "status"])
    if "support_messages" not in tables:
        op.create_table(
            "support_messages",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("ticket_id", sa.String(64), sa.ForeignKey("support_tickets.id"), nullable=False),
            sa.Column("author", sa.String(16), nullable=False),
            sa.Column("operator_id", sa.String(64), sa.ForeignKey("cash_operators.id")),
            sa.Column("text", sa.String(2000), nullable=False),
            sa.Column("photo_file_id", sa.String(200)),
            sa.Column("cards_json", sa.JSON, nullable=False, server_default=sa.text("'[]'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.CheckConstraint("author IN ('user', 'operator')", name="ck_support_message_author"),
        )
        op.create_index("ix_support_messages_ticket", "support_messages", ["ticket_id", "created_at"])


def downgrade():
    op.drop_index("ix_support_messages_ticket", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_user", table_name="support_tickets")
    op.drop_table("support_tickets")
