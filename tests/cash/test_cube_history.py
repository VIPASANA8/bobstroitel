from datetime import datetime, timedelta, timezone

import pytest

from cash.cube import CashCubeService
from online.schema import cube_rounds, tenants, users


pytestmark = pytest.mark.anyio


async def test_recent_rounds_are_newest_first_limited_and_private(db_session_factory):
    now = datetime.now(timezone.utc)
    async with db_session_factory() as session:
        async with session.begin():
            await session.execute(tenants.insert().values(id="tenant", slug="cube", name="CUBE"))
            await session.execute(users.insert(), [
                {"id": "alice", "telegram_user_id": 1, "display_name": "Alice", "acquisition_tenant_id": "tenant"},
                {"id": "bob", "telegram_user_id": 2, "display_name": "Bob", "acquisition_tenant_id": "tenant"},
            ])
            await session.execute(cube_rounds.insert(), [
                {"id": "old", "user_id": "alice", "request_id": "old", "stake_micros": 1_000_000,
                 "selected": "2,5", "roll": 2, "payout_micros": 3_000_000, "created_at": now - timedelta(minutes=1)},
                {"id": "new", "user_id": "alice", "request_id": "new", "stake_micros": 1_000_000,
                 "selected": "1", "roll": 4, "payout_micros": 0, "created_at": now},
                {"id": "bob", "user_id": "bob", "request_id": "bob", "stake_micros": 1_000_000,
                 "selected": "3", "roll": 3, "payout_micros": 6_000_000, "created_at": now},
            ])

    rows = await CashCubeService(db_session_factory).recent("alice", limit=1)

    assert rows == [{
        "round_id": "new",
        "selected": [1],
        "roll": 4,
        "stake_micros": 1_000_000,
        "payout_micros": 0,
        "net_micros": -1_000_000,
        "won": False,
        "created_at": now.isoformat(),
    }]
