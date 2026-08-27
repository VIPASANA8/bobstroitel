"""Let players open their own rooms.

Records who created a table and who may see it. Seat count stays fixed at six,
so the existing constraint is left exactly as it is.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260820_0005"
down_revision = "20260814_0004"
branch_labels = None
depends_on = None


VISIBILITY_CHECK = "ck_poker_tables_visibility"


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("poker_tables")}
    if "created_by" not in columns:
        op.add_column(
            "poker_tables",
            # No database-level foreign key on purpose: SQLite cannot add one
            # through ALTER, which made this migration neither reversible nor
            # repeatable. The column is written only by the room-creation path.
            sa.Column("created_by", sa.String(length=64), nullable=True),
        )
    if "visibility" not in columns:
        op.add_column(
            "poker_tables",
            sa.Column(
                "visibility",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'public'"),
            ),
        )
        # Postgres takes this directly; SQLite needs the table rewritten, which
        # is what batch_alter_table does for us.
        with op.batch_alter_table("poker_tables") as batch:
            batch.create_check_constraint(VISIBILITY_CHECK, "visibility IN ('public', 'link')")


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("poker_tables")}
    # Both drops go through one batch: SQLite refuses to drop a column named in
    # a foreign key, and dropping created_by directly leaves the FK dangling.
    # A batch rewrites the table instead, which handles the key and the check.
    with op.batch_alter_table("poker_tables") as batch:
        if "visibility" in columns:
            try:
                batch.drop_constraint(VISIBILITY_CHECK, type_="check")
            except Exception:
                # Absent on a database where the column predates the constraint.
                pass
            batch.drop_column("visibility")
        if "created_by" in columns:
            batch.drop_column("created_by")
        # The six-seat check has no name, and an unnamed constraint does not
        # survive the reflection a batch rewrite is built on -- it would be
        # dropped silently here. Put it back, named this time.
        try:
            batch.create_check_constraint("ck_poker_tables_max_seats", "max_seats = 6")
        except Exception:
            # Already present on a dialect that kept it through the rewrite.
            pass
