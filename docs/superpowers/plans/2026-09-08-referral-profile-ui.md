# Referral Profile UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an authenticated, CASH-independent referral tab to the Poker8 profile, expose the existing referral totals and share link, and deploy the verified UI to production.

**Architecture:** Keep the existing `/api/cash/referral` response and settlement code, but replace that route's CASH dependency with the ordinary session dependency. Extend the existing profile tab system and `profile.js`; load the referral summary only on first selection, retain it for the page lifetime, and keep copy/share concerns in small helper functions. No schema, ledger, settlement, admin, or partner-share code changes are required.

**Tech Stack:** FastAPI dependencies, SQLAlchemy-backed referral summary, static HTML/CSS/JavaScript, pytest source/API tests, Playwright UI tests, Docker Compose production deployment.

---

## File map

- `app/routers/cash.py` — expose only the referral summary through normal authenticated identity while leaving every other CASH route gated.
- `static/profile.html` — add the third tab and its accessible panel, loading, success, error, and status nodes.
- `static/profile.js` — show the tab after authentication, load and render the summary lazily, skip hidden tabs during keyboard navigation, and implement copy/share fallbacks.
- `static/profile.css` — style the dedicated panel with the existing Poker/Cube token system and responsive rules.
- `tests/online/test_foundation_api.py` — prove authenticated access with CASH disabled and unauthenticated rejection.
- `tests/cash/test_c2c_routes.py` — lock the narrow dependency exception for the referral route and retain the CASH gate everywhere else.
- `tests/test_profile_page.py` — lock the tab/panel structure and required styling hooks.
- `tests/e2e/test_profile_redesign.py` — exercise lazy loading, rendering, retry, keyboard navigation, copy, Telegram share, Web Share, and mobile width.
- `static/index.html`, `static/lobby.html`, `static/profile.html`, `static/cube.html`, `static/component-ui.js`, `static/v028-ready-phase.js`, `static/v037-poker8-v2-reference-table.js` — advance the shared static cache token through every entry point and nested loader immediately before release.

### Task 1: Open the referral summary to every authenticated account

**Files:**
- Modify: `tests/online/test_foundation_api.py`
- Modify: `tests/cash/test_c2c_routes.py`
- Modify: `app/routers/cash.py:7,87-104`

- [ ] **Step 1: Write API tests that distinguish authentication from CASH access**

Add these tests to `tests/online/test_foundation_api.py`:

```python
def test_unauthenticated_referral_is_rejected(client):
    assert client.get("/api/cash/referral").status_code == 401


def test_referral_is_available_while_cash_stays_off(client):
    assert client.post("/api/auth/dev/101").status_code == 200

    referral = client.get("/api/cash/referral")
    assert referral.status_code == 200
    assert set(referral.json()) == {
        "code", "start_payload", "invited", "pending_micros",
        "paid_micros", "carryover_micros", "link",
    }

    # The exception is read-only and route-specific. CASH remains unavailable.
    assert client.get("/api/cash/wallet").status_code == 404
```

Replace `test_all_user_cash_routes_use_cash_identity_gate` in `tests/cash/test_c2c_routes.py` with:

```python
def test_only_the_referral_summary_bypasses_the_cash_identity_gate():
    app = create_app(Settings.from_mapping({"POKER8_ENV": "development"}))
    routes = {
        route.path: route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/cash/")
    }
    assert set(routes) == {
        "/api/cash/break", "/api/cash/wallet", "/api/cash/operations",
        "/api/cash/referral",
        "/api/cash/deposits", "/api/cash/deposits/{deposit_id}",
        "/api/cash/deposits/{deposit_id}/cancel", "/api/cash/deposits/{deposit_id}/paid",
        "/api/cash/deposits/{deposit_id}/simulate-transfer",
        "/api/cash/fiat-orders", "/api/cash/fiat-orders/active",
        "/api/cash/fiat-orders/{order_id}",
        "/api/cash/fiat-orders/{order_id}/paid", "/api/cash/fiat-orders/{order_id}/cancel",
        "/api/cash/fiat-orders/{order_id}/simulate-trader-confirmation",
        "/api/cash/withdrawals", "/api/cash/withdrawals/{withdrawal_id}",
        "/api/cash/withdrawals/{withdrawal_id}/cancel",
    }
    referral_dependencies = routes["/api/cash/referral"].dependant.dependencies
    assert any(dependency.call is get_current_user for dependency in referral_dependencies)

    cash_routes = [route for path, route in routes.items() if path != "/api/cash/referral"]
    assert all(
        any(dependency.call is get_cash_user for dependency in route.dependant.dependencies)
        for route in cash_routes
    )
```

