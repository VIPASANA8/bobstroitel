# Cashier and Mobile Navigation Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the shared POKER/CUBE cashier, add game/cashier touch swipes, reposition the CUBE result strip, merge to `main`, and deploy the verified build.

**Architecture:** Keep the existing profile DOM and product switch, adding only state-specific text, accessibility state, and styles. A tiny dependency-free `swipe-nav.js` handles touch gestures for the three pages; each page supplies only its destination and direction. CUBE layout changes remain CSS-only.

**Tech Stack:** Static HTML/CSS/JavaScript, Python/pytest source-contract tests, Playwright UI tests, Git worktree, Docker Compose production deployment.

---

### Task 1: Lock the required UI contracts

**Files:**
- Modify: `tests/cash/test_cash_moves_into_the_profile.py`
- Modify: `tests/online/test_lobby_page.py`
- Modify: `tests/e2e/test_profile_redesign.py`

- [ ] **Step 1: Write failing source-contract tests**

Add assertions that require `$$$` in CUBE mode, an inert blank profile tab, the CUBE play card, product-specific withdrawal ordering, cross-product header URLs, the shared swipe helper and its three initializations, and top-pinned result CSS:

```python
assert "cube ? '$$$' : '$$$'" in PROFILE_JS
assert "playModeTab.disabled = cube" in PROFILE_JS
assert "cube-play-card" in PROFILE_JS
assert "Poker8SwipeNav" in PROFILE_JS
assert "Poker8SwipeNav" in LOBBY_JS
assert "Poker8SwipeNav" in CUBE_JS
assert "top: 0" in CUBE_CSS
assert "border-bottom" in CUBE_CSS
```

- [ ] **Step 2: Write failing browser behavior tests**

Cover the visible CUBE labels, empty disabled slot, CUBE play link, CUBE-only pending amount, POKER USDT/CASH pending order, and result-strip geometry:

```python
expect(page.locator("#cashModeMark")).to_have_text("$$$")
expect(page.locator("#playModeTab")).to_be_disabled()
expect(page.locator("#profileModeLabel")).to_have_text("")
assert page.locator("#resultLine").bounding_box()["y"] < page.locator(".cube-scene").bounding_box()["y"]
```

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_cash_moves_into_the_profile.py tests/online/test_lobby_page.py tests/e2e/test_profile_redesign.py -q
```

Expected: failures name the missing product labels, swipe helper, header behavior, and result-strip geometry.

- [ ] **Step 4: Commit the failing tests**

```powershell
git add tests/cash/test_cash_moves_into_the_profile.py tests/online/test_lobby_page.py tests/e2e/test_profile_redesign.py
git commit -m "test: cover cashier navigation polish"
```

### Task 2: Implement cashier and header state

**Files:**
- Modify: `static/profile.js:86-125`
- Modify: `static/profile.css:145-160`
- Modify: `static/cube.html:16-20`
- Modify: `static/cube.css:848-857`

- [ ] **Step 1: Implement product-specific header and tab state**

Update `applyProduct()` so links open games, not the opposite profile, and CUBE leaves an inert reserved slot:

```javascript
$('brandLogo').href = cube ? '/cube' : '/';
$('backToProduct').href = cube ? '/' : '/cube';
$('backToProductLabel').textContent = cube ? 'В POKER' : 'В CUBE';
$('cashModeMark').textContent = '$$$';
$('profileModeLabel').textContent = cube ? '' : 'Профиль Poker';
$('playModeTab').disabled = cube;
$('playModeTab').setAttribute('aria-disabled', String(cube));
```

- [ ] **Step 2: Implement wallet-card variants without changing the grid markup**

Use the existing escrow card as the CUBE play control, restoring it for POKER; render CUBE withdrawal only in USDT and POKER withdrawal as USDT primary/CASH secondary:

```javascript
const playCard = $('profileCashEscrow').parentElement;
playCard.classList.toggle('cube-play-card', cube);
playCard.querySelector('span').textContent = cube ? 'Играть' : 'За столами';
playCard.toggleAttribute('tabindex', cube);

