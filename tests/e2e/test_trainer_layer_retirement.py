"""Retire trainer scripts without removing the online behavior they carried."""

from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.e2e.test_mobile_edge_actions import _state


pytestmark = pytest.mark.e2e
RETIRED = {
    "v015-fixes.js", "v020-fixes.js", "v022-balance-topup.js",
    "v024-ready-phase.js", "v025-showdown-compare.js",
}


@pytest.fixture
def table_page(online_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            yield page
        finally:
            browser.close()


def _render(page, state, viewer_state="seated"):
    page.evaluate(
        "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload.state,viewerState:payload.viewerState})",
        {"state": state, "viewerState": viewer_state},
    )


def _open(page, server, width=390):
    state = _state(acting="p1", player_count=3)
    state["viewer_player_id"] = "hero"
    # Use the real online mode from boot. The nonexistent room keeps the
    # transport from overwriting the deterministic snapshots below.
    page.set_viewport_size({"width": width, "height": 877})
    page.goto(f"{server}/table?table=retirement-test", wait_until="domcontentloaded")
    page.wait_for_function("window.Poker8LegacyView && document.getElementById('v040-poker8-v2-dynamic-seats-style') && document.body.classList.contains('p8-boot-ready')")
    _render(page, state)
    return state


def test_retired_scripts_are_not_requested(table_page, online_server):
    requested = []
    table_page.on("request", lambda request: requested.append(urlparse(request.url).path.rsplit("/", 1)[-1]))
    _open(table_page, online_server)
    assert RETIRED.isdisjoint(requested), sorted(RETIRED.intersection(requested))


def test_local_start_and_topup_cannot_send_trainer_requests(table_page, online_server):
    state = _open(table_page, online_server)
    state.update(phase="waiting", acting_player=None)
    _render(table_page, state)
    requests = []
    table_page.route("**/api/game/new", lambda route: route.fulfill(json={}))
    table_page.on("request", lambda request: requests.append(urlparse(request.url).path))
    table_page.evaluate("async () => { await newHand(); document.querySelector('.viewer-seat .seat-stack')?.click(); }")
    assert "/api/game/new" not in requests
    assert not any(path.startswith("/api/profiles/") and path.endswith("/top-up") for path in requests)
    assert table_page.locator("#v022TopupBackdrop, .v024-ready-badge").count() == 0


def test_reselecting_an_auto_action_updates_it_and_explicit_cancel_clears_it(table_page, online_server):
    _open(table_page, online_server)
    selected = table_page.evaluate("""() => {
        document.getElementById('amount').value = '12';
        togglePendingAction('aggressive');
        document.getElementById('amount').value = '24';
        togglePendingAction('aggressive');
        return pendingAction;
    }""")
    assert selected["kind"] == "aggressive"
    assert selected["amount"] == 24
    table_page.evaluate("clearPendingAction()")
    assert table_page.evaluate("pendingAction") is None


def test_turn_hud_does_not_show_a_local_timer_for_an_opponent(table_page, online_server):
    state = _open(table_page, online_server)
    label = table_page.locator("#mobileTimerCard > span")
    expect(label).to_have_text("ХОД P1")
    assert table_page.locator("#mobileActionTimer").evaluate("el => el.style.display") == "none"
    state["acting_player"] = "hero"
    _render(table_page, state)
    expect(label).to_have_text("ВАШ ХОД")
    assert table_page.locator("#mobileActionTimer").evaluate("el => el.style.display") == ""
    state.update(phase="waiting", acting_player=None)
    _render(table_page, state)
    expect(label).to_have_text("ВАШ ХОД")
    assert not table_page.locator("#mobileTimerCard").evaluate("el => el.classList.contains('opponent-turn')")


def _showdown(outcome="win"):
    state = _state(player_count=2)
    state.update(
        phase="result", terminal=True, street="showdown", acting_player=None,
        viewer_player_id="hero", board=["2c", "3d", "7h", "9s", "Jc"],
        seat_order=["hero", "p1"],
    )
    state["players"]["hero"]["hole_cards"] = ["Ah", "Ad"]
    state["players"]["p1"]["hole_cards"] = ["Kh", "Kd"]
    if outcome == "loss":
        state["players"]["hero"]["hole_cards"], state["players"]["p1"]["hole_cards"] = (
            state["players"]["p1"]["hole_cards"], state["players"]["hero"]["hole_cards"],
        )
    elif outcome == "tie":
        state["board"] = ["As", "Ks", "Qs", "Js", "Ts"]
    winners = ["hero", "p1"] if outcome == "tie" else ["p1" if outcome == "loss" else "hero"]
    state.update(winners=winners, result_details=[{"winners": winners, "amount": 12}])
    return state


@pytest.mark.parametrize("width", [390, 1192])
@pytest.mark.parametrize("outcome,title", [("win", "ПОБЕДА"), ("loss", "ПОРАЖЕНИЕ"), ("tie", "ДЕЛЁЖ")])
def test_showdown_survives_the_gap_and_dismissal_until_a_new_hand(table_page, online_server, tmp_path, width, outcome, title):
    _open(table_page, online_server, width)
    result = _showdown(outcome)
    # Start with a river snapshot, so this tests the modal, not runout timing.
    _render(table_page, {**result, "terminal": False, "phase": "active"})
    _render(table_page, result)
    modal = table_page.locator("#v025ShowdownModal")
    expect(modal).to_be_visible()
    expect(modal.locator(".v025-head strong")).to_have_text(title)
    box = modal.bounding_box()
    assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
    assert table_page.locator(".v025-mini-card").count() == 4
    if outcome == "win":
        table_page.screenshot(path=tmp_path / f"showdown-{width}.png", animations="disabled")
    idle = {**result, "phase": "waiting"}
    _render(table_page, idle)
    expect(modal).to_be_visible()
    modal.locator(".v025-close").click()
    _render(table_page, idle)
    _render(table_page, idle)
    expect(modal).to_be_hidden()
    next_hand = {**result, "hand_id": "next-hand", "phase": "active", "terminal": False}
    _render(table_page, next_hand)
    expect(modal).to_be_hidden()
    _render(table_page, {**next_hand, "phase": "result", "terminal": True})
    expect(modal).to_be_visible()


@pytest.mark.parametrize("case", ["spectator", "folded", "hidden"])
def test_showdown_does_not_compare_private_or_ineligible_hands(table_page, online_server, case):
    _open(table_page, online_server)
    result = _showdown()
    viewer_state = "seated"
    if case == "spectator":
        result["viewer_player_id"] = None
        viewer_state = "spectator"
    elif case == "folded":
        result["players"]["hero"]["folded"] = True
    else:
        result["players"]["p1"]["hole_cards"] = ["??", "??"]
    _render(table_page, {**result, "terminal": False, "phase": "active"}, viewer_state)
    _render(table_page, result, viewer_state)
    expect(table_page.locator("#v025ShowdownModal")).to_be_hidden()
