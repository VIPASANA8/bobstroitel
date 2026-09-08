# Mobile Referral Tab Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show only `🔗` in the referral profile tab at viewport widths up to 580 px while retaining the visible desktop label and the accessible name `Рефералы`.

**Architecture:** Keep separate desktop and mobile visual spans inside the existing tab. The existing `@media(max-width:580px)` block controls which span is displayed; JavaScript behavior and API calls do not change.

**Tech Stack:** HTML, CSS media queries, pytest source assertions, Playwright browser tests.

---

### Task 1: Add the responsive tab label

**Files:**
- Modify: `tests/test_profile_page.py`
- Modify: `tests/e2e/test_profile_redesign.py`
- Modify: `static/profile.html`
- Modify: `static/profile.css`

- [ ] **Step 1: Write failing source and browser tests**

Add assertions that `#referralModeTab` contains:

```html
<span class="referral-tab-label">Рефералы</span><span class="referral-tab-icon" aria-hidden="true">🔗</span>
```

Assert that the base CSS hides `.referral-tab-icon`, while the existing `@media(max-width:580px)` block hides `.referral-tab-label` and shows `.referral-tab-icon`. In Playwright, verify the icon is visible at 580 px, the text is visible at 581 px, and the tab's accessible name remains `Рефералы` at both widths.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
C:\project\poker\.venv\Scripts\python.exe -m pytest -q tests\test_profile_page.py tests\e2e\test_profile_redesign.py -m "e2e or not e2e"
```

Expected: the new assertions fail because the two label spans and visibility rules do not exist.

- [ ] **Step 3: Implement the minimal markup and CSS**

Change the tab to:

```html
<button id="referralModeTab" class="mode-tab" type="button" role="tab" aria-label="Рефералы" aria-selected="false" aria-controls="referralSection" tabindex="-1" hidden><span class="referral-tab-label">Рефералы</span><span class="referral-tab-icon" aria-hidden="true">🔗</span></button>
```

Add the base rule:

```css
.referral-tab-icon{display:none}
```

Add inside `@media(max-width:580px)`:

```css
.referral-tab-label{display:none}
.referral-tab-icon{display:inline}
```

- [ ] **Step 4: Verify GREEN and regression safety**

Run:

```powershell
C:\project\poker\.venv\Scripts\python.exe -m pytest -q tests\test_profile_page.py
C:\project\poker\.venv\Scripts\python.exe -m pytest -q -m e2e tests\e2e\test_profile_redesign.py
C:\project\poker\.venv\Scripts\python.exe -m pytest -q
node --check static\profile.js
git diff --check
```

Expected: every command exits successfully.

- [ ] **Step 5: Commit**

```powershell
git add static/profile.html static/profile.css tests/test_profile_page.py tests/e2e/test_profile_redesign.py docs/superpowers/plans/2026-09-08-referral-mobile-tab-icon.md
git commit -m "fix(profile): compact referral tab on phones"
```

### Task 2: Publish and verify production

**Files:**
- Modify: `static/index.html`
- Modify: `static/lobby.html`
- Modify: `static/profile.html`
- Modify: `static/cube.html`
- Modify: `static/component-ui.js`
- Modify: `static/v028-ready-phase.js`
- Modify: `static/v037-poker8-v2-reference-table.js`

- [ ] **Step 1: Update the static cache token**

Replace `referral-profile-1` with `referral-tab-icon-1` across the existing loader chain and run:

```powershell
C:\project\poker\.venv\Scripts\python.exe -m pytest -q tests\test_the_loader_chain_moves_as_one.py
```

Expected: the loader-chain contract passes with one consistent token.

- [ ] **Step 2: Push and deploy**

```powershell
git push origin main
ssh newvps "cd /opt/poker8 && sh deploy/poker8-update.sh donbass.win"
```

- [ ] **Step 3: Verify production**

Confirm `/health/ready` returns 200, `static/profile.html` contains `referral-tab-icon` and the new cache token, and the deployed git commit matches local `main`.
