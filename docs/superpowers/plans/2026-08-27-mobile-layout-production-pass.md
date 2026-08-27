# Mobile Layout Production Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the six approved mobile presentation defects while preserving poker behavior, touch sizes, HUD/card dimensions, and desktop layout.

**Architecture:** Keep the existing `v038` mobile layout and online header controls. Change only their CSS contracts: constrain the shared arc radius, assign fixed vertical lanes to central elements, make the utility wrapper own right alignment, simplify queued-state paint, and reserve opposite avatar sides for dealer and timer. Add source tests before code and extend the existing Playwright geometry test for real viewport assertions.

**Tech Stack:** Vanilla JavaScript with injected CSS, pytest, Playwright, Node syntax checks.

---

### Task 1: Lock the six regressions with failing tests

**Files:**
- Create: `tests/test_mobile_layout_production_pass.py`
- Modify: `tests/e2e/test_mobile_edge_actions.py`

- [ ] **Step 1: Add source-contract tests**

Read `static/online-table.js` and `static/v038-poker8-v2-cinematic-table.js` and
assert these behavioral tokens:

```python
assert "--p8-seat-safe-inset:50px" in table
assert "--p8-arc-radius:min(46vw,calc(50vw - var(--p8-seat-safe-inset)))" in table
assert ".mobile-header-utility{order:2;margin-left:auto!important}" in online
assert ".mobile-chat-button{margin-left:auto!important}" not in table
assert "conic-gradient(from var(--glow-angle)" not in queued_rules
assert "animation:p8HeaderGlowSpin" not in queued_rules
assert pot_chips_top < pot_top < board_top
assert "left:-9px!important;right:auto!important" in dealer_rule
```

- [ ] **Step 2: Extend the player-count E2E test with viewport containment**

For every visible `.seat.v040-dynamic-seat`, assert its rendered identity plate
and avatar stay within the viewport:

```python
for rect in hud_rects:
    assert rect["left"] >= 0
    assert rect["right"] <= width
```

- [ ] **Step 3: Add central-stack and header E2E assertions**

At 360×800 and 402×874, assert:

```python
assert chips["bottom"] <= pot["top"]
assert pot["bottom"] <= board["top"]
assert board["bottom"] <= summary["top"]
assert utility["right"] == pytest.approx(width - 8, abs=2)
```

The first assertion may allow a small visual gap tolerance if the chip stacks'
transparent bounding box is taller than their painted pixels; ordering must
still be strict by element centres.

- [ ] **Step 4: Add dealer/timer non-intersection**

Render an active dealer and assert their rectangles do not intersect:

```python
assert not _rects_intersect(dealer_rect, timer_badge_rect)
```

- [ ] **Step 5: Run focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mobile_layout_production_pass.py -q
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_mobile_edge_actions.py -q -m e2e
```

Expected: source tests fail on the old radius, header ownership, queued glow,
vertical order, and dealer placement; E2E fails on clipped extreme HUDs and the
old central/header/dealer geometry.

- [ ] **Step 6: Commit failing tests**

```powershell
git add tests/test_mobile_layout_production_pass.py tests/e2e/test_mobile_edge_actions.py
git commit -m "test: cover mobile production layout"
```

### Task 2: Implement the minimal CSS contract

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Modify: `static/online-table.js`

- [ ] **Step 1: Constrain the shared opponent arc**

Replace the mobile radius declaration with:

```css
--p8-seat-safe-inset:50px;
--p8-arc-radius:min(46vw,calc(50vw - var(--p8-seat-safe-inset)));
```

Do not alter the existing angle projections or any HUD/card dimensions.

- [ ] **Step 2: Give the utility wrapper right-edge ownership**

Replace the online mobile wrapper rule with:

```css
.poker8-online .mobile-header-utility{order:2;margin-left:auto!important}
```

Remove the obsolete child-level `.mobile-chat-button{margin-left:auto}` rule
from `v038`.

- [ ] **Step 3: Simplify the queued treatment**

Delete the `@property --glow-angle`, `p8HeaderGlowSpin`, rotating
`mode-active::before`, inset `::after`, and broad mode-active halos. Add a small
static dot on the disabled queued status:

```css
#mobileHeaderTakeSeat.mode-active::before {
  content:""; width:6px; height:6px; border-radius:50%; background:#55f3a8;
  box-shadow:0 0 7px rgba(85,243,168,.55);
}
```

Keep `Отменить` violet and interactive.

- [ ] **Step 4: Reorder and raise the central stack**

Assign non-overlapping mobile lanes with chips above pot and board, then move
the fixed summary higher while preserving its width between edge actions:

```css
.pot-chips { top:35%!important; }
.pot-total { top:41%!important; }
.board-cards { top:47%!important; }
.v038-hud-summary { bottom:calc(196px + env(safe-area-inset-bottom))!important; }
```

Tune only these offsets if the real bounding-box test requires a few pixels;
do not change sizes.

- [ ] **Step 5: Reserve the dealer's lower-left lane**

Add the mobile override:

```css
.dealer-button {
  left:-9px!important; right:auto!important; bottom:2px!important;
  width:22px!important; height:22px!important;
}
```

The timer ring and its badge remain unchanged on the right.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mobile_layout_production_pass.py -q
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_mobile_edge_actions.py -q -m e2e
```

Expected: all focused source and mobile E2E tests pass.

- [ ] **Step 7: Commit implementation**

```powershell
git add static/v038-poker8-v2-cinematic-table.js static/online-table.js
git commit -m "fix: finish mobile table geometry"
```

### Task 3: Refresh assets and run production verification

**Files:**
- Modify: `static/index.html`
- Modify: the existing loader files that reference `online-table.js` or `v038-poker8-v2-cinematic-table.js`, if their URLs are versioned there

- [ ] **Step 1: Bump the existing mobile cache key**

Change only the affected asset query strings from `mobile-layout-prod-2` to
`mobile-layout-prod-3`; do not rename files or create a new layout layer.

- [ ] **Step 2: Run JavaScript syntax checks**

Run:

```powershell
node --check static/online-table.js
node --check static/v038-poker8-v2-cinematic-table.js
```

Expected: both commands exit 0 with no output.

- [ ] **Step 3: Run the full non-E2E suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: 542 or more tests pass, with only the repository's documented skips
and deselections.

- [ ] **Step 4: Run the focused mobile E2E suite again**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_mobile_edge_actions.py -q -m e2e
```

Expected: all mobile edge-action tests pass at both target viewports.

- [ ] **Step 5: Inspect the final diff against the approved design**

Confirm the diff contains no poker-engine, action-submission, database, or
desktop-geometry changes and no size reductions for avatars, HUDs, board cards,
HERO cards, stack text, or action touch targets.

- [ ] **Step 6: Commit the cache refresh**

```powershell
git add static/index.html static/*.js
git commit -m "chore: refresh mobile layout assets"
```
