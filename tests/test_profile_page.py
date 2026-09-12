from pathlib import Path

HTML = Path("static/profile.html").read_text(encoding="utf-8")
JS = Path("static/profile.js").read_text(encoding="utf-8")
CSS = Path("static/profile.css").read_text(encoding="utf-8")
CUBE_CSS = Path("static/cube.css").read_text(encoding="utf-8")


def test_profile_page_has_wallet_history_and_return_slot():
    for element_id in ("profileName", "levelProgress", "walletBalance", "cashHistory", "returnToTable"):
        assert f'id="{element_id}"' in HTML


def test_profile_supports_poker_and_cube_contexts():
    for element_id in (
        "brandLogo", "backToProduct", "cashModeLabel", "profileModeLabel",
        "pokerProfile", "cubeProfile", "cashHistory",
    ):
        assert f'id="{element_id}"' in HTML
    assert "Профиль CUBE пока пуст" in HTML


def test_referrals_are_a_first_class_accessible_profile_tab():
    assert 'id="referralModeTab"' in HTML
    assert 'aria-controls="referralSection"' in HTML
    assert 'id="referralSection" role="tabpanel" aria-labelledby="referralModeTab"' in HTML
    referral = HTML[HTML.index('id="referralSection"'):]
    for element_id in (
        "referralLink", "referralShare", "referralCopy", "referralInvited",
        "referralPending", "referralPaid", "referralCarryover",
        "referralError", "referralRetry", "referralStatus",
    ):
        assert f'id="{element_id}"' in referral
    assert "15% первые 30 дней, затем 5%" in referral
    assert "Получить награду" not in referral


def test_referral_panel_uses_the_existing_profile_tokens_and_phone_layout():
    for selector in (
        ".referral-section{", ".referral-hero{", ".referral-link-row{",
        ".referral-summary{", ".referral-carryover{",
    ):
        assert selector in CSS
    assert "var(--accent)" in CSS[CSS.index(".referral-section{"):]
    phone = CSS[CSS.index("@media(max-width:580px){"):]
    assert ".referral-actions{flex-direction:column}" in phone


def test_referral_tab_uses_an_icon_only_at_the_phone_breakpoint():
    assert '<span class="referral-tab-label">Рефералы</span>' in HTML
    assert '<span class="referral-tab-icon" aria-hidden="true">🔗</span>' in HTML
    desktop = CSS[:CSS.index("@media(max-width:580px){")]
    phone = CSS[CSS.index("@media(max-width:580px){"):]
    assert ".referral-tab-icon{display:none}" in desktop
    assert ".referral-tab-label{display:none}" in phone
    assert ".referral-tab-icon{display:inline}" in phone


def test_history_belongs_only_to_the_shared_cashier():
    cash_half = HTML[HTML.index('id="cashSection"'):]
    poker_half = HTML[HTML.index('id="pokerProfile"'):HTML.index('id="cashSection"')]
    assert 'aria-label="История кассы"' in cash_half
    for name in ("Общее", "CUBE", "POKER", "Операции"):
        assert f'>{name}</button>' in cash_half
    assert 'aria-label="Тип истории"' not in poker_half
    assert "$('allHistoryPanel').setAttribute('aria-busy', 'false')" in JS


def test_the_page_actually_has_a_stylesheet():
    """Every class below the shared header shipped unstyled: the markup was
    written, network.css never got the rules, so the whole page rendered as
    bare HTML."""
    for selector in (
        ".profile-hero", ".profile-level", ".profile-dashboard", ".profile-section",
        ".history-list", ".history-row", ".return-link", ".topup-card",
        ".history-error",
        ".stats-grid", ".stats-records", ".profile-wallet",
        ".achievement-list", ".achievement", ".achievement-bar",
        ".mission-list", ".mission",
    ):
        assert selector + "{" in CSS, selector
    assert 'href="/static/profile.css?v=' in HTML


def test_there_is_a_way_back_to_the_lobby_on_a_phone():
    """The text link it replaces is display:none below 760px -- which is every
    phone, i.e. the width this is played at."""
    assert 'class="profile-back" href="/"' in HTML
    assert 'class="text-link"' not in HTML


def test_the_rows_say_something():
    """They printed a raw hand id with a player count, and the ledger printed
    the engine's own word for the transaction."""
    assert "escapeHtml(hand.hand_id)" not in JS
    assert "player.you" in JS, "the viewer's own row is what makes a result"
    for title in ("Выигрыш в POKER", "Проигрыш в POKER", "Пополнение", "Вывод средств"):
        assert title in JS, title
    assert "LEDGER_KINDS" in JS
    assert "representedHands.has(row.reference_id)" in JS
    assert "Тренировочные фишки" in JS


