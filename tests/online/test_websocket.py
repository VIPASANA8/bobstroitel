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


class _DeadSocket:
    """Peer has gone: every send raises, exactly like a half-open connection."""

    async def send_json(self, message):
        raise ConnectionResetError("peer gone")


class _RecordingSeating:
    def __init__(self):
        self.disconnected = []

    async def mark_disconnected(self, user_id, table_id, now):
        self.disconnected.append((user_id, table_id))


class _StubRuntime:
    async def public_snapshot(self, table_id, user_id):
        return {"revision": 1}


def test_a_socket_that_fails_to_send_is_dropped_and_releases_its_seat():
    """A vanished client only reveals itself through a failed send. Keeping the
    socket meant mark_disconnected never ran, so the seat stayed `seated` and
    the lobby offered an active session hours after the app was closed."""
    import anyio

    seating = _RecordingSeating()
    hub = ConnectionHub(seating=seating)
    user = AuthenticatedUser("u1", "tenant", 1, "A")
    socket = _DeadSocket()
    hub.add("t1", socket, user)

    anyio.run(hub.broadcast, "t1", _StubRuntime())

    assert hub.user_connections("t1", "u1") == 0
    assert seating.disconnected == [("u1", "t1")]


def test_a_second_live_socket_keeps_the_seat_when_one_dies():
    """Two tabs open: losing one must not start the hold on the seat."""
    import anyio

    seating = _RecordingSeating()
    hub = ConnectionHub(seating=seating)
    user = AuthenticatedUser("u1", "tenant", 1, "A")

    class _LiveSocket:
        def __init__(self):
            self.sent = []

        async def send_json(self, message):
            self.sent.append(message)

    live = _LiveSocket()
    hub.add("t1", _DeadSocket(), user)
    hub.add("t1", live, user)

    anyio.run(hub.broadcast, "t1", _StubRuntime())

    assert hub.user_connections("t1", "u1") == 1
    assert seating.disconnected == []
    assert live.sent
