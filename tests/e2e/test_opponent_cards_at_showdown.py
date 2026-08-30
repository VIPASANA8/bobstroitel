"""Both layouts render the server's public cards, not an automatic end reveal."""

import pytest
from playwright.sync_api import expect, sync_playwright

from poker.engine import PokerEngine
from poker.models import ActionType
from tests.e2e.test_mobile_edge_actions import _open_table
from tests.test_uncontested_cards_stay_private import _call_or_check


pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("width,height", [(390, 844), (1192, 877)])
@pytest.mark.parametrize("showdown", [False, True])
def test_opponent_cards_open_only_with_two_remaining_players(online_server, width, height, showdown):
    engine = PokerEngine()
    state = engine.new_hand([
        {"id": pid, "name": pid, "seat": i, "stack": 100, "is_bot": i > 0}
        for i, pid in enumerate(["hero", "p1", "p2"])
    ])
    engine.apply_action(state, "hero", ActionType.FOLD)
    if showdown:
        while not state.terminal:
            _call_or_check(engine, state)
    else:
        engine.apply_action(state, state.acting_player, ActionType.FOLD)
    payload = state.to_dict(viewer_player_id="hero")
    payload.update(phase="result", legal_actions=[])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            _open_table(page, online_server, width, height, payload)
            winner_cards = page.locator('.seat[data-seat="2"] .player-cards .card')
            expect(winner_cards).to_have_count(2, timeout=15000)
            assert winner_cards.locator(".card-rank").count() == (2 if showdown else 0)
            assert page.locator('.seat[data-seat="2"] .player-cards .card.back').count() == (0 if showdown else 2)
            if not showdown:
                splashes = page.evaluate("""async state => {
                    const original = showStreetSplash;
                    let calls = 0;
                    showStreetSplash = async () => { calls++; };
                    try { await animateShowdownReveal(null, state); }
                    finally { showStreetSplash = original; }
                    return calls;
                }""", payload)
                assert splashes == 0
        finally:
            browser.close()
