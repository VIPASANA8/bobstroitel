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
    assert 'app.js?v=online-legacy-1' in index_source
    assert 'online-table.js?v=online-legacy-1' in index_source


def test_online_mobile_chat_does_not_cover_table_actions():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "mobileChatButton" in source
    assert "is-open" in source
    assert "if (chat) chat.hidden = false;" not in source

    assert ".poker8-online .online-chat-panel.is-open" in source
