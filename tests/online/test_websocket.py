import asyncio
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.online import create_app
from online.config import Settings
from online.schema import poker_tables, table_seats


@pytest.fixture
def online_client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'online.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Player A,202:Player B",
    })
    with TestClient(create_app(settings)) as client:
        auth_a = client.post("/api/auth/dev/101").json()
        cookie_a = client.cookies.get(settings.session_cookie_name)
        auth_b = client.post("/api/auth/dev/202").json()
        cookie_b = client.cookies.get(settings.session_cookie_name)
        table_id = client.get("/api/lobby/tables").json()["tables"][0]["id"]

        async def seed():
            async with client.app.state.session_factory() as session:
                await session.execute(insert(table_seats), [
                    {"id": "seat-a", "table_id": table_id, "seat_no": 0, "occupant_kind": "user",
                     "user_id": auth_a["user_id"], "system_player_id": None, "stack_units": 100_000, "state": "seated"},
                    {"id": "seat-b", "table_id": table_id, "seat_no": 1, "occupant_kind": "user",
                     "user_id": auth_b["user_id"], "system_player_id": None, "stack_units": 100_000, "state": "seated"},
                ])
                await session.commit()
            await client.app.state.runtime.start_hand(table_id)

        asyncio.run(seed())
        yield client, table_id, auth_a["user_id"], auth_b["user_id"], cookie_a, cookie_b, tmp_path / "online.sqlite3"


def test_each_player_receives_only_their_hole_cards(online_client):
    client, table_id, player_a, player_b, cookie_a, cookie_b, _ = online_client
    with client.websocket_connect(
        f"/ws/tables/{table_id}", headers={"cookie": f"poker8_session={cookie_a}"}
    ) as ws_a:
        snapshot_a = ws_a.receive_json()
    with client.websocket_connect(
        f"/ws/tables/{table_id}", headers={"cookie": f"poker8_session={cookie_b}"}
    ) as ws_b:
        snapshot_b = ws_b.receive_json()
    assert snapshot_a["state"]["players"][player_a]["hole_cards"] != ["??", "??"]
    assert snapshot_a["state"]["players"][player_b]["hole_cards"] == ["??", "??"]
    assert snapshot_b["state"]["players"][player_a]["hole_cards"] == ["??", "??"]


def test_stale_websocket_command_returns_resync(online_client):
    client, table_id, _, _, cookie_a, _, _ = online_client
    with client.websocket_connect(
        f"/ws/tables/{table_id}", headers={"cookie": f"poker8_session={cookie_a}"}
    ) as ws:
        ws.receive_json()
        ws.send_json({"type": "action", "command_id": "stale", "expected_revision": 0,
                      "action": "fold", "amount_units": 0})
        message = ws.receive_json()
        assert message["type"] == "snapshot"
        assert message["reason"] == "stale_revision"


def test_two_connections_hold_seat_until_last_disconnect(online_client):
    client, table_id, player_a, _, cookie_a, _, db_path = online_client
    with client.websocket_connect(
        f"/ws/tables/{table_id}", headers={"cookie": f"poker8_session={cookie_a}"}
    ) as first:
        first.receive_json()
        with client.websocket_connect(
            f"/ws/tables/{table_id}", headers={"cookie": f"poker8_session={cookie_a}"}
        ) as second:
            second.receive_json()
            first.send_json({"type": "disconnect"})

            def state():
                with sqlite3.connect(db_path) as connection:
                    return connection.execute(
                        "SELECT state FROM table_seats WHERE table_id = ? AND user_id = ?",
                        (table_id, player_a),
                    ).fetchone()[0]

            assert state() == "seated"
            second.send_json({"type": "disconnect"})
    for _ in range(50):
        if state() == "held":
            break
        time.sleep(0.01)
    assert state() == "held"
