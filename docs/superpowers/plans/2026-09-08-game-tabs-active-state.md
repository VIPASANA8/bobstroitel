# POKER / CUBE Active Tab Visual State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the active POKER or CUBE bottom tab read immediately as a selected segment while preserving the switcher's geometry, markup, responsive layout, and navigation behavior.

**Architecture:** Keep the existing shared `game-tabs.css` component and its current selectors. Add a shared inactive/active color contract, then specialize only the active surface, border, icon color, and inset glow for POKER and CUBE through the existing product-specific classes.

**Tech Stack:** Static HTML/CSS, Python 3, pytest, Playwright end-to-end checks.

---

## File Structure

- Create `tests/test_game_tabs_visual_state.py`: focused source-level CSS and markup contract for inactive, POKER-active, and CUBE-active states.
- Modify `static/game-tabs.css`: visual declarations only; retain every geometry and layout declaration.
- Read without modifying `static/lobby.html` and `static/cube.html`: confirm the existing `is-active` and `aria-current` state mapping.

### Task 1: Lock the visual contract with a failing test

**Files:**
- Create: `tests/test_game_tabs_visual_state.py`
- Test: `tests/test_game_tabs_visual_state.py`

- [ ] **Step 1: Write the failing CSS and markup contract test**

```python
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "game-tabs.css").read_text(encoding="utf-8")
LOBBY = (ROOT / "static" / "lobby.html").read_text(encoding="utf-8")
CUBE = (ROOT / "static" / "cube.html").read_text(encoding="utf-8")


def rule(selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", CSS)
    assert match, f"missing CSS rule: {selector}"
    return re.sub(r"\s+", "", match.group(1)).lower()


def test_game_tabs_use_equal_selected_segment_visuals():
    inactive = rule(".game-tab")
    active = rule(".game-tab.is-active")
    poker = rule(".game-tab-poker.is-active")
    poker_icon = rule(".game-tab-poker.is-active>i")
    cube = rule(".game-tab-cube.is-active")
    cube_icon = rule(".game-tab-cube.is-active>i")

    assert "border:1pxsolidtransparent" in inactive
    assert "color:#747985" in inactive
    assert "color:#fff" in active
    assert "font-weight:700" in active

    assert "background:rgba(181,140,255,.12)" in poker
    assert "border-color:rgba(181,140,255,.45)" in poker
    assert "box-shadow:inset00" in poker
    assert "color:#b58cff" in poker_icon

    assert "background:rgba(183,255,38,.11)" in cube
    assert "border-color:rgba(183,255,38,.4)" in cube
    assert "box-shadow:inset00" in cube
    assert "color:#b7ff26" in cube_icon


def test_pages_keep_the_existing_active_tab_mapping():
    assert 'class="game-tab game-tab-poker is-active"' in LOBBY
    assert 'class="game-tab game-tab-cube"' in LOBBY
    assert 'class="game-tab game-tab-poker"' in CUBE
    assert 'class="game-tab game-tab-cube is-active"' in CUBE
    assert LOBBY.count('aria-current="page"') == 1
    assert CUBE.count('aria-current="page"') == 1
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
pytest tests/test_game_tabs_visual_state.py -q
```

Expected: `test_game_tabs_use_equal_selected_segment_visuals` fails because the current inactive color is `#81878d`, the active label inherits an accent color, and the requested product-specific surfaces and borders do not exist. The markup mapping test passes.

- [ ] **Step 3: Commit the failing contract test**

```powershell
git add tests/test_game_tabs_visual_state.py
git commit -m "test: define game tab visual states"
```

### Task 2: Implement the equal active-segment treatment

**Files:**
- Modify: `static/game-tabs.css:12-20`
- Test: `tests/test_game_tabs_visual_state.py`

- [ ] **Step 1: Replace only the visual state declarations**

Keep `.game-tabs` and all layout properties unchanged. Update the tab state rules to:

```css
.game-tab{
  display:grid;grid-auto-flow:column;align-items:center;justify-content:center;
  gap:8px;min-height:46px;border:1px solid transparent;border-radius:13px;
  color:#747985;text-decoration:none;
  font:800 12px/1 Manrope,ui-sans-serif,system-ui,sans-serif;letter-spacing:.08em;
}
.game-tab>i{font:15px/1 Georgia,serif;font-style:normal}
.game-tab.is-active{color:#fff;font-weight:700}
.game-tab-poker.is-active{
  background:rgba(181,140,255,.12);border-color:rgba(181,140,255,.45);
  box-shadow:inset 0 0 12px rgba(181,140,255,.06);
}
.game-tab-poker.is-active>i{color:#b58cff}
.game-tab-cube.is-active{
  background:rgba(183,255,38,.11);border-color:rgba(183,255,38,.4);
  box-shadow:inset 0 0 12px rgba(183,255,38,.05);
}
.game-tab-cube.is-active>i{color:#b7ff26}
```

The transparent one-pixel base border keeps the existing outer dimensions and the active/inactive content box stable. Do not alter the switcher width, padding, gap, fixed position, tab minimum height, radius, safe-area expressions, HTML, or JavaScript.

- [ ] **Step 2: Run the focused test and verify GREEN**

Run:

```powershell
pytest tests/test_game_tabs_visual_state.py -q
```

Expected: `2 passed`.

- [ ] **Step 3: Run the relevant existing layout and navigation checks**

Run:

```powershell
pytest tests/e2e/test_profile_redesign.py -q -k "fixed_game_tabs or swipes_starting_on_interactive_controls"
```

Expected: all selected tests pass; the fixed switcher still clears the CUBE action and its links retain their navigation behavior.

- [ ] **Step 4: Check that the implementation diff is CSS-only plus its test**

Run:

```powershell
git diff --check
git diff -- static/game-tabs.css tests/test_game_tabs_visual_state.py
```

Expected: no whitespace errors; production changes are limited to visual declarations in `static/game-tabs.css`, and the only other change is the focused test.

- [ ] **Step 5: Commit the implementation**

```powershell
git add static/game-tabs.css tests/test_game_tabs_visual_state.py
git commit -m "style: clarify active game tab"
```

### Task 3: Visually verify both active states

**Files:**
- Verify: `static/lobby.html`
- Verify: `static/cube.html`
- Verify: `static/game-tabs.css`

- [ ] **Step 1: Start the existing development app**

Run:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected: the app starts without errors and serves `/` and `/cube`.

- [ ] **Step 2: Inspect POKER at a phone viewport**

Open `/` at `390 × 844`. Confirm the POKER label is white, its spade is purple, its purple-tinted surface and border clearly form a selected segment, CUBE is gray and transparent, and the panel position, size, radius, spacing, and mobile clearance match the pre-change layout.

- [ ] **Step 3: Inspect CUBE at the same phone viewport**

Open `/cube` at `390 × 844`. Confirm the CUBE label is white, its hexagon is lime, its lime-tinted surface and border use the same visual hierarchy as POKER, POKER is gray and transparent, and the panel geometry remains unchanged.

- [ ] **Step 4: Run the final focused verification**

Run:

```powershell
pytest tests/test_game_tabs_visual_state.py tests/e2e/test_profile_redesign.py -q -k "game_tabs or fixed_game_tabs or swipes_starting_on_interactive_controls"
```

Expected: all selected tests pass with no errors or warnings caused by the change.
