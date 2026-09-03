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


def test_cash_ui_exposes_rub_p2p_without_changing_trc20_withdrawals():
    assert 'id="cashFiatDeposit"' in LOBBY
    assert 'id="fiatDepositUsdt"' in LOBBY
    assert "/api/cash/fiat-orders" in LOBBY_JS
    assert "Я оплатил" in LOBBY_JS
    assert "ждём подтверждения трейдера" in LOBBY_JS
    # The cashier survives a reload, shows the expiry and never credits itself.
    assert "/api/cash/fiat-orders/active" in LOBBY_JS
    assert "Осталось" in LOBBY_JS
    assert "Комиссия пополнения" in LOBBY_JS
    assert "simulate-trader-confirmation" not in LOBBY_JS
    assert 'id="withdrawAddress"' in LOBBY


def test_profile_and_table_keep_the_mock_warning_visible():
    assert "Доступно" in PROFILE and "За столами" in PROFILE and "Ожидает вывода" in PROFILE
    assert "ТЕСТ — средства ненастоящие" in PROFILE
    assert "ТЕСТ · CASH НЕНАСТОЯЩИЙ" in TABLE_JS


def test_the_client_never_calls_real_money_fake():
    """`средства ненастоящие` is keyed on the mock mode, not on the CASH tab.

    Printed over a production balance those words are a lie; removed from a
    mock balance, they are the only thing telling a tester the chips are not
    savings. So the wording follows the mode, and the tab itself follows only
    whether CASH is on at all.
    """
    assert 'cashTab.hidden = config.cash_mode === "off";' in LOBBY_JS
    assert 'const test = mode === "mock";' in LOBBY_JS
    assert '"USDT TRC20 · реальные средства"' in LOBBY_JS
    # Nothing may gate a live CASH surface on the mock mode specifically.
    assert 'cash_mode === "mock"' not in LOBBY_JS.replace('cashMode === "mock"', "")
