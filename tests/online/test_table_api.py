import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'online.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player",
    })
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_spectator_can_ready_cancel_and_remain_spectator(client):
    client.post("/api/auth/dev/101")
    table_id = client.get("/api/lobby/tables").json()["tables"][0]["id"]
    ready = client.post(
        f"/api/tables/{table_id}/ready",
        json={"seat_no": 2, "buy_in_units": 4_000, "request_id": "ready-1"},
    )
    assert ready.status_code == 200
    assert ready.json()["queue_state"] == "waiting"
    cancelled = client.post(f"/api/tables/{table_id}/ready/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["viewer_state"] == "spectator"


def test_table_snapshot_never_exposes_private_runtime_json(client):
    client.post("/api/auth/dev/101")
    table_id = client.get("/api/lobby/tables").json()["tables"][0]["id"]
    response = client.get(f"/api/tables/{table_id}")
    assert response.status_code == 200
    assert "private_state_json" not in response.text
