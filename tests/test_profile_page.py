from pathlib import Path

HTML = Path("static/profile.html").read_text(encoding="utf-8")
JS = Path("static/profile.js").read_text(encoding="utf-8")
CSS = Path("static/profile.css").read_text(encoding="utf-8")


def test_profile_page_has_wallet_history_and_return_slot():
    for element_id in ("profileName", "levelProgress", "walletBalance", "handHistory", "returnToTable"):
        assert f'id="{element_id}"' in HTML


def test_the_page_actually_has_a_stylesheet():
    """Every class below the shared header shipped unstyled: the markup was
    written, network.css never got the rules, so the whole page rendered as
    bare HTML."""
    for selector in (
        ".profile-hero", ".profile-level", ".profile-dashboard", ".profile-section",
        ".history-list", ".history-row", ".return-link", ".topup-card",
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
    assert "hand.hand_id" not in JS
    assert "player.you" in JS, "the viewer's own row is what makes a result"
    for kind in ("buy_in", "add_on", "return", "settlement", "faucet_grant"):
        assert kind + ":" in JS, kind


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
    assert "renderTopUp(Boolean(config.self_top_up_enabled))" in JS
    assert "renderTopUp(false)" in JS, "and the same when the page fails to load"


def test_pressing_a_balance_reaches_the_top_up():
    lobby = Path("static/lobby.html").read_text(encoding="utf-8")
    assert 'href="/static/profile.html#topup"' in lobby
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
