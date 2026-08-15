# Poker8 Online Table Visual Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the authoritative online table state inside the already-built Poker8 mobile table instead of the temporary technical surface.

**Architecture:** Keep `index.html`, `style.css`, and the v032–v038 visual layers as the only table presentation. Add a small bridge in `app.js` that accepts a server snapshot in the existing render shape; `online-table.js` owns only network polling, WebSocket events, readiness, and chat. The bridge normalizes server state for the existing seat/card/action renderers and never exposes private cards beyond the snapshot received for the current viewer.

**Tech Stack:** Vanilla JavaScript, existing Poker8 CSS/DOM, FastAPI JSON/WebSocket endpoints, pytest source-contract tests, browser smoke test.

---

### Task 1: Lock the visual bridge contract

**Files:**
- Modify: `tests/online/test_lobby_page.py`

- [ ] **Step 1: Write the failing contract assertions**

Assert that the online client delegates to `Poker8LegacyView`, does not create the temporary `onlineSurface`, and that the legacy app skips its local API bootstrap when a `table` query is present.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest tests/online/test_lobby_page.py -q`

Expected: failure because the current online client still creates and hides the temporary surface.

### Task 2: Connect server snapshots to the existing Poker8 renderer

**Files:**
- Modify: `static/app.js`
- Modify: `static/online-table.js`

- [ ] **Step 1: Add the minimal bridge**

Expose a `window.Poker8LegacyView.renderSnapshot` function from `app.js`. It maps six server seats into the existing `tableData.seats`, normalizes viewer/action fields, sets `game` for active/result phases, and calls the existing `renderGame()`.

- [ ] **Step 2: Replace the temporary surface**

Make `online-table.js` keep `.app-shell` visible, remove only local-only controls that cannot be backed by the online API, and send snapshots through the bridge. Keep WebSocket commands, ready state, chat, reconnect, and countdown behavior in this file.

- [ ] **Step 3: Wire existing action controls**

Let the legacy action buttons call `Poker8Transport.sendAction` with server revision and BB-to-unit conversion. Preserve the current private-card visibility from the server snapshot.

- [ ] **Step 4: Run syntax and focused tests**

Run: `pytest tests/online/test_lobby_page.py -q` and `node --check static/app.js` and `node --check static/online-table.js`.

### Task 3: Verify visual states

**Files:**
- Modify: `tests/online/test_table_ui_states.py` only if a missing state contract is found.

- [ ] **Step 1: Run the full local suite**

Run: `pytest -q`

- [ ] **Step 2: Browser smoke test at mobile width**

Open `/table?table=micro-a`, verify the existing felt, six seat layout, cards, pot, ready/waiting state, action panel, chat, and `connected` status.

- [ ] **Step 3: Browser smoke test at desktop width**

Verify the same DOM remains usable without the temporary surface and that the desktop sidebar is still present.

### Task 4: Deploy and verify staging

**Files:**
- No server source changes beyond the committed static files.

- [ ] **Step 1: Commit the local integration**

Commit: `feat: connect online runtime to poker8 table visual`

- [ ] **Step 2: Build and restart only Poker8**

Deploy the current commit to `/root/poker8` and restart the Poker8 compose stack without touching `autorek`.

- [ ] **Step 3: Verify health and recent logs**

Check `/health`, container health, and recent app errors; then repeat the browser smoke test against `http://64.188.67.9:8000`.