Update that test module's import:

```python
from app.dependencies import get_cash_user, get_current_user
```

- [ ] **Step 2: Run the new tests and verify the authenticated request fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_foundation_api.py tests/cash/test_c2c_routes.py -q
```

Expected: the unauthenticated assertion passes; the authenticated referral request returns 404 and the dependency assertion cannot find `get_current_user`.

- [ ] **Step 3: Change only the referral route dependency**

In `app/routers/cash.py`, use both dependencies:

```python
from app.dependencies import AuthenticatedUser, get_cash_user, get_current_user
```

Change the route signature to:

```python
@router.get("/referral")
async def referral(request: Request, user: AuthenticatedUser = Depends(get_current_user)):
```

Leave every other route on `get_cash_user`.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_foundation_api.py tests/cash/test_c2c_routes.py -q
```

Expected: all tests in both files pass. The authenticated response creates a stable code even though CASH mode is off, and `/api/cash/wallet` remains 404.

- [ ] **Step 5: Commit the authorization boundary**

```powershell
git add -- app/routers/cash.py tests/online/test_foundation_api.py tests/cash/test_c2c_routes.py
git commit -m "feat(referrals): open summary to authenticated players"
```

### Task 2: Add the dedicated profile tab and accessible layout

**Files:**
- Modify: `tests/test_profile_page.py`
- Modify: `tests/e2e/test_profile_redesign.py`
- Modify: `static/profile.html:23-26,107-142`
- Modify: `static/profile.js:389-464,530-545`
- Modify: `static/profile.css:57-64,143-203`

- [ ] **Step 1: Write structural tests for the selected design**

Add to `tests/test_profile_page.py`:

```python
def test_referrals_are_a_first_class_accessible_profile_tab():
    assert 'id="referralModeTab"' in HTML
    assert 'aria-controls="referralSection"' in HTML
    assert 'id="referralSection" role="tabpanel" aria-labelledby="referralModeTab"' in HTML
    referral = HTML[HTML.index('id="referralSection"'):]
    for element_id in (
        "referralLink", "referralShare", "referralCopy", "referralInvited",
        "referralPending", "referralPaid", "referralCarryover",
        "referralError", "referralRetry", "referralStatus",
    ):
        assert f'id="{element_id}"' in referral
    assert "15% первые 30 дней, затем 5%" in referral
    assert "Получить награду" not in referral


def test_referral_panel_uses_the_existing_profile_tokens_and_phone_layout():
    for selector in (
        ".referral-section{", ".referral-hero{", ".referral-link-row{",
        ".referral-summary{", ".referral-carryover{",
    ):
        assert selector in CSS
    assert "var(--accent)" in CSS[CSS.index(".referral-section{"):]
    phone = CSS[CSS.index("@media(max-width:580px){"):]
    assert ".referral-actions{flex-direction:column}" in phone
```

Add the referral fixture to the dictionary returned by `profile_data()` in `tests/e2e/test_profile_redesign.py`:

```python
'/api/cash/referral': dict(
    code='7KQ2', start_payload='r7KQ2', invited=12,
    pending_micros=8_400_000, paid_micros=31_200_000,
    carryover_micros=-2_750_000,
    link='https://t.me/poker8bot?startapp=r7KQ2',
),
```

Add a keyboard regression to the same file:

```python
def test_referral_tab_survives_cash_failure_and_hidden_tabs_are_skipped(profile_page):
    page, data, _, server = profile_page
    data['/api/cash/wallet'] = None
    page.goto(server + '/static/profile.html')

    cash = page.locator('#cashModeTab')
    profile = page.locator('#playModeTab')
    referral = page.locator('#referralModeTab')
    expect(cash).to_be_hidden()
    expect(referral).to_be_visible()

    profile.focus()
    profile.press('ArrowRight')
    expect(referral).to_be_focused()
    expect(referral).to_have_attribute('aria-selected', 'true')
    expect(page.locator('#referralSection')).to_be_visible()
```

