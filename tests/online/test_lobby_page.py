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


def test_root_serves_lobby_with_six_card_container(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="tableGrid"' in response.text
    assert 'id="quickPlay"' in response.text


def test_public_config_contains_branding_but_no_bot_token(client):
    payload = client.get("/api/config").json()
    assert payload["tenant"]["slug"] == "poker8"
    assert payload["network_brand"] == "Poker8"
    assert "token" not in str(payload).lower()


def test_lobby_join_has_http_safe_request_id_fallback():
    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "crypto.randomUUID?.()" in source


def test_table_transport_has_http_safe_request_id_fallback():
    source = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "const requestId = () => crypto.randomUUID?.()" in source
    assert "command_id = requestId()" in source


def test_lobby_cards_render_buy_in_from_unit_values():
    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "table.min_buy_in_units / table.big_blind_units" in source


def test_online_table_uses_existing_poker8_visual_dom():
    online_source = Path("static/online-table.js").read_text(encoding="utf-8")
    app_source = Path("static/app.js").read_text(encoding="utf-8")
    index_source = Path("static/index.html").read_text(encoding="utf-8")
    assert "window.Poker8LegacyView?.renderSnapshot" in online_source
    assert "onlineSurface" not in online_source
    assert "window.Poker8LegacyView" in app_source
    assert '/static/app.js?v=' in index_source
    assert '/static/online-table.js?v=' in index_source


def test_online_mobile_chat_does_not_cover_table_actions():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "mobileChatButton" in source
    assert "is-open" in source
    assert "if (chat) chat.hidden = false;" not in source

    assert ".poker8-online .online-chat-panel.is-open" in source


def test_online_table_does_not_repaint_legacy_view_for_same_snapshot():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "lastRenderKey" in source
    assert "if (key === lastRenderKey) return;" in source


def test_online_ready_panel_is_hidden_for_seated_users_and_duplicate_clicks():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert ".online-state-panel[hidden]" in source
    assert '["spectator", "waiting"].includes(viewerState)' in source
    assert "readyInFlight" in source


def test_online_waiting_prompt_reflects_the_viewers_own_ready_state():
    """A hand no longer starts purely on seat count -- every seated human
    must click ready first (online/coordinator.py's _may_start_hand). The
    prompt used to just claim the table deals itself; it now tells the
    viewer whether their own click is still needed."""
    source = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    assert "НАЖМИТЕ НА АВАТАР" in source
    assert "ЖДЁМ ОСТАЛЬНЫХ" in source


def test_online_ready_up_posts_to_the_server_not_the_local_event_bus():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "window.Poker8Transport.readyUp()" in source
    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "/ready-up" in transport


def test_online_mode_disables_legacy_ready_badges():
    index = Path("static/index.html").read_text(encoding="utf-8")
    source = Path("static/v024-ready-phase.js").read_text(encoding="utf-8")
    assert "window.Poker8OnlineTable" in index
    assert "isOnlineTable() || !preHand()" in source


def test_lobby_card_offers_a_way_to_watch_without_buying_in():
    """Every table card used to route through the buy-in dialog -- the only
    reason opening a table to just watch felt impossible even though the
    server has supported it all along (viewer_state: spectator)."""
    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "data-observe-table" in source
    assert "openTable(button.dataset.observeTable)" in source


def test_online_table_header_shows_the_real_seat_state_not_a_stored_choice():
    """Both controls stay up the whole time the viewer has no seat, and the
    pair reads as "where you are now / what you can switch to" -- driven by the
    server's own answer. The old version highlighted a sessionStorage
    preference that could disagree with the actual state, and its "Наблюдатель"
    button did nothing beyond moving that highlight."""
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "mobileHeaderTakeSeat" in source
    assert "mobileHeaderObserve" in source
    assert 'const offer = ["spectator", "waiting"].includes(viewerState);' in source
    assert "wrap.hidden = !offer;" in source
    # Derived from viewerState, never from a stored preference.
    assert "OBSERVE_MODE_KEY" not in source
    assert 'const queued = viewerState === "waiting";' in source
    assert 'take.textContent = queued ? "В очереди" : "Занять место";' in source
    assert "take.disabled = queued;" in source
    # Observing is now a real action while queued: it hands the seat back.
    assert "cancelQueue()" in source


def test_no_card_covers_the_felt_while_a_hand_is_running():
    """The prompt is for an idle table only. While a hand runs it sat over the
    board and the pot, and a player sitting that hand out reads their own state
    off the avatar instead -- the checkmark when ready, the pulse when not."""
    source = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    assert "ВЫ НАБЛЮДАЕТЕ" not in source
    assert "if (!seated) return false;" in source
    # Shown for the idle room only, never alongside a live hand.
    assert 'prompt?.classList.toggle("visible", hasSomethingToSay && room);' in source
    assert "sittingOut" not in source

    # v028 only marks "no hand at all", so the checkmark had nowhere to appear
    # while a hand ran without this seat.
    assert 'document.body.classList.toggle("p8-can-ready"' in source
    assert "body.v014.poker8-v2-sixmax.p8-can-ready .avatar-wrap.v038-viewer-ready .v038-ready-mark{display:grid;}" in source
    assert "body.v014.poker8-v2-sixmax.p8-can-ready .seat[data-visual-seat=\"0\"] .avatar-wrap:not(.v038-viewer-ready) .player-avatar" in source


def test_request_observe_dead_code_is_gone():
    """It was a pure alias for request_leave, and nothing ever called it --
    the client's own 'Наблюдать' needs no server round trip at all, since a
    seatless viewer is already a spectator."""
    seating = Path("online/seating.py").read_text(encoding="utf-8")
    assert "request_observe" not in seating
    router = Path("app/routers/tables.py").read_text(encoding="utf-8")
    assert '"/{table_id}/observe"' not in router
    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "/observe" not in transport
