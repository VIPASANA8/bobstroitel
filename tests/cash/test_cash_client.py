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
    # Stated once per surface: the lobby under its balance, the cashier in
    # its own heading. It used to be printed twice on the profile, once in
    # the heading and again under the withdraw button.
    assert "1 USDT = 10 единиц CASH" in LOBBY
    assert "1 USDT = 10 CASH" in PROFILE
    assert PROFILE.count("1 USDT = 10") == 1
    assert "BigInt" in LOBBY_JS
    assert "cashUnitsToChips" in LOBBY_JS
    assert "BigInt" in CASHIER_JS


def test_the_deposit_limits_on_screen_are_the_ones_the_server_enforces():
    """The P2P hint read 20-500 while the service refused anything over 300:
    a player typing 400 got the raw refusal instead of the form saying no."""
    from cash.fiat_orders import MAX_DEPOSIT_MICROS, MIN_DEPOSIT_MICROS

    low, high = MIN_DEPOSIT_MICROS // 1_000_000, MAX_DEPOSIT_MICROS // 1_000_000
    assert f"Введите сумму ({low}$–{high}$)" in PROFILE


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
    assert 'data-method="fiat"' in PROFILE
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


def _js_keys(source: str, name: str) -> set[str]:
    """The keys of a flat object literal in the cashier, by name."""
    import re

    block = source[source.index("const " + name + " = {"):]
    return set(re.findall(r"^\s+(\w+):", block[:block.index("\n  };")], re.M))


def test_the_client_renders_every_state_the_partner_can_reach():
    """cash/fiat_p2p.py folds eleven pservice statuses into these local ones.
    A state with no branch of its own fell through to "оплата отмечена, ждём
    подтверждения трейдера" -- which told a player their payment was being
    confirmed while the order was still out looking for a trader.
    """
    from cash.fiat_p2p import PSERVICE_STATUS

    covered = _js_keys(CASHIER_JS, "FIAT_OPEN") | _js_keys(CASHIER_JS, "FIAT_CLOSED")
    assert set(PSERVICE_STATUS.values()) <= covered, set(PSERVICE_STATUS.values()) - covered


def test_cancelling_stops_being_offered_once_the_player_says_they_paid():
    """Between "я оплатил" and the trader's answer the rubles have already
    left; cancelling there is how they go missing."""
    block = CASHIER_JS[CASHIER_JS.index("const FIAT_OPEN = {"):]
    block = block[:block.index("\n  };")]
    for state in ("waiting_trader", "clarifying"):
        line = next(row for row in block.splitlines() if row.strip().startswith(state + ":"))
        assert "cancel: false" in line, state


def test_the_payment_panel_can_be_copied_rather_than_retyped():
    """A card number read off a phone screen by eye is how a transfer reaches
    the wrong account -- and the mock printed `4276 **** **** 1000`, which
    cannot be paid at all, in the one mode the pilot actually runs in."""
    assert 'class="pay-copy" data-copy=' in CASHIER_JS
    assert "navigator.clipboard.writeText" in CASHIER_JS
    # Telegram's webview does not always hand out the async clipboard, and a
    # copy button that silently does nothing is worse than none.
    assert 'document.execCommand("copy")' in CASHIER_JS
    # The card reaches the clipboard without the bank and the holder after it.
    assert 'String(order.requisites).split(" · ")[0]' in CASHIER_JS
    assert "**** ****" not in (ROOT / "cash" / "fiat_p2p.py").read_text(encoding="utf-8")