- [ ] **Step 2: Run the tests and verify the tab and styles are missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_profile_page.py -q
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py::test_referral_tab_survives_cash_failure_and_hidden_tabs_are_skipped -q
```

Expected: failures identify the missing tab, panel, CSS selectors, and keyboard target.

- [ ] **Step 3: Add the tab and panel markup**

In the main `profile-modes` tablist in `static/profile.html`, add this button after `playModeTab`:

```html
<button id="referralModeTab" class="mode-tab" type="button" role="tab" aria-selected="false" aria-controls="referralSection" tabindex="-1" hidden>Рефералы</button>
```

After `cashSection` and before the dialogs, add:

```html
<div id="referralSection" role="tabpanel" aria-labelledby="referralModeTab" tabindex="0" hidden>
  <section class="profile-section referral-section" aria-labelledby="referralHeading" aria-busy="true">
    <div class="referral-hero">
      <div>
        <p class="profile-kicker">ПАРТНЁРСКАЯ ПРОГРАММА</p>
        <h1 id="referralHeading">Играй вместе. <span>Получай долю.</span></h1>
        <p>15% первые 30 дней, затем 5% — только с реального дохода Poker и CUBE.</p>
      </div>
    </div>
    <div class="referral-link-row">
      <label for="referralLink">Ваша персональная ссылка</label>
      <input id="referralLink" type="text" value="" placeholder="Загружаем ссылку…" readonly aria-describedby="referralStatus" />
    </div>
    <div class="referral-actions">
      <button id="referralShare" class="profile-button" type="button" disabled>Поделиться</button>
      <button id="referralCopy" class="referral-secondary" type="button" disabled>Копировать</button>
    </div>
    <dl class="referral-summary">
      <div><dt>Приглашено</dt><dd id="referralInvited">—</dd></div>
      <div><dt>На проверке</dt><dd id="referralPending">—</dd></div>
      <div><dt>Выплачено</dt><dd id="referralPaid">—</dd></div>
    </dl>
    <p class="referral-hold">Начисления проходят семидневную проверку и после неё автоматически попадают на денежный баланс.</p>
    <p id="referralCarryover" class="referral-carryover" hidden>CUBE-группе нужно перекрыть <strong id="referralCarryoverAmount">—</strong> до следующего начисления.</p>
    <p id="referralLoading" class="profile-message" role="status">Загружаем реферальные данные…</p>
    <div id="referralError" class="referral-error" hidden>
      <p class="profile-error" role="alert">Не удалось загрузить реферальные данные.</p>
      <button id="referralRetry" class="referral-secondary" type="button">Повторить</button>
    </div>
    <p id="referralStatus" class="section-caption" aria-live="polite"></p>
  </section>
