import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.online import create_app
from online.config import Settings
from online.schema import play_sessions, progress_days
from datetime import datetime, timedelta, timezone


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'online.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player",
        "POKER8_OPEN_ACCESS": "1",
    })
    with TestClient(create_app(settings)) as test_client:
        test_client.post("/api/auth/dev/101")
        yield test_client


def test_an_empty_profile_reports_no_rate_rather_than_zero(client):
    stats = client.get("/api/profile/stats").json()
    assert stats["hands"] == 0
    assert stats["bb_per_100"] is None, "a rate over no hands is unknown, not zero"
    assert stats["best_day"] is None and stats["worst_day"] is None
    assert stats["confidence"] == "low"


@pytest.mark.anyio
async def test_the_rate_divides_by_the_hands_that_could_move_it(client):
    user_id = client.get("/api/profile").json()["user_id"]
    table_id = client.get("/api/lobby/tables").json()["tables"][0]["id"]
    factory = client.app.state.session_factory
    async with factory() as session:
        async with session.begin():
            await session.execute(insert(progress_days), [
                # 400 hands in a room, of which none counted; 100 at a network
                # table worth +50 BB between them.
                {"owner_kind": "user", "owner_id": user_id, "day": "2026-08-30",
                 "hands": 400, "hands_won": 120, "result_hands": 0, "xp": 150, "net_bb_x100": 0},
                {"owner_kind": "user", "owner_id": user_id, "day": "2026-08-31",
                 "hands": 100, "hands_won": 40, "result_hands": 100, "xp": 100, "net_bb_x100": 5_000},
            ])
            ended = datetime.now(timezone.utc)
            await session.execute(insert(play_sessions).values(
                id="s1", user_id=user_id, table_id=table_id,
                started_at=ended - timedelta(minutes=47), ended_at=ended,
                hands=100, net_units=5_000, big_blind_units=100, biggest_pot_units=12_400,
            ))

    stats = client.get("/api/profile/stats").json()
    assert stats["hands"] == 500 and stats["result_hands"] == 100
    assert stats["net_bb"] == 50.0
    # 50 BB over the 100 hands that counted, not over all 500.
    assert stats["bb_per_100"] == 50.0
    assert stats["hands_won"] == 160
    assert stats["days_played"] == 2
    assert stats["sessions"] == 1
    assert stats["longest_session_minutes"] == 47
    assert stats["biggest_pot_bb"] == 124.0
    assert stats["best_day"] == {"day": "2026-08-31", "net_bb": 50.0}
    assert stats["worst_day"] == {"day": "2026-08-30", "net_bb": 0.0}
    assert stats["best_day"] != stats["worst_day"]
    assert stats["confidence"] == "low", "100 counted hands is not a sample"


@pytest.mark.anyio
async def test_one_day_of_play_has_a_best_and_no_worst(client):
    """The same day printed twice, once as the best and once as the worst,
    reads as a page that failed rather than a record."""
    user_id = client.get("/api/profile").json()["user_id"]
    async with client.app.state.session_factory() as session:
        async with session.begin():
            await session.execute(insert(progress_days).values(
                owner_kind="user", owner_id=user_id, day="2026-08-31",
                hands=60, hands_won=20, result_hands=60, xp=60, net_bb_x100=1_200,
            ))

    stats = client.get("/api/profile/stats").json()
    assert stats["best_day"] == {"day": "2026-08-31", "net_bb": 12.0}
    assert stats["worst_day"] is None
