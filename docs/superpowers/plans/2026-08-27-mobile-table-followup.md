# Mobile Table Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix mobile avatar timers, summary placement, 2–5 player geometry, and the duplicate help button without changing desktop or poker behavior.

**Architecture:** Keep the current `v038` mobile layer and `v040` player-count classes. Add count-specific CSS coordinates instead of another layout engine, reparent the ready countdown to HERO while retaining a spectator fallback, and make both avatar timers use the same hollow-ring primitive. Extend the existing Playwright layout test and source-contract test before changing production code.

**Tech Stack:** Vanilla JavaScript, injected CSS, pytest, Playwright, Node syntax checks.

---

### Task 1: Lock the four regressions with failing tests

**Files:**
- Modify: `tests/e2e/test_mobile_edge_actions.py`
- Modify: `tests/test_v101_regressions.py`

- [ ] **Step 1: Add a state helper for lower player counts**

Extend `_state` with `player_count: int = 6` and retain HERO plus the first
`player_count - 1` opponents:

```python
def _state(..., player_count: int = 6) -> dict:
    ...
    players = dict(list(players.items())[:player_count])
```

- [ ] **Step 2: Add the failing geometry/overlap E2E test**

For 2–6 players at 360×800 and 402×874, render the state and assert:

```python
assert len(opponents) == player_count - 1
assert hero_center_x == pytest.approx(width / 2, abs=1)
assert opponents == pytest.approx(list(reversed(opponents)), abs=1)
assert not rects_intersect(summary, seat_rect)
assert not rects_intersect(summary, action_rect)
```

Use expected monotonic/symmetric y coordinates rather than comparing hard-coded
pixels, so the test checks the arc rather than one device.

- [ ] **Step 3: Add the failing avatar-ring E2E assertions**

In `test_timer_and_semantic_states_are_attached_to_player_huds`, verify the turn
timer has a transparent centre and an external badge. Dispatch
`poker8:ready-countdown`, render a waiting state, and verify the ready timer is a
direct child of HERO's `.avatar-wrap`, not `.felt`:

```python
assert active_avatar.locator(":scope > .v038-turn-timer").count() == 1
assert active_avatar.locator(":scope > .v038-turn-timer b").evaluate(
    "el => el.getBoundingClientRect().left >= el.parentElement.getBoundingClientRect().right - 8"
)
assert page.locator('.seat[data-visual-seat="0"] .avatar-wrap > .v038-ready-countdown').count() == 1
```

- [ ] **Step 4: Add the failing duplicate-help source contract**

Replace the existing `mobileHelpButton` expectation with:

```python
assert "mobileHelpButton" not in source
assert 'hint.textContent = "?"' in reference_source
```

Also assert count-specific mobile selectors exist for `p8-player-count-2` through
`p8-player-count-5`.

- [ ] **Step 5: Run the focused tests and verify RED**

Run:

```powershell
D:\project\poker\.venv\Scripts\python.exe -m pytest tests/test_v101_regressions.py tests/e2e/test_mobile_edge_actions.py -q -m "e2e or not e2e"
```

Expected: failures identifying the duplicate `mobileHelpButton`, six-player-only
coordinates, felt-centred ready timer, filled timer centre, and summary overlap.

- [ ] **Step 6: Commit the failing tests**

```powershell
git add tests/test_v101_regressions.py tests/e2e/test_mobile_edge_actions.py
git commit -m "test: cover mobile table follow-up states"
```

### Task 2: Remove the duplicate control and add count-specific arcs

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] **Step 1: Remove the inert help control**

Delete `#mobileHelpButton` from the shared header-size selector, delete its style
rule, and delete the block in `ensureMobileHeaderControls` that creates it. Keep
the connection dot and the `v037` hint button unchanged.

- [ ] **Step 2: Add the missing arc projection variables**

Inside the mobile body variables add:

```css
--p8-arc-half:calc(var(--p8-arc-radius) * .5);
--p8-arc-wide:calc(var(--p8-arc-radius) * .8660254);
```

- [ ] **Step 3: Add player-count-specific coordinate rules**

Keep HERO fixed at bottom centre. Override opponent visual seats using the
existing body count classes:

```css
body...p8-player-count-2 .seat[data-visual-seat="1"] { x:50%; y:arc-top; }
body...p8-player-count-3 .seat[data-visual-seat="1"] { x:50%-diagonal; y:center-diagonal; }
body...p8-player-count-3 .seat[data-visual-seat="2"] { x:50%+diagonal; y:center-diagonal; }
body...p8-player-count-4 .seat[data-visual-seat="1"] { x:50%-wide; y:center-half; }
body...p8-player-count-4 .seat[data-visual-seat="2"] { x:50%; y:arc-top; }
body...p8-player-count-4 .seat[data-visual-seat="3"] { x:50%+wide; y:center-half; }
body...p8-player-count-5 .seat[data-visual-seat="1"] { x:50%-radius; y:center; }
body...p8-player-count-5 .seat[data-visual-seat="2"] { x:50%-half; y:center-wide; }
body...p8-player-count-5 .seat[data-visual-seat="3"] { x:50%+half; y:center-wide; }
body...p8-player-count-5 .seat[data-visual-seat="4"] { x:50%+radius; y:center; }
```

