"""Store the requested seat for FIFO seating."""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0003"
down_revision = "20260814_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    has_column = any(column["name"] == "seat_no" for column in sa.inspect(bind).get_columns("seat_queue"))
    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("seat_queue", recreate=recreate) as batch:
        if not has_column:
            batch.add_column(sa.Column("seat_no", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch.create_check_constraint("ck_seat_queue_seat_no", "seat_no >= 0 AND seat_no <= 5")
        batch.alter_column("seat_no", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table("seat_queue", recreate=recreate) as batch:
        batch.drop_constraint("ck_seat_queue_seat_no", type_="check")
        batch.drop_column("seat_no")
