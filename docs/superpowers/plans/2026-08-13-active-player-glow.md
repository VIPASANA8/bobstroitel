# Active Player Glow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current mobile-table player clear through a smoothly pulsing turquoise glow on that player's avatar and identity plate.

**Architecture:** Reuse `.v032-active-turn`, which the existing table renderer places on exactly the current acting seat. Add a mobile-only CSS rule targeting its avatar and identity plate; no JavaScript state, labels, or game logic changes are needed. The effect yields to the existing reduced-motion preference.

**Tech Stack:** Vanilla JavaScript, injected CSS in `static/v038-poker8-v2-cinematic-table.js`, pytest source regression checks.

---

### Task 1: Specify and verify the active-turn glow

**Files:**
- Modify: `static/v038-poker8-v2-cinematic-table.js:357-363`
- Modify: `tests/test_v101_regressions.py:180-205`

- [ ] **Step 1: Write the failing regression assertion**

Add to `test_v038_cinematic_table_is_mobile_presentation_only`:

```python
assert '.seat-card.v032-active-turn .seat-identity' in source
assert '@keyframes v038ActiveTurnPulse' in source
assert '@media (prefers-reduced-motion:reduce)' in source
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_v101_regressions.py -q`

Expected: one assertion failure because the identity-plate selector and active-turn keyframes do not yet exist.

- [ ] **Step 3: Add the minimal mobile-only CSS**

Place this alongside the existing `.v032-active-turn` rule:

```css
body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .player-avatar,
body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn .seat-identity{
  border-color:#55fff2!important;
  box-shadow:0 0 0 3px rgba(1,5,5,.92),0 0 25px rgba(85,255,242,.78),inset 0 -10px 18px rgba(0,0,0,.50)!important;
  animation:v038ActiveTurnPulse 1.35s ease-in-out infinite;
  transition:border-color 220ms ease,box-shadow 220ms ease,filter 220ms ease!important;
}
@keyframes v038ActiveTurnPulse{50%{filter:brightness(1.16);box-shadow:0 0 0 4px rgba(1,5,5,.92),0 0 34px rgba(85,255,242,.94),inset 0 -10px 18px rgba(0,0,0,.50)}}
@media (prefers-reduced-motion:reduce){body.v014.poker8-v2-sixmax .seat .seat-card.v032-active-turn :is(.player-avatar,.seat-identity){animation:none!important;}}
```

Keep the effect scoped to `.v032-active-turn`; do not add a label, a ray, or a new state class.

- [ ] **Step 4: Run automated verification**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_v101_regressions.py -q && node --check static/v038-poker8-v2-cinematic-table.js && git diff --check`

Expected: all focused tests pass, JavaScript syntax check exits zero, and diff check reports no whitespace errors.

- [ ] **Step 5: Verify the live mobile table**

Open `http://127.0.0.1:8000/` at mobile width. Start a hand, then observe two consecutive turns:

1. Only the acting player's avatar and identity plate emit turquoise glow.
2. The glow moves smoothly to the next acting player.
3. No `ХОД` label, ray, rectangular seat background, or changed action semantics appears.

- [ ] **Step 6: Commit**

```bash
git add static/v038-poker8-v2-cinematic-table.js tests/test_v101_regressions.py
git commit -m "feat: highlight active poker player"
```
