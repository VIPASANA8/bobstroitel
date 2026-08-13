# Compact Mobile HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the redundant mobile amount stepper with a compact, readable HUD matching the approved A mockup.

**Architecture:** Extend the existing mobile-only v038 presentation pass. CSS owns layout and gradient rendering; the existing amount input remains authoritative but hidden, while one small debounce maps the settled slider amount to the nearest preset. Desktop teardown continues through the existing v038 restoration path.

**Tech Stack:** Vanilla JavaScript, CSS, pytest source regressions, browser visual QA.

---

### Task 1: Lock the approved mobile HUD contract

**Files:**
- Modify: `tests/test_v101_regressions.py`

- [ ] Add assertions for the hidden amount row, readable 40 px presets, full gradient slider, adaptive centered turn context, 1,000 ms settle delay, and mobile HUD values without the `BB` suffix.
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_v101_regressions.py -q` and confirm the new assertions fail for the missing implementation.

### Task 2: Implement the compact mobile layout

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] Hide `.amount-row` only inside the v038 mobile media query.
- [ ] Increase preset height and typography, move the slider into the freed row, hide redundant endpoint labels, and render the native range track with a cyan-violet-pink-gold gradient.
- [ ] Center the timer in the left pocket using a viewport/avatar-relative calculation; move timer and context upward with a gap from the HUD and avatar.
- [ ] Make the context width content-driven with compact padding, centered unchanged-size text, and a maximum width for long names.
- [ ] Strip the `BB` suffix only when rendering v038 summary, preset, and action values.

### Task 3: Add settled preset feedback

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] On slider input, clear preset selection immediately and restart one 1,000 ms timeout.
- [ ] When the timeout expires, calculate the nearest current preset amount and highlight only its button.
- [ ] Keep direct preset clicks immediate and clear the timeout during desktop teardown.

### Task 4: Verify and commit

**Files:**
- Test: `tests/test_v101_regressions.py`
- Verify: `static/v038-poker8-v2-cinematic-table.js`

- [ ] Run focused pytest, `node --check`, and `git diff --check`.
- [ ] At 360 by 800, verify no amount stepper, readable presets, gradient slider, separated timer/context, and no `BB` inside the HUD.
- [ ] Resize above 780 px and verify desktop amount controls return.
- [ ] Commit only source, tests, spec, and plan; exclude local SQLite and `.superpowers` state.
