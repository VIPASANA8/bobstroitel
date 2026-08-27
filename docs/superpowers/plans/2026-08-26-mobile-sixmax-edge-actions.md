# Poker8 Mobile 6-Max Edge Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Poker8's permanent mobile action dock with a readable full-height 6-max table, a true five-opponent arc, contextual viewport-edge actions, and safe temporary bet sizing.

**Architecture:** Keep the existing `index.html` → `component-ui.js` → `v037` → `v038` rendering chain and all poker action submission paths. Put mobile presentation and transient sizing/gesture state in `v038`, use the existing `app.js` snapshot/render functions and `sendAction`, and add only the small semantic markup needed for sizing confirmation. Desktop behavior remains untouched above 780 px.

**Tech Stack:** Vanilla HTML/CSS/JavaScript, FastAPI static serving, pytest, Playwright sync API.

---

## File Map

- Modify `static/v038-poker8-v2-cinematic-table.js`: final mobile layout, circular arc, semantic player states, contextual actions, sizing mode, gesture rail, header controls, timer ring.
- Modify `static/index.html`: accessible sizing amount, confirmation, cancellation, and rail markup; cachebuster.
- Modify `static/v037-poker8-v2-reference-table.js`: bump the `v038` cachebuster only.
- Modify `static/component-ui.js`: bump the `v037` cachebuster only.
- Modify `tests/test_v101_regressions.py`: replace obsolete fixed-dock assertions with the new mobile contract while retaining unrelated regression coverage.
- Create `tests/e2e/test_mobile_edge_actions.py`: browser behavior and geometry acceptance tests at 360 × 800, 402 × 874, and 781 px.

### Task 1: Lock the full-height table, circular arc, and compact header

**Files:**
- Modify: `tests/test_v101_regressions.py`
- Create: `tests/e2e/test_mobile_edge_actions.py`
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Modify: `static/index.html`
- Modify: `static/v037-poker8-v2-reference-table.js`
- Modify: `static/component-ui.js`

- [ ] **Step 1: Replace obsolete source assertions with the new mobile layout contract**

Keep the non-layout assertions in `test_v038_cinematic_table_is_mobile_presentation_only`, remove assertions for `--p8-hud-h`, `--p8-bottom-reserve`, percentage seat coordinates, the two-by-two bottom grid, the visible HUD summary, fixed player accent hues, and the floating turn context. Add this focused test:

```python
def test_v038_uses_full_height_arc_and_viewport_edge_controls():
    root = Path(__file__).resolve().parents[1]
    source = (root / "static" / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    index = (root / "static" / "index.html").read_text(encoding="utf-8")
    component = (root / "static" / "component-ui.js").read_text(encoding="utf-8")
    loader = (root / "static" / "v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")

    assert "--p8-arc-radius:calc(46vw)" in source
    assert "--p8-arc-diagonal:calc(var(--p8-arc-radius) * .70710678)" in source
    assert '--p8-seat-angles:"180 135 90 45 0"' in source
    assert 'data-visual-seat="1"]{left:calc(50% - var(--p8-arc-radius))' in source
    assert 'data-visual-seat="2"]{left:calc(50% - var(--p8-arc-diagonal))' in source
    assert 'data-visual-seat="3"]{left:50%' in source
    assert 'data-visual-seat="4"]{left:calc(50% + var(--p8-arc-diagonal))' in source
    assert 'data-visual-seat="5"]{left:calc(50% + var(--p8-arc-radius))' in source
    assert "height:calc(100dvh - var(--p8-header-h))" in source
    assert ".action-panel" in source and "position:fixed!important" in source
    assert "background:transparent!important" in source
    assert "mobileConnectionDot" in source
    assert "mobileHelpButton" in source
    assert "ЗАНЯТЬ МЕСТО" not in source
    assert '/static/component-ui.js?v=edge-actions-1' in index
    assert '/static/v037-poker8-v2-reference-table.js?v=edge-actions-1' in component
    assert '/static/v038-poker8-v2-cinematic-table.js?v=edge-actions-1' in loader
```

- [ ] **Step 2: Run the source contract and verify RED**

