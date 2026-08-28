# Responsive HUD Summary Spacing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the mobile `УРАВНЯТЬ / СТАВКА` strip exactly centered between the rendered pot and community-card row at every table height in seated and spectator layouts.

**Architecture:** Reuse the existing `syncFinalReference` and window-resize path. `ensureHudSummary` will measure the three rendered rectangles and write one CSS custom property for the strip's top coordinate; the existing `41%` remains the fallback whenever the interval is not measurable.

**Tech Stack:** Vanilla JavaScript, CSS custom properties, Playwright, pytest.

---

### Task 1: Add the responsive browser regression

**Files:**
- Modify: `tests/e2e/test_mobile_edge_actions.py`

- [ ] **Step 1: Let the table helper select seated or spectator mode**

Add `viewer_state: str = "seated"` to `_open_table` and pass `{state, viewerState}` into the existing `renderSnapshot` evaluation instead of hard-coding `viewerState:'seated'`.

```python
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
    page.wait_for_function("window.Poker8LegacyView && document.getElementById('v038-poker8-v2-cinematic-table-style')")
    page.evaluate(
        "payload => window.Poker8LegacyView.renderSnapshot({table:{id:'t',name:'Test'},state:payload.state,viewerState:payload.viewerState})",
        {"state": state or _state(), "viewerState": viewer_state},
    )
    page.wait_for_function("document.body.classList.contains('poker8-v2-sixmax')")
    page.wait_for_timeout(100)
```

- [ ] **Step 2: Add the failing spacing test**

```python
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
```

- [ ] **Step 3: Run the test and verify RED**

Run: `uv run --with-requirements requirements.txt pytest -q -m e2e tests/e2e/test_mobile_edge_actions.py::test_call_bet_summary_stays_centered_when_the_table_resizes`

Expected: FAIL at 640px because the current upper gap is about `-2.8px`, while the lower gap is about `10.3px`.

### Task 2: Center the strip from live geometry

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Modify: `static/index.html`
- Modify: `static/component-ui.js`
- Modify: `static/v037-poker8-v2-reference-table.js`
- Modify: `tests/test_v101_regressions.py`

- [ ] **Step 1: Make the CSS top coordinate overridable**

Change the felt rule to:

```css
left:50%!important;right:auto!important;top:var(--v038-summary-top,41%)!important;
```

- [ ] **Step 2: Add the minimal live-geometry calculation**

Add this function beside `ensureHudSummary`:

```javascript
function positionHudSummary(summary, host) {
  const pot = document.querySelector(".pot-total");
  const board = document.getElementById("board");
  if (!summary.classList.contains("on-felt") || !pot || !board) {
    summary.style.removeProperty("--v038-summary-top");
    return;
  }
  const hostRect = host.getBoundingClientRect();
  const potRect = pot.getBoundingClientRect();
  const boardRect = board.getBoundingClientRect();
  const summaryRect = summary.getBoundingClientRect();
  if (!summaryRect.height || boardRect.top <= potRect.bottom) {
    summary.style.removeProperty("--v038-summary-top");
    return;
  }
  const top = (potRect.bottom + boardRect.top - summaryRect.height) / 2 - hostRect.top;
  summary.style.setProperty("--v038-summary-top", `${top}px`);
}
```

Call `positionHudSummary(summary, host)` after applying the `on-felt` class. The existing resize listener already queues this sync, so no observer or second event system is added.

- [ ] **Step 3: Bump only the affected cache chain**

Use `summary-spacing-1` for `component-ui.js`, `v037-poker8-v2-reference-table.js`, and `v038-poker8-v2-cinematic-table.js`. Leave unrelated script keys unchanged. Update `test_v038_uses_full_height_arc_and_viewport_edge_controls` to assert the new chain and the `--v038-summary-top` fallback.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
uv run --with-requirements requirements.txt pytest -q tests/test_v101_regressions.py::test_v038_uses_full_height_arc_and_viewport_edge_controls
uv run --with-requirements requirements.txt pytest -q -m e2e tests/e2e/test_mobile_edge_actions.py::test_call_bet_summary_stays_centered_when_the_table_resizes tests/e2e/test_mobile_edge_actions.py::test_mobile_header_and_center_stack_use_their_reserved_lanes
```

Expected: both commands PASS; all measured upper/lower gaps differ by at most one pixel.

### Task 3: Verify and release

**Files:**
- No additional source files.

- [ ] **Step 1: Run syntax, diff, and regular-suite checks**

Run `node --check` for every changed JavaScript file, `git diff --check`, and `uv run --with-requirements requirements.txt pytest -q -m "not e2e"`.

Expected: JavaScript parses, diff check exits zero, and the regular suite has zero failures.

- [ ] **Step 2: Commit and fast-forward main**

Commit with `fix: center mobile call bet summary`, fetch `origin/main`, verify the branch is based on it, and push `HEAD:main`.

- [ ] **Step 3: Deploy and verify production**

On `/root/poker8`, preserve unrelated files, pull with `--ff-only`, and rebuild with `docker compose -f compose.server.yaml -f deploy/compose.caddy.yaml up -d --build`. Verify `/health/ready`, the public cache chain, `--v038-summary-top`, the deployed commit, and the healthy app container.