if (name === 'withdrawal') {
  $(strongId).textContent = `${wallet.withdrawal_usdt} USDT`;
  $(smallId).textContent = cube ? '' : `${wallet.withdrawal_units} CASH`;
}
```

Bind click and keyboard activation once to navigate the CUBE play card to `/cube`.

- [ ] **Step 3: Reuse the CUBE header nodes as semantic cross-product links**

The left link reads `В POKER` and points to `/`; the right brand reads `cube⬢` and points to `/cube`. Restyle the former profile chip as the brand link and keep both keyboard accessible.

- [ ] **Step 4: Run focused non-browser tests and confirm GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_cash_moves_into_the_profile.py tests/online/test_lobby_page.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit cashier and header behavior**

```powershell
git add static/profile.js static/profile.css static/cube.html static/cube.css
git commit -m "feat: polish product cashiers and headers"
```

### Task 3: Add touch-only game/cashier swipes

**Files:**
- Create: `static/swipe-nav.js`
- Modify: `static/lobby.html:94-98`
- Modify: `static/lobby.js`
- Modify: `static/cube.html:88-94`
- Modify: `static/cube.js`
- Modify: `static/profile.html:142-148`
- Modify: `static/profile.js`

- [ ] **Step 1: Implement the minimal shared helper**

Expose one initializer that ignores interactive starts and navigates only after a horizontal touch swipe:

```javascript
window.Poker8SwipeNav = ({direction, href}) => {
  let start;
  addEventListener('pointerdown', event => {
    if (event.pointerType !== 'touch' || event.target.closest('a,button,input,select,textarea,canvas,[role="button"]')) return;
    start = {x: event.clientX, y: event.clientY};
  });
  addEventListener('pointerup', event => {
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    start = null;
    if (Math.abs(dx) >= 72 && Math.abs(dx) > Math.abs(dy) * 1.4 && Math.sign(dx) === (direction === 'right' ? 1 : -1)) location.href = href;
  });
};
```

- [ ] **Step 2: Load and initialize the helper**

Initialize exact routes:

```javascript
// lobby.js
window.Poker8SwipeNav?.({direction: 'left', href: '/static/profile.html?app=poker#cash'});
// cube.js
window.Poker8SwipeNav?.({direction: 'left', href: '/static/profile.html?app=cube#cash'});
// profile.js
window.Poker8SwipeNav?.({direction: 'right', href: product === 'cube' ? '/cube' : '/'});
```

- [ ] **Step 3: Run source-contract tests and confirm GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/cash/test_cash_moves_into_the_profile.py tests/online/test_lobby_page.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Commit swipe navigation**

```powershell
git add static/swipe-nav.js static/lobby.html static/lobby.js static/cube.html static/cube.js static/profile.html static/profile.js
git commit -m "feat: add mobile game cashier swipes"
```

### Task 4: Move the CUBE result strip above the cube

**Files:**
- Modify: `static/cube.css:102-177`
- Modify: `static/cube.css:888-905`

- [ ] **Step 1: Pin the strip to the top and reserve its space**

Replace bottom reservation with top reservation, move the separator, and keep a visual gap:

```css
.cube-embed .dice-card{padding-top:80px;padding-bottom:0}
.cube-embed .cube-scene{margin:18px auto 8px}
.cube-embed .result-line{top:0;bottom:auto;border-top:0;border-bottom:1px solid var(--line)}
```

Apply the corresponding desktop padding and cube sizing so the card remains within the viewport.

- [ ] **Step 2: Run the browser regression and confirm GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_profile_redesign.py -q
```

Expected: all profile/cube layout checks pass.

- [ ] **Step 3: Commit the layout change**

```powershell
git add static/cube.css tests/e2e/test_profile_redesign.py
git commit -m "fix: move cube result strip above die"
```

### Task 5: Verify, merge, deploy, and verify production

**Files:**
- Modify only cache-version strings in affected HTML if the server requires explicit asset busting.

- [ ] **Step 1: Run formatting and focused regression checks**

```powershell
git diff --check main...HEAD
.\.venv\Scripts\python.exe -m pytest tests/cash/test_cash_moves_into_the_profile.py tests/online/test_lobby_page.py tests/e2e/test_profile_redesign.py -q
```

Expected: no diff errors and all selected tests pass.

- [ ] **Step 2: Run the full automated suite**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: zero failures; infrastructure-only skips are recorded, not treated as passes.

- [ ] **Step 3: Perform local visual QA**

At phone and desktop widths verify POKER lobby/CASH cashier and CUBE game/USDT cashier, including visible links, reserved blank tab space, card ordering, touch route behavior, and a gap between the top result strip and cube.

- [ ] **Step 4: Merge and push**

Merge the feature branch into `main` without staging the unrelated user files, then:

```powershell
git push origin main
```

- [ ] **Step 5: Deploy through the existing production procedure**

Use the repository's existing deployment host and update script, preserving server-local configuration, then verify the deployed revision.

- [ ] **Step 6: Verify production health and public assets**

Confirm `https://donbass.win/health/ready` is healthy, the app container is healthy, and the public profile/CUBE assets contain the new cache version and UI strings.