def test_the_next_level_line_is_about_the_next_level():
    """It printed the total wins so far under a label reading
    "до следующего уровня" -- two unrelated numbers stacked on each other.

    The ladder is XP now, so the line has to be the XP still owed; wins are a
    tally of their own and buy no levels at all.
    """
    assert "wins_to_next_level" not in JS, "wins stopped being what a level costs"
    assert "profile.xp_to_next_level" in JS
    assert "Ещё ${number(left)} XP" in JS
    router = Path("app/routers/profiles.py").read_text(encoding="utf-8")
    assert '"xp_to_next_level": xp_to_next_level(xp)' in router
    assert '"level": level' in router and '"rank": rank_for_level(level)' in router


def test_top_up_asks_before_it_offers():
    """/api/profile/play-top-up is 404 on a deployment on purpose. A panel that
    says so beats a button that fails when pressed."""
    assert "self_top_up_enabled" in Path("app/routers/config.py").read_text(encoding="utf-8")
    assert "renderTopUp(product === 'poker' && Boolean(config.self_top_up_enabled))" in JS
    assert "renderTopUp(false)" in JS, "and the same when the page fails to load"


def test_pressing_a_balance_reaches_the_top_up():
    lobby = Path("static/lobby.html").read_text(encoding="utf-8")
    assert 'href="/static/profile.html?app=poker#topup"' in lobby
    assert 'id="topup" class="profile-wallet"' in HTML
    assert 'id="topupDetails" hidden' in HTML


def test_a_failed_load_says_so_instead_of_a_column_of_dashes():
    assert "Не удалось загрузить историю." in JS
    assert 'class="profile-error"' in HTML and ".profile-error{" in CSS


def test_every_page_shares_one_cache_token():
    """profile.html sat on aurora-gold-9 while the lobby moved with the rest,
    so no network.css change ever reached it."""
    import re
    tokens = set()
    for name in ("index.html", "lobby.html", "profile.html"):
        tokens |= set(re.findall(r"\?v=([a-z0-9-]+)", Path("static", name).read_text(encoding="utf-8")))
    assert len(tokens) == 1, tokens


def test_product_headers_link_to_the_other_game_and_their_own_brand():
    lobby = Path("static/lobby.html").read_text(encoding="utf-8")
    cube = Path("static/cube.html").read_text(encoding="utf-8")
    cube_js = Path("static/cube.js").read_text(encoding="utf-8")
    assert "/static/profile.html?app=poker" in lobby
    assert "/static/profile.html?app=cube#cash" in cube_js
    assert 'class="cube-back" href="/" aria-label="POKER"' in cube
    assert 'class="brand-word" href="/cube" aria-label="CUBE"' in cube
    assert "$('brandLogo').href = cube ? '/cube' : '/';" in JS
    assert "$('backToProduct').href = cube ? '/' : '/cube';" in JS


def test_cube_play_card_has_no_unguarded_motion():
    assert 'transition:filter .18s,transform .18s' not in CSS
    assert '.cube-play-card:hover{filter:brightness(1.08);transform' not in CSS


def test_cube_context_reuses_cashier_layout_with_cube_tokens():
    assert ".profile-page.cube-context" in CSS
    assert "--accent:#c8ff31" in CSS.replace(" ", "")
    assert ".cube-profile-empty{" in CSS


def test_cube_page_chrome_owns_the_tokens_used_by_its_profile_link():
    cube_page_rule = CUBE_CSS[CUBE_CSS.index(".cube-page{"):CUBE_CSS.index("}", CUBE_CSS.index(".cube-page{"))]
    for token in ("--lime:", "--panel:", "--line:"):
        assert token in cube_page_rule


def test_the_colour_says_what_kind_of_money_before_which_way_it_went():
    """Practice chips are purple like the training side, a deposit or a
    payout is gold; green and red are kept for a real result at a table."""
    assert "'kind-play'" in JS and "'kind-operation'" in JS
    assert ".history-row.kind-play .history-amount" in CSS
    assert "var(--accent)" in CSS.split(".history-row.kind-play .history-amount")[1].split("\n")[0]
    assert ".history-row.kind-operation .history-amount" in CSS
    assert "#f4c76b" in CSS.split(".history-row.kind-operation .history-amount")[1].split("\n")[0]
    # The kind rule comes after the outcome rule, so it wins at equal specificity.
    assert CSS.index(".history-row.win .history-amount") < CSS.index(".history-row.kind-play .history-amount")
