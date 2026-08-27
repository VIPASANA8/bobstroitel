from __future__ import annotations

import math

import pytest
from playwright.sync_api import Page, sync_playwright


pytestmark = pytest.mark.e2e


def _state(to_call: float = 0, legal: list[str] | None = None, acting: str = "hero") -> dict:
    players = {
        "hero": {"id": "hero", "name": "SweetGirl", "seat": 0, "stack": 97, "street_invested": 0, "folded": False, "is_bot": False, "profile_id": "hero", "hole_cards": ["4d", "Kc"]},
        "p1": {"id": "p1", "name": "P1", "seat": 1, "stack": 97, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p2": {"id": "p2", "name": "P2", "seat": 2, "stack": 112, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p3": {"id": "p3", "name": "P3", "seat": 3, "stack": 84, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p4": {"id": "p4", "name": "P4", "seat": 4, "stack": 103, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
        "p5": {"id": "p5", "name": "P5", "seat": 5, "stack": 67, "street_invested": 0, "folded": False, "is_bot": True, "hole_cards": ["??", "??"]},
    }
    return {
        "phase": "active", "hand_id": "layout-hand", "street": "flop", "players": players,
        "acting_player": acting, "legal_actions": legal or ["check", "fold", "bet", "all_in"],
        "current_bet": to_call, "min_raise_size": 2, "pot": 4, "board": ["9d", "Ac", "Td"],
        "history": [], "terminal": False, "action_deadline": None,
    }


def _open_table(page: Page, base_url: str, width: int, height: int, state: dict | None = None) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{base_url}/table", wait_until="domcontentloaded")
    page.wait_for_function("window.Poker8LegacyView && document.getElementById('v038-poker8-v2-cinematic-table-style')")
    page.evaluate(
        "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
        state or _state(),
    )
    page.wait_for_function("document.body.classList.contains('poker8-v2-sixmax')")
    page.wait_for_timeout(100)


def _centers(page: Page) -> list[tuple[float, float]]:
    return page.locator('.seat[data-visual-seat="1"],.seat[data-visual-seat="2"],.seat[data-visual-seat="3"],.seat[data-visual-seat="4"],.seat[data-visual-seat="5"]').evaluate_all(
        "els => els.map(el => { const r=el.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2]; })"
    )


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


def _action_keys(page: Page) -> list[str]:
    return page.locator("#actionButtons button:visible").evaluate_all("els => els.map(el => el.dataset.actionKey)")


def test_mobile_actions_hide_irrelevant_controls_and_touch_viewport_edges(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        _open_table(page, online_server, 360, 800, _state(0, ["check", "fold", "bet", "all_in"]))
        assert _action_keys(page) == ["check", "fold", "aggressive", "all_in"]
        _open_table(page, online_server, 360, 800, _state(4, ["fold", "call", "raise", "all_in"]))
        assert _action_keys(page) == ["fold", "call", "aggressive"]
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
        assert active_avatar.locator(":scope > .v038-turn-timer").is_visible()
        assert page.locator(".table-frame > .v038-turn-timer").count() == 0
        assert page.locator(".v038-turn-context").count() == 0

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
        browser.close()


def test_mobile_sizes_hold_and_desktop_layout_returns_at_781(online_server: str):
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
        assert page.locator("#actionButtons").get_attribute("data-v038-reference-actions") is None
        assert page.locator("#actionButtons [data-edge]").count() == 0

        page.set_viewport_size({"width": 360, "height": 800})
        page.wait_for_function("document.body.classList.contains('poker8-v2-sixmax')")
        browser.close()
