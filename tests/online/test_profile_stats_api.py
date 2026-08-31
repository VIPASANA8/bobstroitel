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
    # The room day put no result on the board, so it is neither record.
    assert stats["worst_day"] is None
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


@pytest.mark.anyio
async def test_a_day_that_never_counted_a_result_is_neither_best_nor_worst(client):
    """A day spent entirely in a room the player opened scores zero because
    none of it counted -- and a zero was beating a real losing day to 'best'."""
    user_id = client.get("/api/profile").json()["user_id"]
    async with client.app.state.session_factory() as session:
        async with session.begin():
            await session.execute(insert(progress_days), [
                {"owner_kind": "user", "owner_id": user_id, "day": "2026-08-30",
                 "hands": 300, "hands_won": 90, "result_hands": 0, "xp": 150, "net_bb_x100": 0},
                {"owner_kind": "user", "owner_id": user_id, "day": "2026-08-31",
                 "hands": 200, "hands_won": 60, "result_hands": 200, "xp": 200, "net_bb_x100": -2_000},
            ])

    stats = client.get("/api/profile/stats").json()
    assert stats["best_day"] == {"day": "2026-08-31", "net_bb": -20.0}
    assert stats["worst_day"] is None, "one scored day has a best and no worst"


@pytest.mark.anyio
async def test_a_sitting_too_short_to_be_a_session_sets_no_record(client):
    """§4: below ten hands it is a receipt, not a session. Counting them made
    'sessions' and the biggest pot answer to sitting down and standing up."""
    user_id = client.get("/api/profile").json()["user_id"]
    table_id = client.get("/api/lobby/tables").json()["tables"][0]["id"]
    ended = datetime.now(timezone.utc)
    async with client.app.state.session_factory() as session:
        async with session.begin():
            await session.execute(insert(play_sessions), [
                {"id": "short", "user_id": user_id, "table_id": table_id,
                 "started_at": ended - timedelta(minutes=90), "ended_at": ended,
                 "hands": 3, "net_units": 0, "big_blind_units": 100,
                 "biggest_pot_units": 99_000, "xp_earned": 3, "daily_xp": 0},
                {"id": "real", "user_id": user_id, "table_id": table_id,
                 "started_at": ended - timedelta(minutes=20), "ended_at": ended,
                 "hands": 40, "net_units": 0, "big_blind_units": 100,
                 "biggest_pot_units": 1_200, "xp_earned": 40, "daily_xp": 0},
            ])

    stats = client.get("/api/profile/stats").json()
    assert stats["sessions"] == 1, "only the one that was a session"
    assert stats["biggest_pot_bb"] == 12.0, "the 990 BB pot sat in a three-hand sitting"
    assert stats["longest_session_minutes"] == 20


def test_losing_the_race_for_the_day_reroll_reads_as_refusal_not_failure(client):
    """The unique index refuses the second write, and that used to surface as a
    500. Two people cannot both take the day's one swap, but the one who does
    not should be told so."""
    first = client.post("/api/profile/missions/volume/reroll")
    second = client.post("/api/profile/missions/variety/reroll")
    assert first.status_code == 200
    assert second.status_code == 409, "the day's swap is spent"
    # This exercises the read guard. The index behind it is what catches two
    # requests that read at the same moment, and its refusal is turned into
    # the same 409 rather than escaping as a 500 -- checked against a real
    # Postgres with three concurrent requests, see docs/progression-build.md.