</div>
```

- [ ] **Step 4: Add responsive styles using only existing page tokens**

Add to `static/profile.css` before the Cube context rules:

```css
.referral-section{max-width:820px;margin:24px auto 0;border-color:color-mix(in srgb,var(--accent) 22%,var(--line));background:radial-gradient(circle at 100% 0,color-mix(in srgb,var(--accent) 12%,transparent),transparent 42%),var(--panel)}
.referral-hero{display:grid;grid-template-columns:minmax(0,1fr);padding-bottom:20px;border-bottom:1px solid var(--line)}
.referral-hero h1{margin:0;font-size:clamp(26px,4vw,42px);line-height:1.08;letter-spacing:-.05em}
.referral-hero h1 span{color:var(--accent)}
.referral-hero p:last-child{max-width:620px;margin:12px 0 0;color:var(--muted);font-size:12px;line-height:1.7}
.referral-link-row{display:grid;gap:7px;margin-top:20px;color:var(--muted);font-size:11px}
.referral-link-row input{width:100%;min-height:46px;border:1px solid var(--line);border-radius:9px;padding:10px 12px;background:#101115;color:var(--ink);font:12px ui-monospace,SFMono-Regular,Consolas,monospace;text-overflow:ellipsis}
.referral-actions{display:flex;gap:9px;margin-top:10px}
.referral-actions button{flex:1;min-height:44px}
.referral-secondary{min-height:44px;border:1px solid var(--line);border-radius:8px;padding:10px 14px;background:transparent;color:var(--ink);font-weight:800}
.referral-secondary:hover{border-color:var(--accent);color:var(--accent)}
.referral-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:20px 0 0}
.referral-summary>div{min-width:0;padding:14px;border:1px solid var(--line);border-radius:12px;background:color-mix(in srgb,var(--panel) 82%,#101115)}
.referral-summary dt{color:var(--muted);font-size:10px}
.referral-summary dd{margin:5px 0 0;font:700 clamp(14px,2.2vw,20px) Unbounded,sans-serif;overflow-wrap:anywhere}
.referral-summary>div:nth-child(2) dd{color:#e8c985}
.referral-summary>div:nth-child(3) dd{color:var(--mint)}
.referral-hold,.referral-carryover{margin:12px 0 0;color:var(--muted);font-size:11px;line-height:1.65}
.referral-carryover{padding:11px 13px;border-left:2px solid var(--accent);background:color-mix(in srgb,var(--accent) 5%,transparent)}
.referral-carryover strong{color:var(--ink)}
.referral-error{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px}
.referral-error .profile-error{margin:0}
.referral-section.is-loading :is(.referral-link-row input,.referral-summary dd){color:transparent;background:linear-gradient(100deg,#22232a 35%,#30313a 50%,#22232a 65%);background-size:240% 100%;animation:referral-loading 1.2s linear infinite}
@keyframes referral-loading{to{background-position-x:-240%}}
```

Inside the existing `@media(max-width:580px)` block add:

```css
  .referral-section{margin-top:16px}
  .referral-actions{flex-direction:column}
  .referral-summary{gap:6px}
  .referral-summary>div{padding:11px 8px}
  .referral-summary dt{font-size:8px}
  .referral-summary dd{font-size:12px}
```

Inside the existing reduced-motion rule, disable the skeleton animation:

```css
@media(prefers-reduced-motion:reduce){.referral-section.is-loading :is(.referral-link-row input,.referral-summary dd){animation:none}}
```

- [ ] **Step 5: Reveal the tab after authentication and skip hidden/disabled tabs**

Immediately after `ensureSession()` succeeds in `load()` in `static/profile.js`, add:

```javascript
$('referralModeTab').hidden = false;
document.querySelector('.profile-modes').hidden = false;
```

Replace `bindTabs` with:

```javascript
function bindTabs(list) {
  const tabs = [...list.querySelectorAll('[role="tab"]')];
  const selectable = () => tabs.filter(tab => !tab.hidden && !tab.disabled);
  const selectTab = selected => {
    if (selected.hidden || selected.disabled) return;
    tabs.forEach(tab => {
      const active = tab === selected;
      tab.setAttribute('aria-selected', String(active));
      tab.classList.toggle('is-active', active);
      tab.tabIndex = active ? 0 : -1;
      $(tab.getAttribute('aria-controls')).hidden = !active;
    });
  };
  tabs.forEach(tab => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const choices = selectable();
      const index = choices.indexOf(tab);
      const step = event.key === 'ArrowLeft' ? -1 : 1;
      const next = event.key === 'Home' ? choices[0] : event.key === 'End' ? choices.at(-1)
        : choices[(index + step + choices.length) % choices.length];
      selectTab(next);
      next.focus();
    });
  });
  list.selectTab = selectTab;
}
```

- [ ] **Step 6: Run the structural and keyboard tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_profile_page.py -q
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py::test_referral_tab_survives_cash_failure_and_hidden_tabs_are_skipped -q
```

Expected: all selected tests pass at desktop browser width.

- [ ] **Step 7: Commit the accessible shell**

```powershell
git add -- static/profile.html static/profile.css static/profile.js tests/test_profile_page.py tests/e2e/test_profile_redesign.py
git commit -m "feat(referrals): add profile referral tab"
```

### Task 3: Load, render, cache, and retry the referral summary

**Files:**
- Modify: `tests/e2e/test_profile_redesign.py`
- Modify: `static/profile.js:1-170,389-464`

- [ ] **Step 1: Write browser tests for lazy loading and retry**

Add to `tests/e2e/test_profile_redesign.py`:

```python
def test_referral_summary_loads_once_on_first_open(profile_page):
    page, _, calls, server = profile_page
    page.goto(server + '/static/profile.html')
    assert ('GET', '/api/cash/referral') not in calls

    page.get_by_role('tab', name='Рефералы', exact=True).click()
    expect(page.locator('#referralInvited')).to_have_text('12')
    expect(page.locator('#referralPending')).to_have_text('8.4 USDT')
    expect(page.locator('#referralPaid')).to_have_text('31.2 USDT')
    expect(page.locator('#referralCarryover')).to_contain_text('2.75 USDT')
    expect(page.locator('#referralCarryover')).to_be_visible()
    expect(page.locator('.referral-section')).to_have_attribute('aria-busy', 'false')

    page.get_by_role('tab', name='Профиль Poker', exact=True).click()
    page.get_by_role('tab', name='Рефералы', exact=True).click()
    assert calls.count(('GET', '/api/cash/referral')) == 1


def test_referral_failure_can_be_retried_without_breaking_profile(profile_page):
    page, data, calls, server = profile_page
    referral = data['/api/cash/referral']
    data['/api/cash/referral'] = None
    page.goto(server + '/static/profile.html')
    page.get_by_role('tab', name='Рефералы', exact=True).click()
    expect(page.locator('#referralError')).to_be_visible()
    expect(page.locator('.referral-section')).to_have_attribute('aria-busy', 'false')

    data['/api/cash/referral'] = referral
    page.get_by_role('button', name='Повторить', exact=True).click()
    expect(page.locator('#referralInvited')).to_have_text('12')
    expect(page.locator('#referralError')).to_be_hidden()
    assert calls.count(('GET', '/api/cash/referral')) == 2


def test_zero_cube_carryover_stays_out_of_the_referral_summary(profile_page):
    page, data, _, server = profile_page
    data['/api/cash/referral']['carryover_micros'] = 0
    page.goto(server + '/static/profile.html')
    page.get_by_role('tab', name='Рефералы', exact=True).click()
    expect(page.locator('#referralCarryover')).to_be_hidden()


@pytest.mark.parametrize('width', [360, 390, 1280])
def test_referral_summary_fits_phone_and_desktop_widths(profile_page, width):
    page, _, _, server = profile_page
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto(server + '/static/profile.html')
    page.get_by_role('tab', name='Рефералы', exact=True).click()
    expect(page.locator('.referral-summary > div')).to_have_count(3)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
```

- [ ] **Step 2: Run the tests and verify no referral request is made**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py -k "referral_summary or referral_failure or zero_cube" -q
```

Expected: failures show that selecting the new tab never populates it, retry has no handler, and the responsive referral panel is not available.

- [ ] **Step 3: Add the renderer and one-request page cache**

Add after `renderCashWallet()` in `static/profile.js`:

```javascript
const referralMoney = micros => usdt(micros).replace(/^\+/, '');
let referralLoaded = false;
let referralRequest = null;

function setReferralLoading(loading) {
  const section = document.querySelector('.referral-section');
  section.classList.toggle('is-loading', loading);
  section.setAttribute('aria-busy', String(loading));
  $('referralLoading').hidden = !loading;
  $('referralRetry').disabled = loading;
}

function renderReferral(data) {
  const copyValue = data.link || data.code || '';
  $('referralLink').value = copyValue;
  $('referralLink').placeholder = '';
  $('referralCopy').dataset.value = copyValue;
  $('referralCopy').disabled = !copyValue;
  $('referralShare').dataset.link = data.link || '';
  $('referralShare').disabled = !data.link;
  $('referralShare').textContent = data.link ? 'Поделиться' : 'Ссылка недоступна';
  $('referralInvited').textContent = number(data.invited);
  $('referralPending').textContent = referralMoney(data.pending_micros);
  $('referralPaid').textContent = referralMoney(data.paid_micros);
  const carryover = BigInt(data.carryover_micros || 0);
  $('referralCarryover').hidden = carryover >= 0n;
  $('referralCarryoverAmount').textContent = referralMoney(carryover < 0n ? -carryover : carryover);
}

async function loadReferral() {
  if (referralLoaded) return;
  if (referralRequest) return referralRequest;
  $('referralError').hidden = true;
  $('referralStatus').textContent = '';
  setReferralLoading(true);
  referralRequest = json('/api/cash/referral')
    .then(data => {
      renderReferral(data);
      referralLoaded = true;
    })
    .catch(error => {
      console.error(error);
      $('referralError').hidden = false;
    })
    .finally(() => {
      referralRequest = null;
      setReferralLoading(false);
    });
  return referralRequest;
}
```

In `bindControls()`, add:

```javascript
$('referralRetry').addEventListener('click', loadReferral);
```

At the end of `selectTab()` inside `bindTabs()`, after the `tabs.forEach` block, add:

```javascript
if (selected.id === 'referralModeTab') loadReferral();
```

- [ ] **Step 4: Run syntax and focused browser tests**

Run:

```powershell
node --check static/profile.js
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py -k "referral_summary or referral_failure or zero_cube" -q
```

Expected: JavaScript syntax is valid and the referral rendering, retry, carryover, and responsive tests pass.

- [ ] **Step 5: Commit loading and rendering**

```powershell
git add -- static/profile.js tests/e2e/test_profile_redesign.py
git commit -m "feat(referrals): render profile reward summary"
```

### Task 4: Add copy and Telegram/Web Share actions

**Files:**
- Modify: `tests/e2e/test_profile_redesign.py`
- Modify: `static/profile.js:389-464`

- [ ] **Step 1: Write browser tests for each sharing path and the code fallback**

Add to `tests/e2e/test_profile_redesign.py`:

```python
def test_referral_link_copies_and_uses_telegram_share(profile_page):
    page, _, _, server = profile_page
    page.add_init_script("""
      window.__copied = [];
      Object.defineProperty(navigator, 'clipboard', {value: {
        writeText: value => { window.__copied.push(value); return Promise.resolve(); }
      }});
    """)
    page.goto(server + '/static/profile.html')
    page.evaluate("""window.Telegram = {WebApp: {
      openTelegramLink: value => { window.__telegramShare = value; }
    }}""")
    page.get_by_role('tab', name='Рефералы', exact=True).click()

    page.get_by_role('button', name='Копировать', exact=True).click()
    expect(page.locator('#referralStatus')).to_contain_text('Ссылка скопирована')
    assert page.evaluate('window.__copied') == ['https://t.me/poker8bot?startapp=r7KQ2']

    page.get_by_role('button', name='Поделиться', exact=True).click()
    shared = page.evaluate('window.__telegramShare')
    assert shared.startswith('https://t.me/share/url?')
    assert 'poker8bot' in shared


def test_referral_share_falls_back_to_web_share(profile_page):
    page, _, _, server = profile_page
    page.add_init_script("""
      window.__webShares = [];
      Object.defineProperty(navigator, 'share', {value: payload => {
        window.__webShares.push(payload); return Promise.resolve();
      }});
    """)
    page.goto(server + '/static/profile.html')
    page.evaluate('delete window.Telegram')
    page.get_by_role('tab', name='Рефералы', exact=True).click()
    page.get_by_role('button', name='Поделиться', exact=True).click()
    assert page.evaluate('window.__webShares[0].url') == 'https://t.me/poker8bot?startapp=r7KQ2'


def test_missing_referral_link_copies_the_code_and_disables_share(profile_page):
    page, data, _, server = profile_page
    data['/api/cash/referral']['link'] = None
    page.add_init_script("""
      window.__copied = [];
      Object.defineProperty(navigator, 'clipboard', {value: {
        writeText: value => { window.__copied.push(value); return Promise.resolve(); }
      }});
    """)
    page.goto(server + '/static/profile.html')
    page.get_by_role('tab', name='Рефералы', exact=True).click()
    expect(page.locator('#referralLink')).to_have_value('7KQ2')
    expect(page.locator('#referralShare')).to_be_disabled()
    expect(page.locator('#referralShare')).to_have_text('Ссылка недоступна')
    page.get_by_role('button', name='Копировать', exact=True).click()
    assert page.evaluate('window.__copied') == ['7KQ2']


def test_referral_action_failures_are_announced(profile_page):
    page, _, _, server = profile_page
    page.add_init_script("""
      Object.defineProperty(navigator, 'clipboard', {value: {
        writeText: () => Promise.reject(new Error('clipboard denied'))
      }});
      Object.defineProperty(navigator, 'share', {value: () =>
        Promise.reject(new Error('share denied'))
      });
    """)
    page.goto(server + '/static/profile.html')
    page.evaluate('delete window.Telegram')
    page.get_by_role('tab', name='Рефералы', exact=True).click()

    page.get_by_role('button', name='Копировать', exact=True).click()
    expect(page.locator('#referralStatus')).to_contain_text('Не удалось скопировать')
    page.get_by_role('button', name='Поделиться', exact=True).click()
    expect(page.locator('#referralStatus')).to_contain_text('Поделиться не удалось')
```

- [ ] **Step 2: Run the tests and verify the buttons have no behaviour**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py -k "referral_link_copies or referral_share_falls or missing_referral_link or referral_action_failures" -q
```

Expected: the tests fail because neither button has a click handler and failures are not announced.

- [ ] **Step 3: Add copy and share helpers**

Add before `bindControls()` in `static/profile.js`:

```javascript
function setReferralStatus(message) {
  $('referralStatus').textContent = message;
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const field = document.createElement('textarea');
  field.value = value;
  field.setAttribute('readonly', '');
  field.style.position = 'fixed';
  field.style.opacity = '0';
  document.body.append(field);
  field.select();
  const copied = document.execCommand('copy');
  field.remove();
  if (!copied) throw new Error('copy unavailable');
}

async function copyReferral() {
  const value = $('referralCopy').dataset.value;
  if (!value) return;
  try {
    await copyText(value);
    setReferralStatus(dataLink(value) ? 'Ссылка скопирована.' : 'Код скопирован.');
  } catch (error) {
    console.error(error);
    setReferralStatus('Не удалось скопировать. Выделите значение вручную.');
  }
}

function dataLink(value) {
  return /^https:\/\//.test(value);
}

async function shareReferral() {
  const link = $('referralShare').dataset.link;
  if (!link) return;
  const text = 'Присоединяйся ко мне в Poker8';
  try {
    const telegram = window.Telegram?.WebApp;
    if (telegram?.openTelegramLink) {
      const query = new URLSearchParams({url: link, text});
      telegram.openTelegramLink(`https://t.me/share/url?${query}`);
      return;
    }
    if (navigator.share) {
      await navigator.share({title: 'Poker8', text, url: link});
      return;
    }
    setReferralStatus('Поделиться не удалось. Скопируйте ссылку.');
  } catch (error) {
    if (error?.name !== 'AbortError') {
      console.error(error);
      setReferralStatus('Поделиться не удалось. Скопируйте ссылку.');
    }
  }
}
```

In `bindControls()`, add:

```javascript
$('referralCopy').addEventListener('click', copyReferral);
$('referralShare').addEventListener('click', shareReferral);
```

- [ ] **Step 4: Run syntax and action tests**

Run:

```powershell
node --check static/profile.js
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py -k "referral_link_copies or referral_share_falls or missing_referral_link or referral_action_failures" -q
```

Expected: syntax is valid; copy writes the exact link/code; Telegram uses `t.me/share/url`; the browser fallback receives a Web Share payload.

- [ ] **Step 5: Commit the actions**

```powershell
git add -- static/profile.js tests/e2e/test_profile_redesign.py
git commit -m "feat(referrals): add profile sharing actions"
```

### Task 5: Verify, release, and inspect production

**Files:**
- Modify: `static/index.html`
- Modify: `static/lobby.html`
- Modify: `static/profile.html`
- Modify: `static/cube.html`
- Modify: `static/component-ui.js`
- Modify: `static/v028-ready-phase.js`
- Modify: `static/v037-poker8-v2-reference-table.js`

- [ ] **Step 1: Advance the shared cache token**

Replace every `?v=cash-first-1` under `static/` with `?v=referral-profile-1`, including the nested loader URLs in `component-ui.js`, `v028-ready-phase.js`, and `v037-poker8-v2-reference-table.js`. Do not change asset filenames.

Run the existing cache contract:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_profile_page.py::test_every_page_shares_one_cache_token tests/test_the_loader_chain_moves_as_one.py -q
```