Run:

```powershell
pytest tests/test_v101_regressions.py::test_v038_uses_full_height_arc_and_viewport_edge_controls -q
```

Expected: FAIL on the first missing `--p8-arc-radius` assertion.

- [ ] **Step 3: Add the shared browser fixture and failing arc geometry test**

Create `tests/e2e/test_mobile_edge_actions.py` with this initial content:

```python
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
```

- [ ] **Step 4: Run the geometry test and verify RED**

Run:

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_opponents_form_one_equal_chord_arc_at_both_mobile_sizes -q
```

Expected: FAIL because current opponent chords are not equal and the top three remain clustered.

- [ ] **Step 5: Implement the full-height stage and true circular arc**

In the mobile CSS string in `static/v038-poker8-v2-cinematic-table.js`, replace the fixed table/HUD split and percentage seat coordinates with:

```css
body.v014.poker8-v2-sixmax{
  --p8-header-h:52px;
  --p8-arc-radius:calc(46vw);
  --p8-arc-diagonal:calc(var(--p8-arc-radius) * .70710678);
  --p8-arc-top:90px;
  --p8-arc-center-y:calc(var(--p8-arc-top) + var(--p8-arc-radius));
  --p8-seat-angles:"180 135 90 45 0";
}
body.v014.poker8-v2-sixmax .app-shell{
  height:100dvh!important;min-height:100dvh!important;padding:var(--p8-header-h) 0 0!important;overflow:hidden!important;
}
body.v014.poker8-v2-sixmax .table-frame{
  height:calc(100dvh - var(--p8-header-h))!important;min-height:0!important;overflow:visible!important;
}
body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{left:50%!important;top:auto!important;bottom:18px!important;}
body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:calc(50% - var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:calc(50% - var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{left:50%!important;top:var(--p8-arc-top)!important;}
body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:calc(50% + var(--p8-arc-diagonal))!important;top:calc(var(--p8-arc-center-y) - var(--p8-arc-diagonal))!important;}
body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:calc(50% + var(--p8-arc-radius))!important;top:var(--p8-arc-center-y)!important;}
body.v014.poker8-v2-sixmax .sidebar,
body.v014.poker8-v2-sixmax .action-panel{
  position:fixed!important;inset:var(--p8-header-h) 0 0!important;width:auto!important;height:auto!important;min-height:0!important;
  padding:0!important;margin:0!important;overflow:visible!important;border:0!important;background:transparent!important;box-shadow:none!important;pointer-events:none!important;
}
body.v014.poker8-v2-sixmax .action-panel :is(button,input){pointer-events:auto!important;}
```

Remove the `@media (max-width:370px)` avatar scale-down. Set opponent avatar/HUD/name/stack sizes to `44px`, `90px`, `12px`, and `16px`; board cards to `46px × 64px`; HERO cards to `50px × 70px`; HERO avatar/name/stack to `48px`, `13px`, and `18px`.

Keep the center ordering explicit:

```css
body.v014.poker8-v2-sixmax .pot-total{top:41%!important;}
body.v014.poker8-v2-sixmax .pot-chips{top:45%!important;}
body.v014.poker8-v2-sixmax .board-cards{top:49%!important;}
```

- [ ] **Step 6: Add compact header controls and cachebusters**

In `v038`, add this function and call it from `syncFinalReference()`:

```javascript
function ensureMobileHeaderControls() {
  const header = document.getElementById("mobileGameHeader");
  if (!header) return;
  let dot = document.getElementById("mobileConnectionDot");
  if (!dot) {
    dot = document.createElement("span");
    dot.id = "mobileConnectionDot";
    dot.setAttribute("role", "status");
    dot.setAttribute("aria-label", "Подключение");
    document.getElementById("mobileMenuButton")?.after(dot);
  }
  if (!document.getElementById("mobileHelpButton")) {
    const help = document.createElement("button");
    help.id = "mobileHelpButton";
    help.type = "button";
    help.setAttribute("aria-label", "Помощь");
    help.textContent = "?";
    header.appendChild(help);
  }
}
```

Style menu, chat, and help with 48 px touch boxes. Hide `#connectionStatus` visually on mobile but keep it as the source of status text. Change cachebusters to `edge-actions-1` along the three-file loader chain.

