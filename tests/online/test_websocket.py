from app.dependencies import AuthenticatedUser
from app.routers.realtime import ConnectionHub, _snapshot_message
from online.runtime import StaleRevision
from poker.engine import PokerEngine


def test_each_viewer_receives_only_their_hole_cards():
    state = PokerEngine().new_hand([
        {"id": "u1", "name": "A", "seat": 0, "stack": 1000, "is_bot": False},
        {"id": "u2", "name": "B", "seat": 1, "stack": 1000, "is_bot": False},
    ], button_seat=0)
    snapshot_a = state.to_dict(viewer_player_id="u1")
    snapshot_b = state.to_dict(viewer_player_id="u2")
    assert snapshot_a["players"]["u1"]["hole_cards"] != ["??", "??"]
    assert snapshot_a["players"]["u2"]["hole_cards"] == ["??", "??"]
    assert snapshot_b["players"]["u1"]["hole_cards"] == ["??", "??"]


def test_stale_revision_is_encoded_as_snapshot_resync():
    error = StaleRevision(12)
    message = _snapshot_message({"revision": error.current_revision}, "stale_revision")
    assert message["type"] == "snapshot"
    assert message["reason"] == "stale_revision"
    assert message["revision"] == 12


def test_connection_hub_keeps_duplicate_user_presence_until_last_socket():
    hub = ConnectionHub()
    user = AuthenticatedUser("u1", "tenant", 1, "A")
    first = object()
    second = object()
    hub.add("t1", first, user)
    hub.add("t1", second, user)
    assert hub.user_connections("t1", "u1") == 2
    hub.connections["t1"].pop(first)
    assert hub.user_connections("t1", "u1") == 1
    hub.connections["t1"].pop(second)
    assert hub.user_connections("t1", "u1") == 0
