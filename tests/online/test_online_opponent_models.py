import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert

from online.opponent_models import OnlineOpponentModel
from online.schema import hand_actions, hand_players, hands, poker_tables, tenants, users


@pytest.fixture
def model_context(db_session_factory):
    async def seed():
        async with db_session_factory() as session:
            await session.execute(insert(tenants).values(id="tenant", slug="poker8", name="Poker8"))
            await session.execute(insert(users).values(
                id="u1", telegram_user_id=1, display_name="A", acquisition_tenant_id="tenant",
            ))
            await session.execute(insert(poker_tables).values(
                id="t1", scope="network", name="One", small_blind_units=50,
                big_blind_units=100, min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6,
            ))
            now = datetime.now(timezone.utc)
            await session.execute(insert(hands), [
                {"id": "recent", "table_id": "t1", "revision_started": 1, "button_seat": 0,
                 "board_json": [], "terminal": True, "started_at": now},
                {"id": "old", "table_id": "t1", "revision_started": 1, "button_seat": 0,
                 "board_json": [], "terminal": True, "started_at": now - timedelta(days=30)},
            ])
            await session.execute(insert(hand_players), [
                {"hand_id": "recent", "participant_id": "u1", "user_id": "u1", "seat_no": 0,
                 "position": "BTN", "start_stack_units": 100_000},
                {"hand_id": "old", "participant_id": "u1", "user_id": "u1", "seat_no": 0,
                 "position": "BTN", "start_stack_units": 100_000},
            ])
            await session.execute(insert(hand_actions), [
                {"hand_id": "recent", "sequence": 0, "participant_id": "u1", "street": "preflop",
                 "action": "raise", "amount_units": 200, "pot_before_units": 100, "pot_after_units": 300,
                 "to_call_before_units": 100},
                {"hand_id": "old", "sequence": 0, "participant_id": "u1", "street": "preflop",
                 "action": "fold", "amount_units": 0, "pot_before_units": 100, "pot_after_units": 100,
                 "to_call_before_units": 100},
            ])
            await session.commit()

    asyncio.run(seed())
    return OnlineOpponentModel(db_session_factory)


@pytest.mark.anyio
async def test_recent_samples_are_weighted_more_and_confidence_needs_volume(model_context):
    model = await model_context.model_for("u1")
    assert model.sample_count == 2
    assert model.recency_weight > 1.0
    assert model.confidence < 0.5
    assert model.pfr > model.vpip - 0.01