- [ ] **Step 7: Run RED-to-GREEN checks**

Run:

```powershell
pytest tests/test_v101_regressions.py::test_v038_uses_full_height_arc_and_viewport_edge_controls -q
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_opponents_form_one_equal_chord_arc_at_both_mobile_sizes -q
```

Expected: both PASS.

- [ ] **Step 8: Commit Task 1**

```powershell
git add static/index.html static/component-ui.js static/v037-poker8-v2-reference-table.js static/v038-poker8-v2-cinematic-table.js tests/test_v101_regressions.py tests/e2e/test_mobile_edge_actions.py
git commit -m "feat: rebuild the mobile six-max table stage"
```

### Task 2: Render only contextual actions at viewport edges

**Files:**
- Modify: `tests/e2e/test_mobile_edge_actions.py`
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] **Step 1: Add failing browser tests for both action contexts**

Append:

```python
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
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_mobile_actions_hide_irrelevant_controls_and_touch_viewport_edges -q
```

Expected: FAIL because the current renderer always creates four bottom-grid buttons.

- [ ] **Step 3: Extract and use one contextual definition function**

Add before `configureReferenceActions()`:

```javascript
function mobileActionDefinitions({ localTurn, legal, toCall, amount, allInTotal, aggressiveLabel }) {
  const available = action => !localTurn || legal.includes(action);
  if (toCall > 0) {
    return [
      { key:"fold", label:"FOLD", amount:"", cls:"fold", edge:"left", slot:"top", enabled:available("fold") },
      { key:"call", label:"CALL", amount:stripHudUnit(formatBB(toCall)), cls:"call", edge:"right", slot:"top", enabled:available("call") },
      { key:"aggressive", label:aggressiveLabel, amount:stripHudUnit(formatBB(amount)), cls:"raise", edge:"right", slot:"bottom", enabled:available("raise") },
    ].filter(def => def.enabled);
  }
  return [
    { key:"check", label:"CHECK", amount:"", cls:"check", edge:"left", slot:"top", enabled:available("check") },
    { key:"fold", label:"FOLD", amount:"", cls:"fold", edge:"left", slot:"bottom", enabled:available("fold") },
    { key:"aggressive", label:"BET", amount:stripHudUnit(formatBB(amount)), cls:"raise", edge:"right", slot:"top", enabled:available("bet") },
    { key:"all_in", label:"ALL IN", amount:stripHudUnit(formatBB(allInTotal)), cls:"all-in", edge:"right", slot:"bottom", enabled:available("all_in") },
  ].filter(def => def.enabled);
}
```

Make `configureReferenceActions()` rebuild only when the action-key sequence changes, set `data-edge` and `data-slot`, and remove the disabled styling path. Preserve the existing pre-action click path for `!localTurn`.

- [ ] **Step 4: Position the action grid as a non-layout owner**

Use:

```css
body.v014.poker8-v2-sixmax .action-grid{display:contents!important;}
body.v014.poker8-v2-sixmax .action-grid .action-slot{
  position:fixed!important;z-index:90;width:88px!important;min-height:58px!important;height:auto!important;padding:8px 7px!important;
}
body.v014.poker8-v2-sixmax .action-slot[data-edge="left"]{left:0!important;border-left:0!important;border-radius:0 16px 16px 0!important;}
body.v014.poker8-v2-sixmax .action-slot[data-edge="right"]{right:0!important;border-right:0!important;border-radius:16px 0 0 16px!important;}
body.v014.poker8-v2-sixmax .action-slot[data-slot="top"]{bottom:calc(152px + env(safe-area-inset-bottom))!important;}
body.v014.poker8-v2-sixmax .action-slot[data-slot="bottom"]{bottom:calc(84px + env(safe-area-inset-bottom))!important;}
```

