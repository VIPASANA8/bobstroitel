# Poker/CUBE Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse one shared cashier in Poker and CUBE contexts, move activity history into it, and keep CUBE's profile intentionally empty.

**Architecture:** `profile.html` remains the only profile page. A URL `app` query selects Poker or CUBE presentation, while the same wallet API and cashier dialogs power both. The browser combines cash Poker hands, CUBE rounds, and completed deposits/withdrawals into one tabbed history; the only new data API is read-only CUBE round history.

**Tech Stack:** FastAPI, SQLAlchemy Core/async sessions, static HTML/CSS/JavaScript, pytest.

---

### Task 1: Expose the signed-in player's CUBE round history

**Files:**
- Modify: `cash/cube.py`
- Modify: `app/routers/cube.py`
- Test: `tests/cash/test_cube.py`

- [ ] **Step 1: Write a failing service test**

Append a test that settles two rounds and checks newest-first, user isolation, the computed net amount, and the limit:

```python
async def test_recent_rounds_are_newest_first_and_private(cash_db):
    await fund(cash_db)
    service = CashCubeService(cash_db)
    first = await service.settle("alice", "round-1", STAKE, [2, 5])
    second = await service.settle("alice", "round-2", STAKE, [1])

    rows = await service.recent("alice", limit=1)

    assert [row["round_id"] for row in rows] == [second["round_id"]]
    assert rows[0]["net_micros"] == second["payout_micros"] - second["stake_micros"]
    assert rows[0]["won"] == second["won"]
    assert await service.recent("bob", limit=20) == []
    assert first["round_id"] != second["round_id"]
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `pytest tests/cash/test_cube.py::test_recent_rounds_are_newest_first_and_private -q`

Expected: failure because `CashCubeService.recent` does not exist.

- [ ] **Step 3: Add the minimal read method and route**

Add this method to `CashCubeService`:

```python
async def recent(self, user_id: str, *, limit: int = 20) -> list[dict[str, object]]:
    async with self.session_factory() as session:
        rows = (await session.execute(
            select(cube_rounds)
            .where(cube_rounds.c.user_id == user_id)
            .order_by(cube_rounds.c.created_at.desc(), cube_rounds.c.id.desc())
            .limit(limit)
        )).mappings().all()
    return [{
        "round_id": row["id"],
        "selected": [int(face) for face in row["selected"].split(",")],
        "roll": int(row["roll"]),
        "stake_micros": int(row["stake_micros"]),
        "payout_micros": int(row["payout_micros"]),
        "net_micros": int(row["payout_micros"]) - int(row["stake_micros"]),
        "won": int(row["payout_micros"]) > 0,
        "created_at": row["created_at"],
    } for row in rows]
```

Add `Query` to the FastAPI imports in `app/routers/cube.py`, then add:

```python
@router.get("/history")
async def history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_cash_user),
):
    return {"rounds": await request.app.state.cube.recent(user.user_id, limit=limit)}
```

- [ ] **Step 4: Run the focused backend tests and confirm GREEN**

Run: `pytest tests/cash/test_cube.py -q`

Expected: all CUBE service tests pass; PostgreSQL-marked tests may skip when the local PostgreSQL fixture is unavailable.

- [ ] **Step 5: Commit the backend slice**

```powershell
git add cash/cube.py app/routers/cube.py tests/cash/test_cube.py
git commit -m "feat(cube): expose player round history"
```

### Task 2: Replace profile-local history with the shared cashier history structure

**Files:**
- Modify: `static/profile.html`
- Modify: `tests/test_profile_page.py`
- Modify: `tests/cash/test_cash_moves_into_the_profile.py`

- [ ] **Step 1: Write failing markup contract tests**

Add assertions for the context hooks, the empty CUBE profile, and the four cashier history tabs:

```python
def test_profile_supports_poker_and_cube_contexts():
    for element_id in (
        "brandLogo", "backToProduct", "cashModeLabel", "profileModeLabel",
        "pokerProfile", "cubeProfile", "cashHistory",
    ):
        assert f'id="{element_id}"' in HTML
    assert 'Профиль CUBE пока пуст' in HTML


def test_history_belongs_only_to_the_shared_cashier():
    cash_half = HTML[HTML.index('id="cashSection"'):]
    poker_half = HTML[HTML.index('id="pokerProfile"'):HTML.index('id="cashSection"')]
    assert 'aria-label="История кассы"' in cash_half
    for name in ("Общее", "CUBE", "POKER", "Операции"):
        assert f'>{name}</button>' in cash_half
    assert 'aria-label="Тип истории"' not in poker_half
