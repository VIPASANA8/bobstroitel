"""Backs share the hero's physical size; revealed hands share its avatar anchor."""

import pytest
from playwright.sync_api import sync_playwright

from tests.e2e.test_mobile_edge_actions import _open_table, _state


pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("width,height", [(781, 900), (1192, 877), (1920, 1080)])
@pytest.mark.parametrize("revealed", [False, True])
def test_every_seats_cards_match_the_hero(online_server, width, height, revealed):
    state = _state(acting="p2")
    state["viewer_player_id"] = "hero"
    if revealed:
        for player in state["players"].values():
            player["hole_cards"] = ["4d", "Kc"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            _open_table(page, online_server, width, height, state)
            page.wait_for_timeout(500)
            geometry = page.locator('.seat[data-visual-seat]').evaluate_all("""seats => seats.map(seat => {
                const pair = seat.querySelector('.player-cards');
                const avatar = seat.querySelector('.avatar-wrap');
                const pr = pair.getBoundingClientRect(), ar = avatar.getBoundingClientRect();
                const frame = document.querySelector('.table-frame').getBoundingClientRect();
                const sizes = [...pair.querySelectorAll('.card')].map(card => {
                    const r = card.getBoundingClientRect(), m = new DOMMatrix(getComputedStyle(card).transform);
                    const scale = Math.hypot(m.a, m.b), c = Math.abs(m.a)/scale, s = Math.abs(m.b)/scale;
                    return {w:(r.width*c-r.height*s)/(c*c-s*s), h:(r.height*c-r.width*s)/(c*c-s*s)};
                });
                return {hero:seat.dataset.visualSeat === '0', sizes,
                    rankSize:pair.querySelector('.card-rank') && getComputedStyle(pair.querySelector('.card-rank')).fontSize,
                    suitSize:pair.querySelector('.card-suit') && getComputedStyle(pair.querySelector('.card-suit')).fontSize,
                    overlap:pr.bottom-ar.top,
                    clipped:[...pair.querySelectorAll('.card')].some(card => {
                        const r=card.getBoundingClientRect();
                        return r.top < frame.top-1 || r.bottom > frame.bottom+1;
                    }),
                    foreground:+getComputedStyle(pair).zIndex > +getComputedStyle(avatar).zIndex};
            })""")
            assert len(geometry) == 6
            hero = next(seat for seat in geometry if seat["hero"])
            for seat in geometry:
                assert len(seat["sizes"]) == 2
                for size in seat["sizes"]:
                    assert size == pytest.approx(hero["sizes"][0], abs=0.6)
                if revealed:
                    assert not seat["clipped"]
                    assert seat["rankSize"] == hero["rankSize"]
                    assert seat["suitSize"] == hero["suitSize"]
                    assert seat["foreground"]
                    assert seat["overlap"] == pytest.approx(hero["overlap"], abs=0.6)
        finally:
            browser.close()
