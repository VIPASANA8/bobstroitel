from __future__ import annotations

import os

from sqlalchemy import update

from app.online import create_app
from online.config import Settings
from online.schema import system_players
from poker.models import ActionType


async def install_deterministic_fixture(app) -> None:
    """Install a two-bot fixture only for the browser acceptance server."""
    async with app.state.session_factory() as session:
        async with session.begin():
            await session.execute(update(system_players).values(active=False))
            await session.execute(
                update(system_players)
                .where(system_players.c.id.in_(("system-01", "system-02")))
                .values(active=True)
            )

    runtime = app.state.runtime

    async def deterministic_system_step(table_id: str):
        loaded = await runtime.load(table_id)
        actor = loaded.state.acting_player
        legal = runtime.engine.legal_actions(loaded.state, actor)
        action = ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL
        amount_units = 0
        if action == ActionType.CALL:
            async with app.state.session_factory() as session:
                table = await runtime._table(session, table_id)
            amount_units = round(runtime.engine.to_call(loaded.state, actor) * table["big_blind_units"])
        return await runtime.action(
            table_id, actor, f"fixture:{loaded.state.hand_id}:{loaded.revision}",
            loaded.revision, action.value, amount_units,
        )

    runtime.system_step = deterministic_system_step


app = create_app(
    Settings.from_mapping(os.environ),
    fixture=install_deterministic_fixture,
)
