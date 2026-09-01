from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOBBY = (ROOT / "static" / "lobby.html").read_text(encoding="utf-8")
LOBBY_JS = (ROOT / "static" / "lobby.js").read_text(encoding="utf-8")
PROFILE = (ROOT / "static" / "profile.html").read_text(encoding="utf-8")
TABLE_JS = (ROOT / "static" / "online-table.js").read_text(encoding="utf-8")


def test_lobby_has_explicit_training_and_cash_catalogues():
    assert 'data-asset="PLAY"' in LOBBY
    assert 'data-asset="CASH_USDT"' in LOBBY
    assert "ТЕСТ — средства ненастоящие" in LOBBY
    assert "asset=${asset}" in LOBBY_JS
    assert "/api/lobby/quick-play?asset=${asset}" in LOBBY_JS


def test_cash_ui_keeps_usdt_payment_fields_separate_from_cash_units():
    assert 'id="depositUsdt"' in LOBBY
    assert 'id="withdrawUsdt"' in LOBBY
    assert 'id="withdrawAddress"' in LOBBY
    assert "1 USDT = 10 единиц CASH" in LOBBY
    assert "BigInt" in LOBBY_JS
    assert "cashUnitsToChips" in LOBBY_JS


def test_profile_and_table_keep_the_mock_warning_visible():
    assert "Доступно" in PROFILE and "За столами" in PROFILE and "Ожидает вывода" in PROFILE
    assert "ТЕСТ — средства ненастоящие" in PROFILE
    assert "ТЕСТ · CASH НЕНАСТОЯЩИЙ" in TABLE_JS

