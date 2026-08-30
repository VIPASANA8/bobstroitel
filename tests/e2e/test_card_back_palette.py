"""Phone and desktop share the same quiet back, independent of seat accents."""

import pytest
from playwright.sync_api import sync_playwright

from tests.e2e.test_mobile_edge_actions import _open_table, _state


pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("hidden_hero", [False, True])
def test_card_backs_share_graphite_turquoise_paint_on_phone_and_desktop(online_server, hidden_hero):
    state = _state()
    state.update(viewer_player_id="hero", board=["9d", "Ac", "Td", "2h", "7s"])
    if hidden_hero:
        state["players"]["hero"]["hole_cards"] = ["??", "??"]
    reference = None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for width, height in [(390, 844), (1192, 877)]:
                _open_table(page, online_server, width, height, state)
                if not hidden_hero:
                    # Back exclusions must not outrank face-up suit/combo accents.
                    red = page.locator('.viewer-seat .player-cards .card.red').first
                    assert red.evaluate("el => getComputedStyle(el).borderTopColor") == "rgb(255, 103, 77)"
                    red.evaluate("el => el.classList.add('hand-combo')")
                    assert red.evaluate("el => getComputedStyle(el).borderTopColor") == "rgb(241, 200, 103)"
                paints = page.locator('.player-cards .card.back').evaluate_all("""cards =>
                    cards.map(card => {
                        const style = getComputedStyle(card);
                        return {background:style.backgroundImage,
                                border:style.borderTopColor, shadow:style.boxShadow};
                    })
                """)
                assert len(paints) == (12 if hidden_hero else 10)
                for paint in paints:
                    assert "rgb(7, 26, 26)" in paint["background"]
                    assert "rgb(11, 32, 32)" in paint["background"]
                    assert "rgba(22, 207, 160, 0.22)" in paint["background"]
                    assert paint["border"] == "rgba(53, 240, 192, 0.55)"
                    assert "rgba(53, 240, 192, 0.18)" in paint["shadow"]
                    if reference is None:
                        reference = paint
                    assert paint == reference
        finally:
            browser.close()