```

Update the old test that required `handHistory` in the Poker profile so it requires `cashHistory` instead. Update the CASH/profile separation test so it expects the history inside `cashSection`, not in `playSection`.

- [ ] **Step 2: Run the static tests and confirm RED**

Run: `pytest tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py -q`

Expected: failures for the missing context IDs and four history tabs.

- [ ] **Step 3: Restructure the existing page without duplicating the cashier**

In `static/profile.html`:

- add `id="backToProduct"` to the back link and `id="brandLogo"` to the logo;
- wrap the current Poker hero/dashboard in `id="pokerProfile"`;
- remove the existing Poker history card;
- add a sibling `id="cubeProfile"` empty-state section inside the existing profile tab panel;
- add IDs around the two top-level tab labels so JavaScript can rename them;
- replace `История CASH` with one `id="cashHistory"` card containing four accessible tabs and four panels: `allHistory`, `cubeHistory`, `pokerHistory`, and `operationsHistory`;
- keep the existing wallet grid and deposit/withdrawal dialogs unchanged.

The CUBE empty state is exactly:

```html
<section id="cubeProfile" class="profile-section cube-profile-empty" hidden>
  <p class="profile-kicker">ПРОФИЛЬ CUBE</p>
  <h1>Профиль CUBE пока пуст</h1>
  <p class="section-caption">Здесь появятся данные CUBE, когда для профиля будет определено наполнение.</p>
</section>
```

Each history tab uses the page's existing `role="tab"`, `aria-controls`, and `bindTabs` contract.

- [ ] **Step 4: Run the static tests and confirm GREEN**

Run: `pytest tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the markup slice**

```powershell
git add static/profile.html tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py
git commit -m "feat(profile): share cashier between Poker and CUBE"
```

### Task 3: Apply product context and render the unified history

**Files:**
- Modify: `static/profile.js`
- Modify: `cash/wallet.py`
- Modify: `tests/cash/test_cash_client.py`
- Modify: `tests/cash/test_cash_moves_into_the_profile.py`

- [ ] **Step 1: Write failing client and wallet contract tests**

Require the wallet journal to expose `scope`, then add static assertions for the URL context and the three data sources:

```python
def test_wallet_journal_exposes_scope_for_operation_classification():
    source = Path("cash/wallet.py").read_text(encoding="utf-8")
    assert "cash_transactions.c.scope" in source


def test_profile_context_and_history_use_shared_sources():
    assert "new URLSearchParams(location.search).get('app')" in PROFILE_JS
    assert "'/api/cube/history?limit=20'" in PROFILE_JS
    assert "'/api/profile/hands?limit=20&asset=CASH_USDT'" in PROFILE_JS
    assert "wallet.journal" in PROFILE_JS
    assert "scope.startsWith('withdrawal-')" in PROFILE_JS
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest tests/cash/test_cash_client.py tests/cash/test_cash_moves_into_the_profile.py -q`

Expected: failures because the journal lacks `scope` and the profile has no product context/history merger.

- [ ] **Step 3: Expose the journal scope**

Add `cash_transactions.c.scope` to the existing wallet journal query in `cash/wallet.py`. Keep the response shape otherwise unchanged.

- [ ] **Step 4: Add product context and one history renderer**

In `static/profile.js`, derive the context once:

```javascript
const product = new URLSearchParams(location.search).get('app') === 'cube' ? 'cube' : 'poker';
```

Add `applyProduct()` that:

- toggles `cube-context` on `body`;
- swaps `poker♠` and `cube⬢` in `brandLogo`;
- points the logo to the opposite context;
- points `backToProduct` to `/` or `/cube`;
- updates the page title and top-level tab labels;
- shows `pokerProfile` only for Poker and `cubeProfile` only for CUBE.

Change `renderCashWallet` so the same elements show `${available_units} CASH` first in Poker and `${available_usdt} USDT` first in CUBE, with the equivalent in `<small>`.

Normalize all history sources into `{category, title, detail, amountMicros, createdAt}` rows:

- cash Poker hands: `category: 'poker'`, amount from the viewer's `net_micros`;
- CUBE rounds: `category: 'cube'`, amount from `net_micros`;
- wallet journal: keep only `kind === 'deposit'` or `scope.startsWith('withdrawal-') && kind === 'payout'`, then use `category: 'operation'`.

Deduplicate operation rows by transaction ID, sort all rows newest-first, and render:

```javascript
fill('allHistory', rows.map(cashActivityRow), 'Операций пока нет.');
fill('cubeHistory', rows.filter(row => row.category === 'cube').map(cashActivityRow), 'Игр в CUBE пока нет.');
fill('pokerHistory', rows.filter(row => row.category === 'poker').map(cashActivityRow), 'Раздач в POKER пока нет.');
fill('operationsHistory', rows.filter(row => row.category === 'operation').map(cashActivityRow), 'Пополнений и выводов пока нет.');
```

Format the primary amount as CASH in Poker context and USDT in CUBE context. Use the same row data in both contexts so `Операции` never changes when the logo is switched.

