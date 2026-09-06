"""CUBE moves to USDT: its rounds are counted in micros, not PLAY units.

The columns are renamed rather than converted, because there is nothing to
convert -- a PLAY unit is a training chip and a micro is a millionth of a
dollar. Any round already stored belongs to the chip game and is refused here
rather than silently reinterpreted as money.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260906_0028"
down_revision = "20260906_0027"
branch_labels = None
depends_on = None


def _columns(bind):
    return {c["name"] for c in sa.inspect(bind).get_columns("cube_rounds")}


def upgrade():
    bind = op.get_bind()
    if "stake_micros" in _columns(bind):
        return
    played = bind.execute(sa.text("SELECT count(*) FROM cube_rounds")).scalar()
    if played:
        raise RuntimeError(
            f"Refusing to relabel {played} CUBE round(s) played for chips as USDT; "
            "archive and clear cube_rounds first"
        )
    op.drop_constraint("ck_cube_round_stake", "cube_rounds", type_="check")
    op.drop_constraint("ck_cube_round_payout", "cube_rounds", type_="check")
    op.alter_column("cube_rounds", "stake_units", new_column_name="stake_micros")
    op.alter_column("cube_rounds", "payout_units", new_column_name="payout_micros")
    op.create_check_constraint("ck_cube_round_stake", "cube_rounds", "stake_micros > 0")
    op.create_check_constraint("ck_cube_round_payout", "cube_rounds", "payout_micros >= 0")


def downgrade():
    bind = op.get_bind()
    played = bind.execute(sa.text("SELECT count(*) FROM cube_rounds")).scalar()
    if played:
        raise RuntimeError(
            f"Refusing to relabel {played} CUBE round(s) played for USDT as chips"
        )
    op.drop_constraint("ck_cube_round_stake", "cube_rounds", type_="check")
    op.drop_constraint("ck_cube_round_payout", "cube_rounds", type_="check")
    op.alter_column("cube_rounds", "stake_micros", new_column_name="stake_units")
    op.alter_column("cube_rounds", "payout_micros", new_column_name="payout_units")
    op.create_check_constraint("ck_cube_round_stake", "cube_rounds", "stake_units > 0")
    op.create_check_constraint("ck_cube_round_payout", "cube_rounds", "payout_units >= 0")
