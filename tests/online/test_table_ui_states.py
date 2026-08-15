from pathlib import Path


def test_table_contains_online_state_surfaces():
    html = Path("static/index.html").read_text(encoding="utf-8")
    for element_id in ("readyPanel", "queueStatus", "connectionStatus", "chatPanel", "newHandCountdown"):
        assert f'id="{element_id}"' in html


def test_system_player_has_no_large_ai_badge():
    script = Path("static/app.js").read_text(encoding="utf-8")
    assert 'seatAvatar.textContent = "AI"' not in script