Expected: all cache-contract tests pass with exactly one shared token across the entry pages and every nested loader.

- [ ] **Step 2: Run focused backend and UI verification**

```powershell
node --check static/profile.js
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/online/test_foundation_api.py tests/cash/test_c2c_routes.py tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py tests/cash/test_cash_client.py -q
.\.venv\Scripts\python.exe -m pytest -m e2e tests/e2e/test_profile_redesign.py -q
```

Expected: JavaScript syntax and diff checks are clean; every selected pytest test passes.

- [ ] **Step 3: Run the PostgreSQL money suite and the regular full suite**

Start only the local test database if it is not already healthy:

```powershell
docker compose -f compose.yaml up -d postgres_test
$env:POKER8_CASH_TEST_DATABASE_URL='postgresql+psycopg://poker8:poker8@localhost:5433/poker8_test'
.\.venv\Scripts\python.exe -m pytest tests/cash -m postgres -q
Remove-Item Env:POKER8_CASH_TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: the PostgreSQL suite and full default suite complete with zero failures. Declared skips are reported separately and never counted as coverage for a skipped money path.

- [ ] **Step 4: Perform desktop and phone visual QA**

At 1280×900, 390×844, and 360×800 verify:

- referral navigation is visible after authentication in Poker and Cube contexts;
- a failed/hidden cashier does not remove the referral tab;
- the three summary values fit without horizontal scrolling;
- long links truncate visually and copy in full;
- the carryover notice names Cube and disappears at zero;
- tab arrows skip hidden CASH and disabled Cube profile slots;
- share/copy/retry status is readable and receives visible keyboard focus.

- [ ] **Step 5: Commit the release token**

```powershell
git add -- static/index.html static/lobby.html static/profile.html static/cube.html static/component-ui.js static/v028-ready-phase.js static/v037-poker8-v2-reference-table.js
git commit -m "chore: refresh referral profile assets"
```

- [ ] **Step 6: Confirm the branch contains only intended work, merge, and push**

```powershell
git status --short
git diff --stat main...HEAD
git log --oneline main..HEAD
```

Preserve the existing user-owned edits to `docs/superpowers/plans/2026-08-31-cash-foundation.md` and the untracked image files. Merge the isolated implementation branch into `main` with a fast-forward when possible, then:

```powershell
git push origin main
```

Expected: `origin/main` points to the verified referral UI commit without staging unrelated files.

- [ ] **Step 7: Deploy through the existing production updater**

```powershell
ssh newvps "cd /opt/poker8 && sh deploy/poker8-update.sh donbass.win"
```

Expected: the updater reports the pushed revision, applies no new migration, rebuilds/restarts the app, and finishes with `ready:200`.

- [ ] **Step 8: Verify public health, authorization, assets, and partner configuration**

Run unauthenticated and static checks:

```powershell
curl.exe -fsS https://donbass.win/health/ready
curl.exe -sS -o NUL -w "%{http_code}" https://donbass.win/api/cash/referral
curl.exe -fsS https://donbass.win/static/profile.html | Select-String "referralModeTab|referral-profile-1"
ssh newvps "cd /opt/poker8 && docker compose -f compose.pilot.yaml -f deploy/compose.caddy.yaml ps"
```

Expected: readiness succeeds, the unauthenticated referral request prints `401`, public profile markup contains the referral tab and new cache token, and app/Caddy/PostgreSQL are healthy.

Finally open the production Mini App with an authenticated Telegram account and verify the referral tab loads a real code/link while a non-allowlisted account still cannot open CASH operations. Read the partner configuration through the existing admin report and confirm the effective Cube-only monthly share remains `5000` basis points; do not post a second share row.
