# Poker8 v2 Cinematic Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the mobile six-max table's materials and game pieces to closely match the supplied cinematic poker reference, without portrait assets or game-logic changes.

**Architecture:** Add one final `v038` presentation pass after `v037`. It reuses the existing seat, card, chip, wager, and avatar DOM; CSS pseudo-elements provide the wooden rail, card crowns, neutral avatar depth, and material polish, while a focused static regression test locks mobile-only scope and the future profile-avatar hook.

**Tech Stack:** Vanilla JavaScript, CSS, pytest, existing FastAPI static delivery.

---

### Task 1: Lock the cinematic-pass contract

**Files:**
- Modify: `tests/test_v101_regressions.py`

- [ ] Add `test_v038_cinematic_table_is_mobile_presentation_only`, reading `v037` and `v038` and asserting: guarded v038 loader URL/data attribute, `@media (max-width:780px)`, `--profile-avatar-image`, card-crown selectors, pot-chip selectors, no `fetch(`, and no click listener.
- [ ] Run the focused test and confirm it fails because `static/v038-poker8-v2-cinematic-table.js` does not exist.

### Task 2: Add the cinematic table pass

**Files:**
- Modify: `static/v037-poker8-v2-reference-table.js`
- Create: `static/v038-poker8-v2-cinematic-table.js`
- Test: `tests/test_v101_regressions.py`

- [ ] Append a guarded loader for `/static/v038-poker8-v2-cinematic-table.js` with `data-v038-poker8-v2-cinematic-table` after v037 initializes.
- [ ] In v038, inject only a scoped stylesheet; add no event, fetch, persistence, or game-state logic.
- [ ] Build a layered room background and thick oval wooden rail with grain, bevel, inset shadow, and two green neon edge lines.
- [ ] Refine the felt to deep emerald with subtle radial texture and readable contrast.
- [ ] Turn each seat into the reference silhouette: two angled CSS card backs behind a neutral medallion, a compact black plaque, stable per-seat neon accents, and `--profile-avatar-image` as an optional future override.
- [ ] Refine community cards with ivory faces, suit-color borders, stronger rank/suit hierarchy, and narrow five-card spacing.
- [ ] Refine existing `.poker-chip`, `.chip-column`, `.pot-chips`, and `.bet-marker` elements into dimensional stacks with edge stripes and compact numeric labels.
- [ ] Keep the local player's cards and cyan plaque prominent without covering the action tray.
- [ ] Run the focused regression file and `git diff --check`; expect green output.

### Task 3: Visual and regression verification

**Files:**
- Verify: `static/v038-poker8-v2-cinematic-table.js`
- Verify: `static/v037-poker8-v2-reference-table.js`

- [ ] Start the existing FastAPI app and reload the local page after the new pass is served.
- [ ] Inspect 360 × 800 and 402 × 874: rail, felt, six seats, card crowns, pot, board, chip stacks, wagers, hero cards, menu/chat, and action tray remain in-frame without unintended overlap.
- [ ] Click the chat button and confirm no navigation or panel appears.
- [ ] Inspect desktop width above 780 px and desktop-to-mobile resize; desktop remains unchanged and mobile styling initializes correctly.
- [ ] Run `pytest tests/test_v101_regressions.py -q`; expect all focused regressions to pass.
- [ ] Run `pytest -q` and report the known unrelated six-bot-capacity failure separately if it remains the only failure.
- [ ] Commit only the plan, v037/v038, and regression test; preserve all SQLite working-tree state.