Remove the obsolete PLAY history/journal loads and renderers from the profile. `openCashier()` fetches wallet, cash Poker hands, and CUBE history in parallel, mounts the existing cashier, and renders the four lists.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run: `pytest tests/cash/test_cash_client.py tests/cash/test_cash_moves_into_the_profile.py tests/test_profile_page.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the behavior slice**

```powershell
git add static/profile.js cash/wallet.py tests/cash/test_cash_client.py tests/cash/test_cash_moves_into_the_profile.py
git commit -m "feat(profile): add product-aware shared history"
```

### Task 4: Reuse the CASH layout with CUBE colors and wire entry links

**Files:**
- Modify: `static/profile.css`
- Modify: `static/cash-ui.css`
- Modify: `static/lobby.html`
- Modify: `static/lobby.js`
- Modify: `static/cube.html`
- Modify: `static/cube.css`
- Modify: `static/cube.js`
- Modify: `tests/test_profile_page.py`
- Modify: `tests/cash/test_cash_moves_into_the_profile.py`

- [ ] **Step 1: Write failing link/theme tests**

Add assertions that Poker links specify `app=poker`, CUBE links specify `app=cube`, and the CUBE theme uses existing palette values:

```python
def test_product_entries_open_the_matching_profile_context():
    lobby = Path("static/lobby.html").read_text(encoding="utf-8")
    cube = Path("static/cube.html").read_text(encoding="utf-8")
    cube_js = Path("static/cube.js").read_text(encoding="utf-8")
    assert '/static/profile.html?app=poker' in lobby
    assert '/static/profile.html?app=cube' in cube
    assert '/static/profile.html?app=cube#cash' in cube_js


def test_cube_context_reuses_cashier_layout_with_cube_tokens():
    assert ".profile-page.cube-context" in CSS
    assert "--accent:#c8ff31" in CSS.replace(" ", "")
    assert ".cube-profile-empty{" in CSS
```

- [ ] **Step 2: Run static tests and confirm RED**

Run: `pytest tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py -q`

Expected: failures for missing product links and CUBE theme selectors.

- [ ] **Step 3: Add the CUBE token override without a second cashier stylesheet**

In `static/profile.css`, add one scoped token block:

```css
.profile-page.cube-context{
  --ink:#f5f7f7;--muted:#81878d;--line:rgba(255,255,255,.09);
  --panel:#111315;--accent:#c8ff31;--mint:#56f08c;--danger:#ff778f;
  background:#08090a;
}
```

Add scoped CUBE surface/focus rules and `.cube-profile-empty` spacing. Reuse `.cash-wallet-grid`, `.cash-actions`, `.profile-section`, `.history-tabs`, and `.history-row`; do not duplicate their layout declarations. In `static/cash-ui.css`, replace any Poker-only literal active colors that block token inheritance with `var(--accent)`/`color-mix` equivalents.

- [ ] **Step 4: Wire context-preserving entry links**

- Poker lobby wallet/profile links use `/static/profile.html?app=poker#cash` and `/static/profile.html?app=poker`.
- CUBE header gets the same accessible profile icon linked to `/static/profile.html?app=cube`.
- CUBE insufficient-balance and balance-button redirects use `/static/profile.html?app=cube#cash`.
- Cache-buster values remain identical across `index.html`, `lobby.html`, and `profile.html`.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run: `pytest tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py tests/cash/test_cash_client.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the presentation and navigation slice**

```powershell
git add static/profile.css static/cash-ui.css static/lobby.html static/lobby.js static/cube.html static/cube.css static/cube.js tests/test_profile_page.py tests/cash/test_cash_moves_into_the_profile.py
git commit -m "feat(profile): theme cashier for CUBE"
```

### Task 5: Full verification and browser QA

**Files:**
- Verify only; modify files only for defects found by the checks.

- [ ] **Step 1: Run all profile/CASH/CUBE tests**

Run: `pytest tests/test_profile_page.py tests/cash -q`

Expected: zero failures; environment-gated PostgreSQL tests may be skipped.

- [ ] **Step 2: Run the complete suite**

Run: `pytest -q`

Expected: zero failures.

- [ ] **Step 3: Inspect both contexts in the browser**

Start the local app using the repository's documented development command. Check:

- `/static/profile.html?app=poker#cash` at desktop and 390 px width;
- `/static/profile.html?app=cube#cash` at desktop and 390 px width;
- logo switching, back links, cashier/profile tabs, denomination order, four history tabs, and dialog opening;
- Poker profile contains no history card;
- CUBE profile contains only its empty state;
- the `Операции` rows are identical in both contexts.

- [ ] **Step 4: Review the final diff**

Run: `git diff --check HEAD~4..HEAD` and `git status --short`.

Expected: no whitespace errors; only task files plus the user's pre-existing changes are present.

- [ ] **Step 5: Commit any QA-only correction**

If Step 3 required a correction, add only the affected task files and commit with `fix(profile): polish shared Poker and CUBE cashier`. If no correction was required, do not create an empty commit.
