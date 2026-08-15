from pathlib import Path


def test_table_uses_online_transport_not_legacy_game_fetches():
    html = Path("static/index.html").read_text(encoding="utf-8")
    script = Path("static/app.js").read_text(encoding="utf-8")
    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "online-transport.js" in html
    assert "new WebSocket" in transport
    assert "Poker8Transport.sendAction" in script
    assert 'fetch(`/api/game/${game.hand_id}/action`' not in script
