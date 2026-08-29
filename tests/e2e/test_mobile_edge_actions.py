from __future__ import annotations

import math

import pytest
from playwright.sync_api import Page, sync_playwright


pytestmark = pytest.mark.e2e


def _state(
    to_call: float = 0,
    legal: list[str] | None = None,
    acting: str | None = "hero",
    player_count: int = 6,
) -> dict:
    players = {
        "hero": {"id": "hero", "name": "SweetGirl", "seat": 0, "stack": 97, "street_invested": 0, "folded": False, "is_bot": False, "profile_id": "hero", "hole_cards": ["4d", "Kc"]},
        "p1": {"id": "p1", "name": "P1", "seat": 1, "stack": 97, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p2": {"id": "p2", "name": "P2", "seat": 2, "stack": 112, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p3": {"id": "p3", "name": "P3", "seat": 3, "stack": 84, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p4": {"id": "p4", "name": "P4", "seat": 4, "stack": 103, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p5": {"id": "p5", "name": "P5", "seat": 5, "stack": 67, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
    }
    players = dict(list(players.items())[:player_count])
    return {
        "phase": "active", "hand_id": "layout-hand", "street": "flop", "players": players,
        "acting_player": acting, "legal_actions": legal or ["check", "fold", "bet", "all_in"],
        "current_bet": to_call, "min_raise_size": 2, "pot": 4, "board": ["9d", "Ac", "Td"],
        "history": [], "terminal": False, "action_deadline": None,
    }


def _open_table(
    page: Page,
    base_url: str,
    width: int,
    height: int,
    state: dict | None = None,
    viewer_state: str = "seated",
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{base_url}/table", wait_until="domcontentloaded")
    page.wait_for_function("window.Poker8LegacyView && document.getElementById('v040-poker8-v2-dynamic-seats-style')")
    page.evaluate(
        "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload.state,viewerState:payload.viewerState})",
        {"state": state or _state(), "viewerState": viewer_state},
    )
    page.wait_for_function("document.body.classList.contains('poker8-v2-sixmax')")
    page.wait_for_timeout(100)


def _centers(page: Page) -> list[tuple[float, float]]:
    return page.locator('.seat[data-visual-seat="1"],.seat[data-visual-seat="2"],.seat[data-visual-seat="3"],.seat[data-visual-seat="4"],.seat[data-visual-seat="5"]').evaluate_all(
        "els => els.map(el => { const r=el.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]; })"
    )


def _center(page: Page, selector: str) -> tuple[float, float]:
    return page.locator(selector).evaluate(
        "el => { const r = el.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
    )


def test_the_sit_button_occupies_the_hero_avatars_exact_place(online_server: str):
    """Changing from spectator to seated must replace the invitation in
    place, rather than making the avatar jump inside the same outer chair."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        try:
            for width, height in ((360, 800), (402, 874)):
                state = _state(player_count=3)
                _open_table(page, online_server, width, height, state, viewer_state="spectator")
                # The fixture serves the legacy view without a table query;
                # switch on the online identity rule before measuring the
                # spectator render so no local profile is promoted to hero.
                page.evaluate("window.Poker8OnlineTable = {}")
                page.evaluate(
                    "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'spectator'})",
                    state,
                )
                page.wait_for_function("!!document.querySelector('.seat.v040-sit-slot .empty-avatar')")
                page.wait_for_timeout(500)
                invitation = _center(page, ".seat.v040-sit-slot .empty-avatar")

                state["viewer_player_id"] = "hero"
                page.evaluate(
                    "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
                    state,
                )
                page.wait_for_function("!!document.querySelector('.seat[data-visual-seat=\"0\"] .player-avatar')")
                page.wait_for_timeout(500)
                avatar = _center(page, '.seat[data-visual-seat="0"] .player-avatar')

                assert invitation == pytest.approx(avatar, abs=1)
        finally:
            browser.close()


def test_opponents_form_one_equal_chord_arc_at_both_mobile_sizes(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        for width, height in ((360, 800), (402, 874)):
            _open_table(page, online_server, width, height)
            centers = _centers(page)
            assert len(centers) == 5
            chords = [math.dist(centers[i], centers[i + 1]) for i in range(4)]
            assert max(chords) - min(chords) <= 3
            assert centers[0][1] == pytest.approx(centers[4][1], abs=1)
            assert centers[1][1] == pytest.approx(centers[3][1], abs=1)
            assert centers[2][1] < centers[1][1] < centers[0][1]
        browser.close()


def _rects_intersect(first: dict, second: dict) -> bool:
    return not (
        first["right"] <= second["left"]
        or first["left"] >= second["right"]
        or first["bottom"] <= second["top"]
        or first["top"] >= second["bottom"]
    )


@pytest.mark.parametrize("player_count", [2, 3, 4, 5, 6])
def test_player_count_arcs_and_summary_do_not_overlap(online_server: str, player_count: int):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        for width, height in ((360, 800), (402, 874)):
            _open_table(page, online_server, width, height, _state(player_count=player_count))
            page.wait_for_function(
                "count => document.body.classList.contains(`p8-player-count-${count}`)",
                arg=player_count,
            )
            opponents = page.locator(
                '.seat.v040-dynamic-seat:not([data-visual-seat="0"])'
            ).evaluate_all(
                """els => els
                    .sort((a, b) => Number(a.dataset.visualSeat) - Number(b.dataset.visualSeat))
                    .map(el => { const r = el.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })"""
            )
            assert len(opponents) == player_count - 1
            for left, right in zip(opponents, reversed(opponents)):
                assert left[0] + right[0] == pytest.approx(width, abs=2)
                assert left[1] == pytest.approx(right[1], abs=2)
            if len(opponents) > 1:
                chords = [math.dist(opponents[index], opponents[index + 1]) for index in range(len(opponents) - 1)]
                assert max(chords) - min(chords) <= 3

            hero = page.locator('.seat[data-visual-seat="0"]').evaluate(
                "el => { const r = el.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }"
            )
            assert hero[0] == pytest.approx(width / 2, abs=1)
            assert hero[1] > max(point[1] for point in opponents)

            summary = page.locator(".v038-hud-summary").evaluate(
                "el => { const r = el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; }"
            )
            seat_rects = page.locator(".seat.v040-dynamic-seat").evaluate_all(
                "els => els.map(el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; })"
            )
            hud_rects = page.locator(
                ".seat.v040-dynamic-seat .seat-identity, .seat.v040-dynamic-seat .player-avatar"
            ).evaluate_all(
                "els => els.map(el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; })"
            )
            action_rects = page.locator("#actionButtons button:visible").evaluate_all(
                "els => els.map(el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; })"
            )
            assert all(rect["left"] >= -1 and rect["right"] <= width + 1 for rect in hud_rects)
            assert all(not _rects_intersect(summary, rect) for rect in seat_rects)
            assert all(not _rects_intersect(summary, rect) for rect in action_rects)
        browser.close()


@pytest.mark.parametrize("viewer_state", ["seated", "spectator"])
def test_call_bet_summary_stays_centered_when_the_table_resizes(
    online_server: str, viewer_state: str,
):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        for height in (640, 720, 800, 874):
            _open_table(page, online_server, 374, height, viewer_state=viewer_state)
            rects = page.locator(".pot-total,.v038-hud-summary.on-felt,#board").evaluate_all(
                """els => Object.fromEntries(els.map(el => {
                    const rect = el.getBoundingClientRect();
                    const key = el.classList.contains('pot-total') ? 'pot' : el.id === 'board' ? 'board' : 'summary';
                    return [key, {top:rect.top,bottom:rect.bottom}];
                }))"""
            )
            above = rects["summary"]["top"] - rects["pot"]["bottom"]
            below = rects["board"]["top"] - rects["summary"]["bottom"]
            assert above >= -1
            assert below >= -1
            assert above == pytest.approx(below, abs=1)
        browser.close()


def test_call_bet_summary_and_pot_share_visibility(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        try:
            _open_table(page, online_server, 374, 800)
            assert page.locator(".pot-total").is_visible()
            assert page.locator(".v038-hud-summary").is_visible()

            page.evaluate(
                "window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:null,viewerState:'seated'})"
            )
            page.wait_for_function("document.body.classList.contains('p8-no-pot')")
            assert not page.locator(".pot-total").is_visible()
            assert not page.locator(".v038-hud-summary").is_visible()
        finally:
            browser.close()


def test_mobile_header_and_center_stack_use_their_reserved_lanes(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        for width, height in ((360, 800), (402, 874)):
            _open_table(page, online_server, width, height)
            utility = page.locator("#mobileHeaderUtility").evaluate(
                "el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; }"
            )
            utility_debug = page.locator("#mobileHeaderUtility").evaluate(
                "el => ({marginLeft:getComputedStyle(el).marginLeft,position:getComputedStyle(el).position,parent:el.parentElement?.id,body:document.body.className})"
            )
            assert utility["right"] == pytest.approx(width - 8, abs=2), utility_debug

            layers = page.locator(
                "#potChips, .pot-total, #board, .v038-hud-summary"
            ).evaluate_all(
                """els => Object.fromEntries(els.map(el => {
                    const r=el.getBoundingClientRect();
                    const key=el.id || (el.classList.contains('pot-total') ? 'potTotal' : 'summary');
                    return [key,{left:r.left,right:r.right,top:r.top,bottom:r.bottom,cx:r.left+r.width/2,cy:r.top+r.height/2}];
                }))"""
            )
            chips = layers["potChips"]
            pot = layers["potTotal"]
            board_rect = layers["board"]
            summary = layers["summary"]
            assert chips["cy"] < pot["cy"] < summary["cy"] < board_rect["cy"]
            assert not _rects_intersect(chips, pot)
            assert not _rects_intersect(pot, summary)
            assert not _rects_intersect(summary, board_rect)
        browser.close()


def _action_keys(page: Page) -> list[str]:
    return page.locator("#actionButtons button:visible").evaluate_all("els => els.map(el => el.dataset.actionKey)")


def test_mobile_actions_hide_irrelevant_controls_and_touch_viewport_edges(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        _open_table(page, online_server, 360, 800, _state(0, ["check", "fold", "bet", "all_in"]))
        # ALL-IN | CHECK over FOLD | BET -- one arrangement on every street, so
        # a thumb that has learned where FOLD is does not have it move.
        assert _action_keys(page) == ["all_in", "check", "fold", "aggressive"]
        _open_table(page, online_server, 360, 800, _state(4, ["fold", "call", "raise", "all_in"]))
        # Same arrangement facing a bet, with CALL where CHECK was. ALL-IN
        # has a slot of its own now instead of appearing only as a relabelled
        # maximum raise.
        assert _action_keys(page) == ["all_in", "call", "fold", "aggressive"]
        boxes = page.locator("#actionButtons button:visible").evaluate_all(
            "els => els.map(el => { const r=el.getBoundingClientRect(); return {key:el.dataset.actionKey,left:r.left,right:r.right,height:r.height}; })"
        )
        for box in boxes:
            assert box["height"] >= 48
            assert box["left"] == pytest.approx(0, abs=1) or box["right"] == pytest.approx(360, abs=1)
        browser.close()


def test_bet_and_all_in_open_sizing_without_immediate_submission(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        submissions: list[str] = []
        page.route("**/api/game/**/action", lambda route: (submissions.append(route.request.post_data or ""), route.fulfill(status=200, json={})))
        state = _state(0, ["check", "fold", "bet", "all_in"])
        _open_table(page, online_server, 360, 800, state)

        page.locator('[data-action-key="aggressive"]').click()
        assert page.locator("#sizingWrap").get_attribute("aria-hidden") == "false"
        assert page.locator("#mobileSizingConfirm").is_visible()
        assert submissions == []
        page.locator("#mobileSizingConfirm").click()
        page.wait_for_timeout(50)
        assert len(submissions) == 1

        page.evaluate(
            "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
            state,
        )
        page.locator('[data-action-key="all_in"]').click()
        assert page.locator("#sizingWrap").get_attribute("aria-hidden") == "false"
        assert page.locator("#mobileSizingAmount").inner_text().strip()
        assert len(submissions) == 1
        page.locator("#mobileSizingConfirm").click()
        page.wait_for_timeout(50)
        assert len(submissions) == 2
        browser.close()


def test_vertical_bet_gesture_selects_amount_but_never_submits(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        submissions: list[str] = []
        page.route("**/api/game/**/action", lambda route: (submissions.append(route.request.post_data or ""), route.fulfill(status=200, json={})))
        _open_table(page, online_server, 360, 800, _state(0, ["check", "fold", "bet", "all_in"]))

        button = page.locator('[data-action-key="aggressive"]')
        box = button.bounding_box()
        assert box is not None
        initial = float(page.locator("#amount").input_value())
        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        page.mouse.move(354, 170, steps=8)
        assert page.locator("#mobileBetRail").get_attribute("aria-hidden") == "false"
        assert float(page.locator("#amount").input_value()) > initial
        assert submissions == []

        page.mouse.up()
        assert page.locator("#mobileBetRail").get_attribute("aria-hidden") == "true"
        assert page.locator("#mobileSizingConfirm").is_visible()
        assert submissions == []
        browser.close()


def test_timer_and_semantic_states_are_attached_to_player_huds(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        state = _state(0, ["check", "fold", "bet", "all_in"], acting="p3")
        state["players"]["p1"]["folded"] = True
        state["players"]["p4"]["all_in"] = True
        _open_table(page, online_server, 360, 800, state)

        active_avatar = page.locator('.seat[data-seat="3"] .avatar-wrap')
        turn_timer = active_avatar.locator(":scope > .v038-turn-timer")
        assert turn_timer.is_visible()
        assert page.locator(".table-frame > .v038-turn-timer").count() == 0
        assert page.locator(".v038-turn-context").count() == 0
        timer_paint = turn_timer.evaluate(
            """el => {
                const own = getComputedStyle(el);
                const ring = getComputedStyle(el, '::before');
                return {
                    background: own.backgroundColor,
                    image: own.backgroundImage,
                    mask: ring.maskImage || ring.webkitMaskImage,
                };
            }"""
        )
        assert timer_paint["background"] == "rgba(0, 0, 0, 0)"
        assert timer_paint["image"] == "none"
        assert "radial-gradient" in timer_paint["mask"]
        assert turn_timer.locator("b").evaluate(
            "el => el.getBoundingClientRect().left >= el.parentElement.getBoundingClientRect().right - 8"
        )
        hero_dealer = _state(0, ["check", "fold", "bet", "all_in"], acting="hero")
        hero_dealer["players"]["hero"]["position"] = "BTN"
        hero_dealer["players"]["p1"]["folded"] = True
        hero_dealer["players"]["p4"]["all_in"] = True
        page.evaluate(
            "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
            hero_dealer,
        )
        hero_timer = page.locator('.seat[data-visual-seat="0"] .avatar-wrap > .v038-turn-timer')
        dealer_rect = page.locator('.seat[data-visual-seat="0"] .dealer-button').evaluate(
            "el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; }"
        )
        timer_badge_rect = hero_timer.locator("b").evaluate(
            "el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; }"
        )
        timer_ring_rect = hero_timer.evaluate(
            "el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; }"
        )
        # The badge must not sit on the number. It may overlap the ring: the
        # ring is 54px around a 44px avatar, so anything placed beside the
        # avatar -- which is where the dealer button belongs, mirroring the
        # timer on the other side -- crosses its outer edge by design. The
        # older assertion demanded the badge clear the ring entirely, which
        # asked for a dealer button pushed off the seat.
        assert not _rects_intersect(dealer_rect, timer_badge_rect)
        assert dealer_rect["right"] <= timer_ring_rect["right"]

        folded = page.locator('.seat[data-seat="1"] .seat-card')
        assert 0.35 <= float(folded.evaluate("el => getComputedStyle(el).opacity")) <= 0.5
        folded_back_opacity = folded.locator(".avatar-wrap").evaluate("el => getComputedStyle(el, '::before').opacity")
        assert float(folded_back_opacity) == 0

        neutral_accents = page.locator('.seat[data-seat="2"], .seat[data-seat="5"]').evaluate_all(
            "els => els.map(el => getComputedStyle(el).getPropertyValue('--seat-accent').trim())"
        )
        assert len(set(neutral_accents)) == 1

        page.evaluate("document.getElementById('connectionStatus').textContent = 'reconnecting'")
        page.wait_for_function("document.getElementById('mobileConnectionDot').dataset.state === 'reconnecting'")
        assert page.locator("#mobileConnectionDot").get_attribute("aria-label") == "Переподключение"

        waiting = _state(acting=None)
        page.evaluate(
            "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
            waiting,
        )
        page.evaluate(
            "window.dispatchEvent(new CustomEvent('poker8:ready-countdown', {detail:{endsAt:Date.now() + 5000}}))"
        )
        ready_timer = page.locator('.seat[data-visual-seat="0"] .avatar-wrap > .v038-ready-countdown')
        assert ready_timer.is_visible()
        assert page.locator(".felt > .v038-ready-countdown").count() == 0
        browser.close()


def test_mobile_sizes_hold_and_compact_actions_continue_at_781(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        for width, height in ((360, 800), (402, 874)):
            _open_table(page, online_server, width, height)
            opponent_avatar = page.locator('.seat[data-visual-seat="1"] .player-avatar').bounding_box()
            board_card = page.locator("#board .card").first.bounding_box()
            hero_card = page.locator('.seat[data-visual-seat="0"] .player-cards .card').first.bounding_box()
            assert opponent_avatar and opponent_avatar["width"] >= 44
            assert board_card and board_card["width"] >= 44
            assert hero_card and hero_card["width"] >= board_card["width"]
            assert page.locator(".action-panel").evaluate("el => getComputedStyle(el).backgroundColor") == "rgba(0, 0, 0, 0)"

        page.set_viewport_size({"width": 781, "height": 900})
        page.wait_for_timeout(100)
        assert page.locator("body").evaluate("el => el.classList.contains('poker8-desktop-v2')")
        assert page.locator("#actionButtons").get_attribute("data-v038-reference-actions") == "1"
        assert page.locator("#actionButtons [data-edge]").count() == 4

        page.set_viewport_size({"width": 360, "height": 800})
        page.wait_for_function("document.body.classList.contains('poker8-v2-sixmax')")
        browser.close()


def test_desktop_actions_live_inside_the_table_without_a_layout_row(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(device_scale_factor=1)
        try:
            _open_table(page, online_server, 1192, 877)
            page.wait_for_function("document.body.classList.contains('poker8-desktop-v2')")

            measured = page.evaluate(
                """() => {
                    const box = el => {
                        const r = el.getBoundingClientRect();
                        return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,cx:r.left+r.width/2};
                    };
                    const frame = document.querySelector('.table-frame');
                    const hero = document.querySelector('.seat[data-visual-seat="0"]');
                    const actions = [...document.querySelectorAll('#actionButtons [data-edge]')].map(el => ({
                        edge:el.dataset.edge, slot:el.dataset.slot, box:box(el), visible:el.checkVisibility(),
                    }));
                    return {
                        frame:box(frame), hero:box(hero), actions,
                        panelParent:document.querySelector('.action-panel').parentElement.className,
                        hudHeight:getComputedStyle(document.body).getPropertyValue('--p8-hud-h').trim(),
                        scrollHeight:document.documentElement.scrollHeight,
                        viewportHeight:innerHeight,
                    };
                }"""
            )
            assert "table-frame" in measured["panelParent"]
            assert measured["hudHeight"] == "0px"
            assert measured["scrollHeight"] <= measured["viewportHeight"] + 1
            assert len(measured["actions"]) == 4 and all(action["visible"] for action in measured["actions"])
            assert {action["edge"] for action in measured["actions"]} == {"left", "right"}
            assert {action["slot"] for action in measured["actions"]} == {"top", "bottom"}
            for action in measured["actions"]:
                rect = action["box"]
                assert rect["left"] >= measured["frame"]["left"]
                assert rect["right"] <= measured["frame"]["right"]
                assert rect["top"] >= measured["frame"]["top"]
                assert rect["bottom"] <= measured["frame"]["bottom"]
                if action["edge"] == "left":
                    assert rect["right"] < measured["hero"]["cx"]
                else:
                    assert rect["left"] > measured["hero"]["cx"]

            page.locator('[data-action-key="aggressive"]').click()
            page.wait_for_function("document.body.classList.contains('v038-sizing-open')")
            sizing = page.locator("#sizingWrap")
            assert sizing.is_visible()
            sizing_box = sizing.bounding_box()
            assert sizing_box is not None
            assert sizing_box["x"] >= measured["frame"]["left"]
            assert sizing_box["x"] + sizing_box["width"] <= measured["frame"]["right"]
            assert sizing_box["y"] >= measured["frame"]["top"]
            assert sizing_box["y"] + sizing_box["height"] <= measured["frame"]["bottom"]
            assert not page.locator('#actionButtons [data-edge="left"]').first.is_visible()
            page.locator("#mobileSizingCancel").click()
            page.wait_for_function("!document.body.classList.contains('v038-sizing-open')")

            frame_before = {
                key: measured["frame"][key]
                for key in ("left", "right", "top", "bottom")
            }
            page.evaluate(
                "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
                _state(acting="p1"),
            )
            page.wait_for_timeout(100)
            frame_after = page.locator(".table-frame").evaluate(
                "el => { const r=el.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; }"
            )
            assert frame_after == pytest.approx(frame_before, abs=1)
        finally:
            browser.close()