- [ ] **Step 5: Run the contextual action test and regression file**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_mobile_actions_hide_irrelevant_controls_and_touch_viewport_edges -q
pytest tests/test_v101_regressions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```powershell
git add static/v038-poker8-v2-cinematic-table.js tests/e2e/test_mobile_edge_actions.py tests/test_v101_regressions.py
git commit -m "feat: move contextual poker actions to screen edges"
```

### Task 3: Add temporary sizing mode with explicit confirmation

**Files:**
- Modify: `static/index.html`
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Modify: `tests/e2e/test_mobile_edge_actions.py`

- [ ] **Step 1: Add a failing safe-confirmation browser test**

Append:

```python
def test_bet_and_all_in_open_sizing_without_immediate_submission(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        submissions: list[str] = []
        page.route("**/api/game/**/action", lambda route: (submissions.append(route.request.post_data or ""), route.fulfill(status=200, json={})))
        _open_table(page, online_server, 360, 800, _state(0, ["check", "fold", "bet", "all_in"]))

        page.locator('[data-action-key="aggressive"]').click()
        assert page.locator("#sizingWrap").get_attribute("aria-hidden") == "false"
        assert page.locator("#mobileSizingConfirm").is_visible()
        assert submissions == []
        page.locator("#mobileSizingConfirm").click()
        assert len(submissions) == 1

        page.evaluate(
            "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload,viewerState:'seated'})",
            _state(0, ["check", "fold", "bet", "all_in"]),
        )
        page.locator('[data-action-key="all_in"]').click()
        assert page.locator("#sizingWrap").get_attribute("aria-hidden") == "false"
        assert page.locator("#mobileSizingAmount").inner_text().strip()
        assert len(submissions) == 1
        page.locator("#mobileSizingConfirm").click()
        assert len(submissions) == 2
        browser.close()
```

- [ ] **Step 2: Run and verify RED**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_bet_and_all_in_open_sizing_without_immediate_submission -q
```

Expected: FAIL because aggressive action currently submits immediately or uses the old timed double-tap confirmation.

- [ ] **Step 3: Add accessible sizing controls to the existing wrapper**

Inside `#sizingWrap`, before `.quick-sizes`, add:

```html
<div class="mobile-sizing-head">
  <output id="mobileSizingAmount" for="amount amountSlider" aria-live="polite">0.00 BB</output>
  <button id="mobileSizingCancel" type="button" aria-label="Отменить выбор ставки">×</button>
</div>
```

After `.bet-slider-row`, add:

```html
<button id="mobileSizingConfirm" type="button">ПОДТВЕРДИТЬ СТАВКУ</button>
<div id="mobileBetRail" aria-hidden="true"><output id="mobileBetRailAmount">0.00 BB</output></div>
```

Set `aria-hidden="true"` on `#sizingWrap` in the static markup.

- [ ] **Step 4: Replace timed all-in arming with explicit sizing state**

Remove `allInArmed*`, `ALL_IN_CONFIRM_MS`, `confirmAllIn()`, and their timer CSS. Add:

```javascript
let sizingMode = null;

function closeSizingMode() {
  sizingMode = null;
  document.body.classList.remove("v038-sizing-open");
  document.getElementById("sizingWrap")?.setAttribute("aria-hidden", "true");
  queueSync();
}

function openSizingMode(action, amount = null) {
  const bounds = amountBounds();
  const value = Math.min(bounds.max, Math.max(bounds.min, amount ?? bounds.value));
  sizingMode = { action, value };
  syncAmountControls(value);
  document.body.classList.add("v038-sizing-open");
  document.getElementById("sizingWrap")?.setAttribute("aria-hidden", "false");
  syncSizingModeText();
  queueSync();
}

function syncSizingModeText() {
  const amount = Number(document.getElementById("amount")?.value || 0);
  if (sizingMode) sizingMode.value = amount;
  setText(document.getElementById("mobileSizingAmount"), `${stripHudUnit(formatBB(amount))} BB`);
  setText(document.getElementById("mobileSizingConfirm"), sizingMode?.action === "raise" ? "ПОДТВЕРДИТЬ РЕЙЗ" : "ПОДТВЕРДИТЬ СТАВКУ");
}

function confirmSizingMode() {
  if (!sizingMode || !game || game.terminal) return closeSizingMode();
  const { action, value } = sizingMode;
  const localTurn = isLocalHumanTurn();
  closeSizingMode();
  if (!localTurn) {
    togglePendingAction(action === "all_in" ? "all_in" : "aggressive");
    renderMobileSelectedCard();
    return;
  }
  clearPendingAction(false);
  if (action === "all_in") return sendAction("all_in", 0);
  return sendAction(action, value);
}
```

