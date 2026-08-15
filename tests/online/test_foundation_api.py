import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'online.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player,202:Second Player",
    })
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_unauthenticated_lobby_is_rejected(client):
    assert client.get("/api/lobby/tables").status_code == 401


def test_dev_login_returns_same_global_profile_and_six_tables(client):
    login = client.post("/api/auth/dev/101")
    assert login.status_code == 200
    assert login.json()["display_name"] == "Dev Player"
    assert login.json()["available_units"] == 100_000
    lobby = client.get("/api/lobby/tables")
    assert lobby.status_code == 200
    assert len(lobby.json()["tables"]) == 6


def test_repeated_login_does_not_repeat_welcome_grant(client):
    client.post("/api/auth/dev/101")
    client.post("/api/auth/dev/101")
    assert client.get("/api/profile").json()["available_units"] == 100_000


def test_play_top_up_is_idempotent(client):
    client.post("/api/auth/dev/101")
    first = client.post("/api/profile/play-top-up", json={"amount_units": 100_000, "request_id": "topup-1"})
    second = client.post("/api/profile/play-top-up", json={"amount_units": 100_000, "request_id": "topup-1"})
    assert first.json()["available_units"] == second.json()["available_units"] == 200_000
