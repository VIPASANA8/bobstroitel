"""Separate the daily reroll claim from the saved mission choice.

Legacy days may contain several replacement missions. Mark one quota claim
without changing any offset, progress, completion, or XP. Also replace the
offset-based index on databases that already ran the original 0012.

Offsets erased by that original migration cannot be recovered without a
backup; this migration preserves the remaining data and never guesses them.
Downgrading returns to corrected 0012, without its unsafe offset index.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260831_0013"
down_revision = "20260831_0012"
branch_labels = None
depends_on = None

INDEX = "uq_user_missions_daily_reroll"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_missions" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("user_missions")}
    if "reroll_claimed" not in columns:
        op.add_column(
            "user_missions",
            sa.Column("reroll_claimed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        # The chosen slot only records that this day spent its quota; every
        # slot keeps its original mission, including multiple old rerolls.
        op.execute(sa.text("""
            UPDATE user_missions SET reroll_claimed = true
            WHERE reroll_offset <> 0 AND slot = (
                SELECT MAX(kept.slot) FROM user_missions AS kept
                WHERE kept.user_id = user_missions.user_id
                  AND kept.day = user_missions.day AND kept.reroll_offset <> 0
            )
        """))
    if INDEX in {index["name"] for index in inspector.get_indexes("user_missions")}:
        op.drop_index(INDEX, table_name="user_missions")
    op.create_index(
        INDEX, "user_missions", ["user_id", "day"], unique=True,
        postgresql_where=sa.text("reroll_claimed IS true"),
        sqlite_where=sa.text("reroll_claimed IS true"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "user_missions" not in set(inspector.get_table_names()):
        return
    if INDEX in {index["name"] for index in inspector.get_indexes("user_missions")}:
        op.drop_index(INDEX, table_name="user_missions")
    if "reroll_claimed" in {column["name"] for column in inspector.get_columns("user_missions")}:
        with op.batch_alter_table("user_missions") as batch:
            batch.drop_column("reroll_claimed")