Aggressive buttons call `openSizingMode(legal.includes("raise") ? "raise" : "bet", amount)`. All-in calls `openSizingMode("all_in", amountBounds().max)`. Bind confirm and cancel once in `start()`. Close sizing mode when the hand becomes terminal, the viewer is no longer alive, the aggressive action becomes illegal, or mobile mode tears down.

- [ ] **Step 5: Show sizing only while open and preserve five readable presets**

```css
body.v014.poker8-v2-sixmax .sizing-wrap{
  display:none!important;position:fixed!important;z-index:96;left:50%!important;bottom:calc(150px + env(safe-area-inset-bottom))!important;
  width:min(344px,calc(100vw - 16px))!important;transform:translateX(-50%)!important;padding:10px!important;
  border:1px solid rgba(77,255,188,.42)!important;border-radius:18px!important;background:rgba(2,10,7,.96)!important;box-shadow:0 0 28px rgba(33,242,164,.22)!important;
}
body.v014.poker8-v2-sixmax.v038-sizing-open .sizing-wrap{display:block!important;}
body.v014.poker8-v2-sixmax.v038-sizing-open .action-grid .action-slot{visibility:hidden!important;}
body.v014.poker8-v2-sixmax .quick-sizes{display:grid!important;grid-template-columns:repeat(5,minmax(48px,1fr))!important;gap:5px!important;}
body.v014.poker8-v2-sixmax .quick-sizes button{min-height:48px!important;font-size:10px!important;}
body.v014.poker8-v2-sixmax #mobileSizingConfirm{width:100%!important;min-height:50px!important;}
```

- [ ] **Step 6: Run and verify GREEN**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_bet_and_all_in_open_sizing_without_immediate_submission -q
pytest tests/test_v101_regressions.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add static/index.html static/v038-poker8-v2-cinematic-table.js tests/e2e/test_mobile_edge_actions.py tests/test_v101_regressions.py
git commit -m "feat: add safe temporary mobile bet sizing"
```

### Task 4: Add the vertical bet gesture without auto-submit

**Files:**
- Modify: `tests/e2e/test_mobile_edge_actions.py`
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] **Step 1: Add a failing gesture selection test**

Append:

```python
def test_vertical_bet_gesture_selects_amount_but_never_submits(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 360, "height": 800}, device_scale_factor=1)
        submissions: list[str] = []
        page.route("**/api/game/**/action", lambda route: (submissions.append(route.request.post_data or ""), route.fulfill(status=200, json={})))
        _open_table(page, online_server, 360, 800, _state(0, ["check", "fold", "bet", "all_in"]))
        bet = page.locator('[data-action-key="aggressive"]')
        box = bet.bounding_box()
        assert box
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(354, 170, steps=8)
        page.mouse.up()
        assert page.locator("#mobileBetRail").get_attribute("aria-hidden") == "true"
        assert page.locator("#mobileSizingConfirm").is_visible()
        assert float(page.locator("#amount").input_value()) > 0
        assert submissions == []
        browser.close()
```

- [ ] **Step 2: Run and verify RED**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_vertical_bet_gesture_selects_amount_but_never_submits -q
```

Expected: FAIL because no pointer gesture or rail exists.

- [ ] **Step 3: Add legal deduplicated gesture steps**

