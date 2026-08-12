# Poker8 v2 Reference Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the mobile six-max table to the approved reference and add an inert chat button.

**Architecture:** Keep the existing DOM and game logic. Append a `v037` presentation pass after `v036`; it injects a decorative chat button and mobile-scoped CSS only.

**Tech Stack:** FastAPI static files, vanilla JavaScript, CSS, pytest.

---

### Task 1: Regression contract

**Files:**
- Modify: `tests/test_v101_regressions.py`

- [ ] Write a failing test which reads `static/v036-poker8-v2-prehand-pass.js` and `static/v037-poker8-v2-reference-table.js`, asserting the loader URL and data attribute, `mobileChatButton`, `aria-label="Чат"`, `type="button"`, mobile media query, and absence of click handlers.
- [ ] Run `pytest tests/test_v101_regressions.py::test_v037_reference_table_pass_is_loaded_and_chat_is_decorative -q`; expect failure because v037 is absent.

### Task 2: Isolated visual pass

**Files:**
- Modify: `static/v036-poker8-v2-prehand-pass.js`
- Create: `static/v037-poker8-v2-reference-table.js`
- Modify: `tests/test_v101_regressions.py`

- [ ] Extend v036 with a guarded dynamic script loader for `/static/v037-poker8-v2-reference-table.js` and `data-v037-poker8-v2-reference-table`.
- [ ] Implement v037: on mobile v2 only, insert `#mobileChatButton.mobile-chat-button` into `#mobileGameHeader`. Give it `type="button"`, `aria-label="Чат"`, an inline chat SVG, and no event listener.
- [ ] Scope CSS to `@media (max-width:780px)` and `body.v014.poker8-v2-sixmax`: hide the existing right primary action, match the chat icon to the cyan menu control, add dark wood backing, emerald oval felt with twin neon rail, colored opponent plaques, cyan hero plaque, and compact pot styling.
- [ ] Run `pytest tests/test_v101_regressions.py::test_v037_reference_table_pass_is_loaded_and_chat_is_decorative -q`; expect `1 passed`.
- [ ] Run `git diff --check`; expect exit code `0`.
- [ ] Commit only the test and visual-pass files with `feat: restyle mobile poker table to reference`.

### Task 3: End-to-end verification

**Files:**
- Verify: `static/v036-poker8-v2-prehand-pass.js`
- Verify: `static/v037-poker8-v2-reference-table.js`

- [ ] Run `pytest -q`; expect exit code `0` and no failures.
- [ ] Start `uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- [ ] Inspect `360 × 800` and `402 × 874`: six seats, pot, board, chips, hero cards, menu, chat, and action area fit without unintended overlap; the chat button is inert.
- [ ] Inspect a width above 780 px: chat control is absent and desktop is unchanged.
- [ ] If needed, make CSS-only corrections in v037, repeat all verification, and commit `fix: tune reference table mobile spacing`.
