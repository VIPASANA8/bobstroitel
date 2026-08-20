from pathlib import Path

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


def test_already_seated_error_points_at_the_blocking_table():
    from app.routers.tables import _error
    from online.seating import AlreadySeated

    detail = _error(AlreadySeated("user already has a network seat", "t9", "seated")).detail

    assert detail["code"] == "already_seated"
    assert detail["table_id"] == "t9"
    assert detail["seat_state"] == "seated"


def test_lobby_sends_a_blocked_player_to_their_table():
    from pathlib import Path

    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "already_seated" in source
    assert "openTable(detail.table_id)" in source


def test_table_snapshot_reports_a_dead_seat_request(client):
    """A request can die on its own -- the table stays full past its TTL, or the
    balance stops covering the buy-in. Reporting only "waiting" left the client
    unable to tell "never asked" from "asked and lost it", so the request just
    vanished from the header with no explanation."""
    import re

    router = Path("app/routers/tables.py").read_text(encoding="utf-8")
    snapshot = router[router.index("async def table_snapshot"):router.index("@router.post")]
    queue_query = snapshot[snapshot.index("queue = ("):snapshot.index("scalar_one_or_none()", snapshot.index("queue = ("))]
    # The state filter is gone from the query...
    assert 'seat_queue.c.state == "waiting"' not in queue_query
    # ...and moved to viewer_state, which must still only count a live request.
    assert 'else "waiting" if queue == "waiting"' in snapshot


def test_client_announces_a_seat_request_that_died_on_its_own(client):
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "noticeLostSeatRequest(payload.queue_state)" in source
    assert 'if (previous !== "waiting") return;' in source
    assert '"expired"' in source and '"cancelled"' in source
