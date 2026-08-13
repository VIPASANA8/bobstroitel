# Mobile Hand Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make mobile seat colors reflect real actions and return a completed table to an unmistakable ready-room state seven seconds after the hand ends.

**Architecture:** Keep the change in the existing mobile presentation pass. Read action truth from `game.history`, decorate only circular avatars, and use a guarded terminal timer to fade the rendered hand out before setting the client view back to `game = null`; the existing ready-phase wrapper then owns the next-hand interaction.

**Tech Stack:** Vanilla JavaScript, injected mobile CSS, pytest source regressions, in-app browser verification.

---

### Task 1: Lock the approved contract in regression tests

**Files:**
- Modify: `tests/test_v101_regressions.py`

- [ ] **Step 1: Write the failing assertions**

Add assertions for `HAND_RESULT_HOLD_MS = 7000`, `syncSeatActionStates`, the four action families, the guarded room-reset token, the room invitation, the symmetric context position, the empty zero-investment line, and explicit suppression of both seat-card pseudo-elements.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `pytest -q tests/test_v101_regressions.py`

Expected: the cinematic-table regression fails because the new behavior tokens are absent.

### Task 2: Render real action colors and remove leftover rectangular layers

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Test: `tests/test_v101_regressions.py`

- [ ] **Step 1: Add action-state synchronization**

Walk `game.history` in order, retain each player's latest action, map it to `fold`, `passive`, `aggressive`, or `all-in`, and add exactly one `v038-action-*` class to the matching `.seat-card`.

- [ ] **Step 2: Style only the circular avatar**

Set red, cold-blue, green, and gold border/glow rules on `.player-avatar`. Explicitly set `.seat-card::before,.seat-card::after` to `display:none`, preserving the separate identity plaque.

- [ ] **Step 3: Run focused tests**

Run: `pytest -q tests/test_v101_regressions.py`

Expected: remaining reset assertions still fail; action/pseudo-layer assertions pass.

### Task 3: Correct the turn pockets and action text

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Test: `tests/test_v101_regressions.py`

- [ ] **Step 1: Make the two pockets symmetric**

Keep the timer at `left:calc(25% - 20.5px)` and place the context at `left:calc(75% + 20.5px)` with `transform:translateX(-50%)`, removing the edge-anchored `right` rule.

- [ ] **Step 2: Remove the false action fallback**

For the context second line, render `ПОСТАВИЛ · <amount>` only when the current actor's `street_invested` is positive; otherwise render an empty string. Do not read another player's last history row.

- [ ] **Step 3: Run focused tests**

Run: `pytest -q tests/test_v101_regressions.py`

Expected: pocket and false-FOLD assertions pass.

### Task 4: Reset a completed hand into the ready room

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Test: `tests/test_v101_regressions.py`

- [ ] **Step 1: Add a guarded seven-second terminal timer**

Store the terminal hand id, schedule once for 7000 ms, and before applying the callback verify that `game.terminal` and the hand id are unchanged. Cancel it as soon as an active hand appears.

- [ ] **Step 2: Fade and clear the client view**

Add `v038-room-resetting`, wait for the short visual fade, then assign `game = null` and call `renderGame()`. This keeps server balances/table data intact while letting the existing ready phase render the room.

- [ ] **Step 3: Add the ready-room invitation**

Create one centered `.v038-room-prompt` with `НОВАЯ РАЗДАЧА` and `Нажмите на свою аватарку`; show it whenever `game` is null. Pulse only the local avatar while it is not ready. Disable the pulse under `prefers-reduced-motion`.

- [ ] **Step 4: Run focused tests and syntax checks**

Run: `pytest -q tests/test_v101_regressions.py && node --check static/v038-poker8-v2-cinematic-table.js && git diff --check`

Expected: all commands exit zero.

### Task 5: Verify the actual mobile UI

**Files:**
- Verify: `http://127.0.0.1:8000/`

- [ ] **Step 1: Reload at the mobile viewport**

Verify the page has no rectangular seat pseudo-layer and the timer/context centers are symmetric around the hero avatar.

- [ ] **Step 2: Verify live actions**

Play or inspect a hand and confirm action classes derive from `game.history`, the context has no false `FOLD`, and the action palette matches the approved mapping.

- [ ] **Step 3: Verify terminal transition**

Confirm the result remains visible for seven seconds, the field fades into the ready room, balances persist, and the invitation plus avatar-ready toggle are visible.

- [ ] **Step 4: Commit only intended files**

Run: `git add static/v038-poker8-v2-cinematic-table.js tests/test_v101_regressions.py && git commit -m "feat: reset completed mobile hands"`

Expected: the database, WAL/SHM files, and `.superpowers/` remain unstaged.