Each real rule sets `--v040-seat-x`, `--v040-seat-y`, `left`, and `top` with
`!important`, matching the existing v038/v040 contract.

- [ ] **Step 4: Run geometry and source tests and verify GREEN for this task**

Run:

```powershell
D:\project\poker\.venv\Scripts\python.exe -m pytest tests/test_v101_regressions.py tests/e2e/test_mobile_edge_actions.py::test_player_count_arcs_and_summary_do_not_overlap -q
```

Expected: help/geometry assertions pass; timer/summary-specific assertions may
remain red until Task 3.

- [ ] **Step 5: Commit**

```powershell
git add static/v038-poker8-v2-cinematic-table.js
git commit -m "fix: adapt mobile arc to player count"
```

### Task 3: Make timers hollow and move the summary rail

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] **Step 1: Replace the filled avatar timer with a pseudo-element ring**

The timer container itself has no background. Its `::before` draws only the outer
ring using a mask, leaving all avatar pixels visible:

```css
.avatar-wrap > :is(.v038-turn-timer,.v038-ready-countdown)::before {
  content:"";
  position:absolute;
  inset:0;
  border-radius:50%;
  background:conic-gradient(#57ffd0 var(--timer-progress,100%),rgba(87,255,208,.10) 0);
  -webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 4px),#000 0);
  mask:radial-gradient(farthest-side,transparent calc(100% - 4px),#000 0);
}
```

Share the external badge rule between both timer classes. The ready countdown sets
its `--timer-progress` from its deadline on each tick.

- [ ] **Step 2: Reparent the ready countdown to HERO**

Update `ensureReadyCountdown` to choose:

```javascript
const hero = document.querySelector('.seat[data-visual-seat="0"] .avatar-wrap');
const host = hero || document.querySelector(".felt");
if (countdown.parentElement !== host) host.appendChild(countdown);
countdown.classList.toggle("v038-avatar-countdown", Boolean(hero));
```

Call `ensureReadyCountdown()` inside the tick so a countdown created before seat
rendering moves to HERO as soon as the avatar exists. Keep the table-centred base
style only when the fallback host is `.felt`.

- [ ] **Step 3: Move the mobile summary into the centre corridor**

Override the summary inside the mobile media query:

```css
.v038-hud-summary {
  position:fixed!important;
  z-index:82;
  left:96px!important;
  right:96px!important;
  top:auto!important;
  bottom:calc(148px + env(safe-area-inset-bottom))!important;
  min-height:38px;
  pointer-events:none;
}
```

Use a compact dark background/border and keep the existing three equal columns and
tabular numbers. The 8 px gap between the 88 px edge buttons and the rail prevents
intersection.

- [ ] **Step 4: Run all focused mobile tests and verify GREEN**

Run:

```powershell
D:\project\poker\.venv\Scripts\python.exe -m pytest tests/test_v101_regressions.py tests/test_ready_countdown_visible_while_waiting.py tests/e2e/test_mobile_edge_actions.py -q -m "e2e or not e2e"
node --check static/v038-poker8-v2-cinematic-table.js
```

Expected: all selected tests pass and Node reports no syntax error.

- [ ] **Step 5: Commit**

```powershell
git add static/v038-poker8-v2-cinematic-table.js
git commit -m "fix: keep mobile table chrome clear"
```

### Task 4: Cache bust, regression verification, and delivery

**Files:**
- Modify: `static/index.html`
- Modify: `static/component-ui.js`
- Modify: `static/v037-poker8-v2-reference-table.js`
- Test: full pytest and mobile E2E suites

- [ ] **Step 1: Advance the mobile bundle cache key**

Change `mobile-edge-prod-1` to `mobile-layout-prod-2` in the three loader files so
production clients cannot reuse the old v038 bundle.

- [ ] **Step 2: Update source-contract cache expectations**

Change the three expected loader URLs in `tests/test_v101_regressions.py` to
`mobile-layout-prod-2`.

- [ ] **Step 3: Run final verification**

```powershell
D:\project\poker\.venv\Scripts\python.exe -m pytest -q
D:\project\poker\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_mobile_edge_actions.py tests/e2e/test_mobile_online_flow.py -q
node --check static/v038-poker8-v2-cinematic-table.js
git diff --check
```

Expected: unit/integration suite, all selected E2E tests, Node syntax, and whitespace
check pass with zero failures.

- [ ] **Step 4: Commit the release cache key**

```powershell
git add static/index.html static/component-ui.js static/v037-poker8-v2-reference-table.js tests/test_v101_regressions.py
git commit -m "chore: refresh mobile table assets"
```

- [ ] **Step 5: Push, open a PR, merge, deploy, and verify production**

Push `codex/mobile-layout-followup`, open a PR against `main`, merge only when it is
clean, then follow `docs/runbooks/prod-launch-checklist.md`: create a PostgreSQL
backup, `git pull --ff-only origin main`, rebuild with the existing Compose+Caddy
files, and verify root HTTP 200, `/health/ready`, healthy app container, migration
head, and the `mobile-layout-prod-2` marker from public HTTPS.
