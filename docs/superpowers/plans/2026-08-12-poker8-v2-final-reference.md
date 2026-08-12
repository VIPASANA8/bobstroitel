# Poker8 v2 Final Mobile Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the real mobile Poker8 screen to match the approved cinematic reference, including a perspective table, full reference-style seats, an elevated three-action HUD, and a reserved bottom strip.

**Architecture:** Extend the existing final `v038` presentation pass and current DOM instead of changing the game renderer. CSS owns perspective, materials, seat scale, HUD hierarchy, and safe-area geometry; existing buttons and data remain the only interactive/game-state source.

**Tech Stack:** Vanilla JavaScript, CSS, pytest, existing FastAPI static delivery.

---

### Task 1: Lock the final-reference contract

**Files:**
- Modify: `tests/test_v101_regressions.py`

- [ ] Extend `test_v038_cinematic_table_is_mobile_presentation_only` with assertions for perspective tokens, front-facing HUD, five sizing columns, three action columns, and a bottom-menu reserve token.
- [ ] Run `pytest tests/test_v101_regressions.py::test_v038_cinematic_table_is_mobile_presentation_only -q` and confirm failure because the final-reference tokens are absent.

### Task 2: Implement the final mobile scene

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js`
- Test: `tests/test_v101_regressions.py`

- [ ] Add shared mobile geometry tokens for header, table, HUD, and reserved bottom strip.
- [ ] Apply a restrained perspective transform to the felt/table scene, compensate internal seats/cards/labels for readability, and preserve visible bounds at 360 × 800 and 402 × 874.
- [ ] Increase every seat to the reference silhouette with stable card crowns, larger medallion, and separate plaque while preserving profile-avatar fallback and state styles.
- [ ] Restyle the existing action panel into a fixed-height front-facing HUD with summary row, five preset columns, slider/amount, and three equal primary actions.
- [ ] Keep the existing menu and decorative chat unchanged, and leave the bottom reserve visually empty and non-interactive.
- [ ] Run the focused regression and `git diff --check`; expect green output.

### Task 3: Verify, review, and hand off to grilling

**Files:**
- Verify: `static/v038-poker8-v2-cinematic-table.js`
- Verify: `tests/test_v101_regressions.py`

- [ ] Inspect pre-hand and active-hand layouts at 360 × 800 and 402 × 874: all six seats, pot, board, chips, hero cards, HUD, and reserved strip fit without document scroll or clipping.
- [ ] Verify desktop width above 780 px and desktop-to-mobile resize; desktop stays unchanged and chat initializes on mobile.
- [ ] Run `pytest tests/test_v101_regressions.py -q`, `git diff --check`, and `pytest -q`; report the known unrelated capacity failure if it remains the only failure.
- [ ] Request code review, fix actionable issues, and commit only the spec, plan, v038, and regression test while preserving SQLite state.
- [ ] Start `$grill-me` against the verified product screenshot and approved design decisions.