```javascript
function verticalBetSteps() {
  const bounds = amountBounds();
  const candidates = [
    bounds.min,
    2,
    4,
    presetTarget(.5),
    presetTarget(2 / 3),
    presetTarget(1),
    bounds.max,
  ];
  return [...new Set(candidates.map(value => Math.min(bounds.max, Math.max(bounds.min, Number(value))).toFixed(2)))]
    .map(Number)
    .sort((a, b) => a - b);
}

function gestureStepAt(clientY) {
  const steps = verticalBetSteps();
  const progress = Math.min(1, Math.max(0, (window.innerHeight - clientY) / Math.max(240, window.innerHeight * .65)));
  return steps[Math.min(steps.length - 1, Math.round(progress * (steps.length - 1)))];
}
```

- [ ] **Step 4: Bind pointer capture to aggressive actions**

Use delegated `pointerdown`, `pointermove`, `pointerup`, and `pointercancel` handlers on `#actionButtons`. A downward/tap movement under 8 px opens normal sizing. Movement of at least 8 px opens the rail, updates `#amount`, `#mobileBetRailAmount`, and the large amount output. `pointerup` hides the rail and leaves sizing open. `pointercancel` restores the starting amount and leaves sizing open. Do not call `sendAction` from any pointer handler.

The state object is:

```javascript
let betGesture = null;

function endBetGesture(cancelled) {
  if (!betGesture) return;
  if (cancelled) syncAmountControls(betGesture.startAmount);
  betGesture = null;
  document.getElementById("mobileBetRail")?.setAttribute("aria-hidden", "true");
  syncSizingModeText();
}
```

- [ ] **Step 5: Style the right-edge rail and amount bubble**

```css
body.v014.poker8-v2-sixmax #mobileBetRail{
  position:fixed;z-index:100;right:0;top:18%;bottom:26%;width:64px;border:1px solid rgba(74,255,178,.52);border-right:0;border-radius:18px 0 0 18px;background:linear-gradient(180deg,rgba(255,163,62,.2),rgba(45,255,166,.12));pointer-events:none;
}
body.v014.poker8-v2-sixmax #mobileBetRail[aria-hidden="true"]{display:none;}
body.v014.poker8-v2-sixmax #mobileBetRailAmount{position:absolute;right:68px;top:12px;min-width:112px;padding:10px;border-radius:14px;background:#03110d;color:#fff;font-size:24px;font-weight:950;text-align:center;}
```

- [ ] **Step 6: Run and verify GREEN**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_vertical_bet_gesture_selects_amount_but_never_submits -q
pytest -m e2e tests/e2e/test_mobile_edge_actions.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```powershell
git add static/v038-poker8-v2-cinematic-table.js tests/e2e/test_mobile_edge_actions.py
git commit -m "feat: add safe vertical mobile bet gesture"
```

### Task 5: Attach semantic states and the timer to player HUDs

**Files:**
- Modify: `tests/e2e/test_mobile_edge_actions.py`
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] **Step 1: Add failing state and timer tests**

Append:

```python
def test_timer_fold_and_connection_states_stay_attached_to_huds(online_server: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 402, "height": 874}, device_scale_factor=1)
        state = _state(0, ["check", "fold", "bet", "all_in"], acting="p4")
        state["players"]["p1"]["folded"] = True
        _open_table(page, online_server, 402, 874, state)
        active = page.locator('.seat[data-seat="4"]')
        folded = page.locator('.seat[data-seat="1"]')
        assert active.locator(".v038-turn-ring").count() == 1
        assert active.locator(".v038-turn-ring").is_visible()
        assert folded.locator(".player-cards").evaluate("el => getComputedStyle(el).opacity") == "0"
        assert folded.locator(".seat-stack").is_visible()
        assert page.locator(".v038-turn-timer").count() == 0
        assert page.locator("#connectionStatus").is_hidden()
        assert page.locator("#mobileConnectionDot").is_visible()
        browser.close()
```

