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


def test_online_table_header_offers_seat_and_observe_while_spectating():
    """Both controls stay up the whole time the viewer has no seat -- picking
    "Наблюдать" only marks that choice (for the shimmer), it must never hide
    either button, since a spectator can always change their mind."""
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "mobileHeaderTakeSeat" in source
    assert "mobileHeaderObserve" in source
    assert 'const offer = ["spectator", "waiting"].includes(viewerState);' in source
    assert "wrap.hidden = !offer;" in source
    # The picked mode survives re-renders and snapshot pushes, not just this click.
    assert "sessionStorage.setItem(OBSERVE_MODE_KEY" in source
    assert "sessionStorage.removeItem(OBSERVE_MODE_KEY)" in source
    assert 'classList.toggle("mode-active", observing)' in source


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
