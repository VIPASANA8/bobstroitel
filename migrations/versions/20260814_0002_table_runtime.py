"""Persist recoverable table runtimes and game commands."""

from alembic import op

from online.schema import (
    game_commands,
    hand_actions,
    hand_players,
    hands,
    integrity_events,
    table_runtimes,
)


revision = "20260814_0002"
down_revision = "20260814_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        table_runtimes,
        game_commands,
        hands,
        hand_players,
        hand_actions,
        integrity_events,
    ):
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        integrity_events,
        hand_actions,
        hand_players,
        hands,
        game_commands,
        table_runtimes,
    ):
        table.drop(bind=bind, checkfirst=True)
