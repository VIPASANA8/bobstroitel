# Viewer Wager Position Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Place only the main player's mobile wager stack to the upper-right of the avatar so cards and identity never cover it.

**Architecture:** Reuse the existing `wagerPointForPlayerV031` coordinate function. Add one mobile-only branch for `visualSeat === 0`; all other seats keep the current interpolation logic and nudges.

**Tech Stack:** Vanilla JavaScript, CSS-rendered poker chips, pytest source regression tests.

---

### Task 1: Lock the main-player coordinate

**Files:**
- Modify: `tests/test_v101_regressions.py`
- Modify: `static/v031-pot-cluster-mobile-fix.js`

- [ ] **Step 1: Write the failing regression test**

Add assertions that the mobile wager coordinate function has a dedicated `visualSeat === 0` branch returning a point offset to the right and upward from the viewer seat.

```python
assert 'if (visualSeat === 0)' in wager_source
assert 'x: from.x + 66' in wager_source
assert 'y: from.y - 30' in wager_source
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `pytest -q tests/test_v101_regressions.py`

Expected: FAIL because the viewer-specific coordinate branch does not exist.

- [ ] **Step 3: Implement the minimal coordinate branch**

In `wagerPointForPlayerV031`, before the other mobile-seat nudges, return the viewer point directly:

```javascript
if (mobile && visualSeat === 0) {
  return { x: from.x + 66, y: from.y - 30 };
}
```

Do not modify chip markup, sizes, other seat coordinates, or poker logic.

- [ ] **Step 4: Verify GREEN and syntax**

Run: `pytest -q tests/test_v101_regressions.py`

Expected: `5 passed`.

Run: `node --check static/v031-pot-cluster-mobile-fix.js`

Expected: exit code 0.

- [ ] **Step 5: Verify visually at mobile width**

Start or observe a live hand with a viewer wager. Confirm the stack appears to the upper-right of the viewer avatar, remains inside the felt, and does not overlap cards, avatar, identity, timer, or HUD.

- [ ] **Step 6: Commit**

```bash
git add tests/test_v101_regressions.py static/v031-pot-cluster-mobile-fix.js
git commit -m "fix: move viewer wager beside avatar"
```