- [ ] **Step 2: Run and verify RED**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_timer_fold_and_connection_states_stay_attached_to_huds -q
```

Expected: FAIL because the current timer is attached to `.table-frame` and the connection dot is not synchronized.

- [ ] **Step 3: Replace the floating timer with one active-seat ring**

Rewrite `syncTableTurnHud()` so it removes stale `.v038-turn-ring` elements, finds the physical seat for `game.acting_player`, and appends this markup to that seat's `.avatar-wrap`:

```javascript
ring = document.createElement("div");
ring.className = "v038-turn-ring";
ring.innerHTML = '<b>30</b><span class="sr-only">секунд на ход</span>';
```

Retain the current 30-second token/reset logic and set `--timer-progress` on the ring. Use green normally and add `.critical` at ten seconds or below. Remove `.v038-turn-context` entirely.

- [ ] **Step 4: Synchronize semantic connection and player states**

Add:

```javascript
function syncConnectionDot() {
  const text = document.getElementById("connectionStatus")?.textContent?.trim().toLowerCase() || "";
  const dot = document.getElementById("mobileConnectionDot");
  const state = text === "connected" ? "connected" : text.includes("connecting") || text.includes("устанавливается") ? "connecting" : "disconnected";
  if (dot) {
    dot.dataset.state = state;
    dot.setAttribute("aria-label", state === "connected" ? "Подключено" : state === "connecting" ? "Подключение" : "Нет соединения");
  }
}
```

Observe `#connectionStatus` text once in `start()`. Replace per-seat accent hues with neutral borders; keep cyan only for visual seat zero, bright green for `.v032-active-turn`, orange for `.all-in`, muted opacity for `.v032-folded`, and critical red only on the timer ring. Fold opacity is `.5`, and folded `.player-cards` opacity is `0` while identity and stack remain `1`.

- [ ] **Step 5: Run and verify GREEN**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_timer_fold_and_connection_states_stay_attached_to_huds -q
pytest tests/test_v101_regressions.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```powershell
git add static/v038-poker8-v2-cinematic-table.js tests/e2e/test_mobile_edge_actions.py tests/test_v101_regressions.py
git commit -m "feat: attach mobile table states to player huds"
```

### Task 6: Verify responsive behavior and the complete regression surface

**Files:**
- Modify: `tests/e2e/test_mobile_edge_actions.py`
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] **Step 1: Add the desktop restoration and readable-size acceptance test**

Append:

```python
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
        assert not page.locator("body").evaluate("el => el.classList.contains('poker8-v2-sixmax')")
        assert page.locator(".action-panel").evaluate("el => getComputedStyle(el).position") != "fixed"
        browser.close()
```

- [ ] **Step 2: Run and verify RED or confirm existing implementation**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py::test_mobile_sizes_hold_and_desktop_layout_returns_at_781 -q
```

Expected: FAIL because the current 370 px override shrinks cards and `poker8-v2-sixmax` remains on the body after resizing to 781 px.

- [ ] **Step 3: Restore desktop state explicitly without shrinking mobile content**

Delete the legacy `@media (max-width:370px)` scale rules. In `teardownFinalReference()`, add the exact cleanup below after removing transient v038 body classes:

```javascript
document.body.classList.remove("poker8-v2-sixmax", "v038-sizing-open");
document.getElementById("sizingWrap")?.setAttribute("aria-hidden", "true");
document.getElementById("mobileBetRail")?.setAttribute("aria-hidden", "true");
```

The existing v032 resize listener reapplies `poker8-v2-sixmax` when the viewport returns below 781 px. Do not add a smaller mobile breakpoint or any whole-interface scale.

- [ ] **Step 4: Run focused browser acceptance**

```powershell
pytest -m e2e tests/e2e/test_mobile_edge_actions.py -q
pytest -m e2e tests/e2e/test_mobile_online_flow.py -q
```

Expected: PASS.

- [ ] **Step 5: Run source and online UI regressions**

```powershell
pytest tests/test_v101_regressions.py tests/online/test_table_ui_states.py tests/online/test_table_transport_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Run the default full suite**

```powershell
pytest -q
```

Expected: all non-PostgreSQL, non-E2E tests PASS.

- [ ] **Step 7: Inspect the final diff and whitespace**

```powershell
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only the planned source/test files plus the user's pre-existing `data/poker_trainer.sqlite3` modification appear.

- [ ] **Step 8: Commit the acceptance pass**

```powershell
git add static/v038-poker8-v2-cinematic-table.js tests/e2e/test_mobile_edge_actions.py
git commit -m "test: verify mobile edge-action table layout"
```
