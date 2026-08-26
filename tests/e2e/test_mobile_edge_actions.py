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
