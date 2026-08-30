"""Every desktop card has the same painted edge lengths, including fanned pairs."""

import pytest
from playwright.sync_api import sync_playwright

from tests.e2e.test_mobile_edge_actions import _open_table, _state


pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("width,height", [(781, 900), (1192, 877), (1920, 1080)])
def test_desktop_hero_board_and_backs_share_one_card_size(online_server, width, height):
    state = _state()
    state.update(viewer_player_id="hero", board=["9d", "Ac", "Td", "2h", "7s"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            _open_table(page, online_server, width, height, state)
            page.wait_for_timeout(400)
            sizes = page.evaluate("""() => {
                const size = el => {
                    const r = el.getBoundingClientRect();
                    const m = new DOMMatrix(getComputedStyle(el).transform);
                    // Undo the fan's axis-aligned bounding box, not its scale:
                    // rotated cards have wider boxes but equal physical edges.
                    const scale = Math.hypot(m.a, m.b);
                    const c = Math.abs(m.a) / scale, s = Math.abs(m.b) / scale;
                    return {w:(r.width*c-r.height*s)/(c*c-s*s),
                            h:(r.height*c-r.width*s)/(c*c-s*s)};
                };
                return {
                    board:[...document.querySelectorAll('.board-cards .card')].map(size),
                    hero:[...document.querySelectorAll('.seat[data-visual-seat="0"] .player-cards .card')].map(size),
                    backs:[...document.querySelectorAll('.player-cards .card.back')].map(size),
                };
            }""")
            assert len(sizes["board"]) == 5
            assert len(sizes["hero"]) == 2
            assert len(sizes["backs"]) == 10
            reference = sizes["board"][0]
            for group in sizes.values():
                for card in group:
                    assert card == pytest.approx(reference, abs=0.6)
        finally:
            browser.close()
