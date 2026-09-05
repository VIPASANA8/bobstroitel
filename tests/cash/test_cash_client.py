from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOBBY = (ROOT / "static" / "lobby.html").read_text(encoding="utf-8")
LOBBY_JS = (ROOT / "static" / "lobby.js").read_text(encoding="utf-8")
PROFILE = (ROOT / "static" / "profile.html").read_text(encoding="utf-8")
PROFILE_JS = (ROOT / "static" / "profile.js").read_text(encoding="utf-8")
CASHIER_JS = (ROOT / "static" / "cash-cashier.js").read_text(encoding="utf-8")
TABLE_JS = (ROOT / "static" / "online-table.js").read_text(encoding="utf-8")


def test_lobby_has_explicit_training_and_cash_catalogues():
    assert 'data-asset="PLAY"' in LOBBY
    assert 'data-asset="CASH_USDT"' in LOBBY
    assert "ТЕСТ — средства ненастоящие" in LOBBY
    assert "asset=${asset}" in LOBBY_JS
    assert "/api/lobby/quick-play?asset=${asset}" in LOBBY_JS


def test_cash_ui_keeps_usdt_payment_fields_separate_from_cash_units():
    # The cashier lives in the profile; the lobby only says what a seat costs.
    assert 'id="depositUsdt"' in PROFILE
    assert 'id="withdrawUsdt"' in PROFILE
    assert 'id="withdrawAddress"' in PROFILE
    assert "1 USDT = 10 единиц CASH" in LOBBY and "1 USDT = 10 единиц CASH" in PROFILE
    assert "BigInt" in LOBBY_JS
    assert "cashUnitsToChips" in LOBBY_JS
    assert "BigInt" in CASHIER_JS


def test_the_lobby_sends_the_player_to_one_cashier():
    """Two places showing the same balance is two answers. The lobby shows
    what is spendable at a table and links to the profile for the rest."""
    assert '/static/profile.html#cash' in LOBBY
    assert "Открыть CASH-кассу" in LOBBY
    for gone in ('id="depositDialog"', 'id="withdrawDialog"', 'id="cashEscrow"', 'id="cashWithdrawal"'):
        assert gone not in LOBBY
    assert "/api/cash/deposits" not in LOBBY_JS
    assert "/api/cash/withdrawals" not in LOBBY_JS


def test_cash_ui_exposes_rub_p2p_without_changing_trc20_withdrawals():
    assert 'id="cashFiatDeposit"' in PROFILE
    assert 'id="fiatDepositUsdt"' in PROFILE
    assert "/api/cash/fiat-orders" in CASHIER_JS
    assert "Я оплатил" in CASHIER_JS
    assert "ждём подтверждения трейдера" in CASHIER_JS
    # The cashier survives a reload, shows the expiry and never credits itself.
    assert "/api/cash/fiat-orders/active" in CASHIER_JS
    assert "Осталось" in CASHIER_JS
    assert "Комиссия пополнения" in CASHIER_JS
    assert "simulate-trader-confirmation" not in CASHIER_JS
    assert 'id="withdrawAddress"' in PROFILE


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
    assert "'USDT TRC20 · реальные средства'" in PROFILE_JS
    # Nothing may gate a live CASH surface on the mock mode specifically.
    assert 'cash_mode === "mock"' not in LOBBY_JS.replace('cashMode === "mock"', "")
    # The profile's cashier tab follows the wallet, never the mock mode: the
    # mode picks the wording and the withdraw button's label, nothing else.
    assert "$('cashModeTab').hidden = false;" in PROFILE_JS
    assert "hidden = !test" not in PROFILE_JS.replace(
        "$('cashModeTab').querySelector('small').hidden = !test;", "")
