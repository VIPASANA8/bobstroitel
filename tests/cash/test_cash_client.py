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
    assert "<small>$$$</small>" in LOBBY
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


def test_the_money_surfaces_are_marked_without_naming_a_mode():
    """CASH is still marked apart from practice chips everywhere it appears --
    the tab, the cashier and the felt -- but the mark is the money, not a
    claim about how real it is."""
    assert "Доступно" in PROFILE and "За столами" in PROFILE and "Ожидает вывода" in PROFILE
    assert "<small>$$$</small>" in PROFILE
    assert '"$$$"' in TABLE_JS


def test_the_client_makes_no_claim_about_how_real_the_money_is():
    """It used to say both, keyed on the mode: "средства ненастоящие" over a
    mock balance and "реальные средства" over a live one. The first was asked
    for and removed; the second must not survive it alone, because that is the
    half that lies -- it would print "real funds" over the mock pilot.

    So the client says neither, and what CASH is stays a deployment question
    the operator answers, not a sentence on the felt.
    """
    for name, source in (
        ("lobby.html", LOBBY), ("lobby.js", LOBBY_JS),
        ("profile.html", PROFILE), ("profile.js", PROFILE_JS),
        ("cash-cashier.js", CASHIER_JS),
    ):
        for claim in ("ненастоящ", "реальные средства", "ТЕСТ", "TEST", "mock", "MOCK", "Mock"):
            assert claim not in source, f"{name} still says {claim!r}"
    # The tab follows only whether CASH is on at all, and the cashier follows
    # the wallet -- neither is gated on which mode CASH happens to run in.
    assert 'cashTab.hidden = config.cash_mode === "off";' in LOBBY_JS
    assert "$('cashModeTab').hidden = false;" in PROFILE_JS
    assert "cash_mode" not in PROFILE_JS
