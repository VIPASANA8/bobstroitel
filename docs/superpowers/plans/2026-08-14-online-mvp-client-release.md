# Poker8 Online Client and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the mobile Lobby → Table → Result → Next Hand product, table chat, profile/history, tenant co-branding, second-bot readiness, and the final operational release gate.

**Architecture:** Keep the current cinematic table DOM and renderer, place an online transport adapter beneath it, and add focused lobby/profile clients. All user actions call authenticated APIs or the table WebSocket; tenant branding comes from server configuration, and browser code never receives bot secrets or private table snapshots.

**Tech Stack:** Vanilla HTML/CSS/JavaScript, existing Poker8 visual assets, FastAPI routers, PostgreSQL, Playwright, pytest, WebSocket load probe.

---

### Task 1: Add table lifecycle HTTP endpoints

**Files:**
- Create: `app/routers/tables.py`
- Modify: `app/online.py`
- Test: `tests/online/test_table_api.py`

- [ ] **Step 1: Write failing lifecycle API tests**

Create `tests/online/test_table_api.py`:

```python
def test_spectator_can_ready_cancel_and_remain_spectator(logged_in_client, table_id):
    ready = logged_in_client.post(
        f"/api/tables/{table_id}/ready",
        json={"seat_no": 2, "buy_in_units": 4_000, "request_id": "ready-1"},
    )
    assert ready.status_code == 200
    assert ready.json()["queue_state"] == "waiting"
    cancelled = logged_in_client.post(f"/api/tables/{table_id}/ready/cancel")
    assert cancelled.json()["viewer_state"] == "spectator"


def test_add_on_is_rejected_during_active_hand(seated_client, active_table_id):
    response = seated_client.post(
        f"/api/tables/{active_table_id}/add-on",
        json={"amount_units": 1_000, "request_id": "addon-1"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "between_hands_only"
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_table_api.py -q
```

Expected: table routes return 404.

- [ ] **Step 3: Implement authenticated table endpoints**

Add:

```text
GET  /api/tables/{table_id}
POST /api/tables/{table_id}/ready
POST /api/tables/{table_id}/ready/cancel
POST /api/tables/{table_id}/observe
POST /api/tables/{table_id}/leave
POST /api/tables/{table_id}/add-on
POST /api/tables/{table_id}/reconnect
```

`GET` returns a viewer-specific snapshot and never the private runtime JSON. State-changing routes call `SeatingService`, enforce request IDs for financial effects, and return stable error objects such as `{ "code": "between_hands_only", "message": "Add-on is available between hands" }`.

- [ ] **Step 4: Run API tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_table_api.py tests/online/test_seating.py -q
```

Expected: all tests pass.

```powershell
git add app/routers/tables.py app/online.py tests/online/test_table_api.py
git commit -m "feat: expose online table lifecycle"
```

### Task 2: Add table chat with bounded history and rate limits

**Files:**
- Modify: `online/schema.py`
- Create: `migrations/versions/20260814_0003_chat_and_branding.py`
- Create: `online/chat.py`
- Create: `app/routers/chat.py`
- Test: `tests/online/test_chat.py`

- [ ] **Step 1: Write failing chat tests**

Create `tests/online/test_chat.py`:

```python
@pytest.mark.anyio
async def test_chat_returns_only_last_fifty_messages(chat, table_id, user_id):
    for index in range(55):
        await chat.post(table_id, user_id, f"message {index}", now=index)
    rows = await chat.recent(table_id)
    assert len(rows) == 50
    assert rows[0].text == "message 5"


@pytest.mark.anyio
async def test_chat_rejects_sixth_message_inside_ten_seconds(chat, table_id, user_id):
    for index in range(5):
        await chat.post(table_id, user_id, f"ok {index}", now=100 + index)
    with pytest.raises(ChatRateLimited):
        await chat.post(table_id, user_id, "too fast", now=109)
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_chat.py -q
```

Expected: import failure for `online.chat`.

- [ ] **Step 3: Add chat and tenant-branding storage**

Migration `20260814_0003` adds:

```text
chat_messages(id PK, table_id FK, user_id FK, text VARCHAR(300), created_at)
tenants.branding_json JSON NOT NULL DEFAULT '{}'
tenants.support_url VARCHAR(500) NULL
```

Index chat by `(table_id, created_at DESC)`.

- [ ] **Step 4: Implement chat service and routes**

`ChatService.post` strips surrounding whitespace, rejects empty text, control characters, and text longer than 300 Unicode characters, and allows five messages per user/table in a rolling ten-second window. Persist plain text, never rendered HTML.

Add:

```text
GET  /api/tables/{table_id}/chat?limit=50
POST /api/tables/{table_id}/chat { text }
```

Posting publishes a `chat_message` table event after commit. Local mute is a client-only preference and does not alter server history.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_chat.py -q
```

Expected: all tests pass.

```powershell
git add online/schema.py migrations/versions/20260814_0003_chat_and_branding.py online/chat.py app/routers/chat.py tests/online/test_chat.py
git commit -m "feat: add bounded table chat"
```

### Task 3: Build Telegram boot and the six-card lobby

**Files:**
- Create: `static/lobby.html`
- Create: `static/lobby.js`
- Create: `static/network.css`
- Create: `static/auth-client.js`
- Create: `app/routers/config.py`
- Modify: `app/online.py`
- Test: `tests/online/test_lobby_page.py`

- [ ] **Step 1: Write failing static-shell and config tests**

Create `tests/online/test_lobby_page.py`:

```python
def test_root_serves_lobby_with_six_card_container(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="tableGrid"' in response.text
    assert 'id="quickPlay"' in response.text


def test_public_config_contains_branding_but_no_bot_token(client):
    payload = client.get("/api/config").json()
    assert payload["tenant"]["slug"] == "poker8"
    assert payload["network_brand"] == "Poker8"
    assert "token" not in str(payload).lower()
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_lobby_page.py -q
```

Expected: root is missing or still serves the legacy table.

- [ ] **Step 3: Implement the authentication bootstrap**

`static/auth-client.js` exports `ensureSession()`:

1. call `/api/profile` and return if the cookie session is valid;
2. when `window.Telegram.WebApp.initData` exists, POST it to `/api/auth/telegram`; the server resolves the tenant from the configured host;
3. in development only, render the predefined profile selector returned by `/api/config` and POST `/api/auth/dev/{id}`;
4. in production with no valid initData, show a Telegram-only error and do not create a guest account.

- [ ] **Step 4: Build the mobile-first lobby**

`lobby.html` contains:

- co-branded header and `Powered by Poker8`;
- wallet summary and `Return to table` slot;
- prominent Quick Play button;
- `tableGrid` for exactly six cards per page;
- profile link;
- buy-in modal with 40–100 BB bounds.

`lobby.js` loads `/api/lobby/tables?page=1&per_page=6`, labels every card `Blinds X/Y` and `Entry 40–100`, and displays one bot-inclusive `occupied_count / 6` value without an `AI`, human/system split, or difficulty label. Quick Play opens the chosen table as a spectator and starts the buy-in/Ready flow; only a confirmed request joins the FIFO queue.

The root route serves `lobby.html`; `/table` continues to serve the existing `static/index.html`.

- [ ] **Step 5: Run tests and manually verify 360×800**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_lobby_page.py -q
.\.venv\Scripts\uvicorn.exe app.online:app --reload
```

Expected: lobby fits at 360×800 without horizontal scrolling, six cards paginate correctly, and no bot token appears in browser responses.

- [ ] **Step 6: Commit**

```powershell
git add static/lobby.html static/lobby.js static/network.css static/auth-client.js app/routers/config.py app/online.py tests/online/test_lobby_page.py
git commit -m "feat: add Poker8 network lobby"
```

### Task 4: Put the existing cinematic table behind an online transport

**Files:**
- Create: `static/online-transport.js`
- Modify: `static/index.html`
- Modify: `static/app.js`
- Test: `tests/online/test_table_transport_contract.py`

- [ ] **Step 1: Write a failing source-contract test**

Create `tests/online/test_table_transport_contract.py`:

```python
from pathlib import Path


def test_table_uses_online_transport_not_legacy_game_fetches():
    html = Path("static/index.html").read_text(encoding="utf-8")
    script = Path("static/app.js").read_text(encoding="utf-8")
    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "online-transport.js" in html
    assert "new WebSocket" in transport
    assert "Poker8Transport.sendAction" in script
    assert 'fetch(`/api/game/${game.hand_id}/action`' not in script
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_table_transport_contract.py -q
```

Expected: transport file is missing.

- [ ] **Step 3: Implement the transport API**

`static/online-transport.js` exposes this exact browser contract:

```javascript
window.Poker8Transport = {
  connect(tableId, handlers),
  disconnect(),
  sendAction(action, amountUnits),
  resync(),
  ready(seatNo, buyInUnits),
  cancelReady(),
  observe(),
  leave(),
  addOn(amountUnits),
  loadChat(),
  sendChat(text)
};
```

It generates one `crypto.randomUUID()` command ID per user action, tracks the last revision, reconnects with exponential delays capped at five seconds, and asks for a full resync after reconnect. It never retries an action with a new command ID.

- [ ] **Step 4: Adapt only the networking seams in `static/app.js`**

Keep the existing render functions and visual layers. Replace legacy implementations of table load, new hand, bot-step polling, player action, and timeout submission with `Poker8Transport`. Map the online viewer-specific snapshot into the existing `game` and `tableData` shapes. Remove client-driven bot stepping and client authority over action timeout.

Render server phases as follows:

```text
waiting   → clean room / ready state
active    → current cinematic table and HUD
result    → cards, chips, and result remain visible
countdown → cards and chips hidden; centered New Hand 3..2..1
paused    → readable paused banner, action buttons disabled
```

- [ ] **Step 5: Run source and regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_table_transport_contract.py tests/test_v101_regressions.py -q
node --check static/online-transport.js
node --check static/app.js
```

Expected: all tests and syntax checks pass.

- [ ] **Step 6: Commit**

```powershell
git add static/online-transport.js static/index.html static/app.js tests/online/test_table_transport_contract.py
git commit -m "feat: connect cinematic table to realtime state"
```

### Task 5: Add ready, queue, turn, reconnect, and chat UI states

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`
- Modify: `static/style.css`
- Modify: `static/mobile.css`
- Test: `tests/online/test_table_ui_states.py`

- [ ] **Step 1: Write failing UI-state contract tests**

Create `tests/online/test_table_ui_states.py`:

```python
from pathlib import Path


def test_table_contains_online_state_surfaces():
    html = Path("static/index.html").read_text(encoding="utf-8")
    for element_id in ("readyPanel", "queueStatus", "connectionStatus", "chatPanel", "newHandCountdown"):
        assert f'id="{element_id}"' in html


def test_system_player_has_no_large_ai_badge():
    script = Path("static/app.js").read_text(encoding="utf-8")
    assert 'seatAvatar.textContent = "AI"' not in script
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_table_ui_states.py -q
```

Expected: required surfaces are absent.

- [ ] **Step 3: Implement online lifecycle UI**

Add compact, mobile-safe states:

- spectator seat choice and buy-in;
- a 10-second buy-in/Ready prompt; expiry leaves the user a spectator and reserves nothing;
- one-tap Ready and second-tap cancellation before seating;
- FIFO queue position;
- connection/reconnecting indicator;
- active-player glow on avatar and nameplate only, without rectangular seat backlight;
- 30-second turn ring and readable action information;
- Observe and Leave controls applied at a boundary;
- four-second result display and three-second centered New Hand countdown;
- no pocket or board cards in waiting/countdown phase;
- system-player level visuals without a large `AI` label;
- detailed seat profile label `System player`.

The chat drawer loads the last 50 messages, escapes text with `textContent`, sends on Enter, and stores locally muted user IDs in `localStorage`.

- [ ] **Step 4: Run tests and visual checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_table_ui_states.py tests/test_v101_regressions.py -q
node --check static/app.js
```

Expected: tests pass; at 360×800, timer/info panels do not overlap the avatar or HUD.

- [ ] **Step 5: Commit**

```powershell
git add static/index.html static/app.js static/style.css static/mobile.css tests/online/test_table_ui_states.py
git commit -m "feat: render online table lifecycle"
```

### Task 6: Build the global profile, wallet journal, and last-20-hand screen

**Files:**
- Create: `static/profile.html`
- Create: `static/profile.js`
- Modify: `static/network.css`
- Modify: `app/routers/profiles.py`
- Test: `tests/online/test_profile_api.py`
- Test: `tests/online/test_profile_page.py`

- [ ] **Step 1: Write failing profile API tests**

Create tests that assert:

```python
def test_profile_level_thresholds(logged_in_client, set_wins):
    for wins, expected in ((0, 0), (9, 0), (10, 1), (50, 2), (100, 3), (200, 4), (500, 5)):
        set_wins(wins)
        assert logged_in_client.get("/api/profile").json()["level"] == expected


def test_self_profile_returns_telegram_id_as_separate_field(logged_in_client):
    payload = logged_in_client.get("/api/profile").json()
    assert payload["telegram_user_id"] == 101
    assert "telegram_user_id" not in logged_in_client.get("/api/lobby/tables").text


def test_hand_history_hides_mucked_opponent_cards(logged_in_client, completed_hidden_hand):
    rows = logged_in_client.get("/api/profile/hands?limit=20").json()["hands"]
    opponent = rows[0]["players"][completed_hidden_hand.opponent_id]
    assert opponent["hole_cards"] is None
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_profile_api.py -q
```

Expected: history route or level data is missing.

- [ ] **Step 3: Complete profile endpoints**

Add `GET /api/profile/hands?limit=20` and ensure the authenticated user's own `/api/profile` returns Telegram display name, Telegram user ID as a separate field, level, avatar asset key, wins, hands, available play units, active-table stack units, and active table ID. Lobby, table, chat, history, journal, and other-user payloads never expose Telegram IDs.

- [ ] **Step 4: Build the profile page**

`profile.html` and `profile.js` render:

- centered display name and level avatar;
- Telegram ID on its own copyable support row;
- exact level progress to the next threshold;
- wins and hands;
- available wallet and active table stack as separate values;
- journal entries;
- last 20 hands with positions, actions, pot, result, own cards, and shown opponent cards only;
- Return to table button when seated.

- [ ] **Step 5: Run API and page tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_profile_api.py tests/online/test_profile_page.py -q
node --check static/profile.js
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add static/profile.html static/profile.js static/network.css app/routers/profiles.py tests/online/test_profile_api.py tests/online/test_profile_page.py
git commit -m "feat: add global Poker8 profile"
```

### Task 7: Prove tenant co-branding and second-bot readiness

**Files:**
- Modify: `online/config.py`
- Modify: `online/auth.py`
- Modify: `app/routers/config.py`
- Create: `tests/online/test_two_tenants.py`
- Create: `docs/runbooks/add-partner-bot.md`

- [ ] **Step 1: Write a failing two-tenant test**

Create `tests/online/test_two_tenants.py`:

```python
def test_same_telegram_user_keeps_account_wallet_and_first_partner(two_tenant_client, signed_init_data):
    # Fixtures use base URLs https://brand-a.test and https://brand-b.test.
    client_a, client_b = two_tenant_client
    user_a = client_a.post("/api/auth/telegram", json={"init_data": signed_init_data("token-a", 900)}).json()
    client_a.post("/api/profile/play-top-up", json={"amount_units": 100_000, "request_id": "grant-900"})
    user_b = client_b.post("/api/auth/telegram", json={"init_data": signed_init_data("token-b", 900)}).json()
    profile_b = client_b.get("/api/profile").json()
    assert user_a["user_id"] == user_b["user_id"]
    assert user_b["acquisition_tenant_slug"] == "brand-a"
    assert profile_b["available_units"] == 200_000


def test_client_cannot_spoof_tenant(two_tenant_client, signed_init_data):
    client_a, _ = two_tenant_client
    response = client_a.post(
        "/api/auth/telegram?tenant=brand-b",
        headers={"X-Tenant": "brand-b"},
        json={"init_data": signed_init_data("token-b", 901), "tenant": "brand-b"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_two_tenants.py -q
```

Expected: only the default tenant is resolvable.

- [ ] **Step 3: Add multi-tenant secret references**

Allow `POKER8_TENANTS_JSON` to declare tenant slug, allowed hostnames, display name, bot ID, environment secret name, support URL, and branding variables. Resolve the tenant only from an exact allowed-hostname match, then resolve the actual bot token from the named environment variable; never return either secret through `/api/config`.

The browser receives only network brand, tenant brand, support URL, and approved CSS variables. Render `Powered by Poker8` in lobby, table menu, and profile.

- [ ] **Step 4: Document second-bot attachment**

`docs/runbooks/add-partner-bot.md` contains exact steps to create the tenant row, define its environment token, set its Mini App URL, run the two-tenant smoke test, rotate a token, disable the tenant, and confirm no duplicate user or wallet was created.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_two_tenants.py tests/online/test_auth.py -q
```

Expected: all tests pass.

```powershell
git add online/config.py online/auth.py app/routers/config.py tests/online/test_two_tenants.py docs/runbooks/add-partner-bot.md
git commit -m "feat: prepare co-branded partner gateways"
```

### Task 8: Add operational visibility and privacy-safe event logs

**Files:**
- Create: `online/logging.py`
- Create: `online/health.py`
- Modify: `online/events.py`
- Modify: `app/routers/health.py`
- Create: `tests/online/test_observability.py`
- Create: `docs/runbooks/online-mvp.md`

- [ ] **Step 1: Write failing log-redaction and readiness tests**

Create tests proving that structured events contain tenant, table, hand, command, and internal user IDs but never Telegram ID, bot token, hole cards, cookie token, or private snapshot JSON. Add a readiness test that returns 503 when the database query fails or a runtime is paused for ledger mismatch.

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_observability.py -q
```

Expected: logging module or required readiness details are missing.

- [ ] **Step 3: Implement JSON logging and health details**

Use stdlib `logging` with a JSON formatter. Emit event name, UTC timestamp, tenant ID, table ID, hand ID, command ID, internal user ID, duration, and result code. Install a filter that removes keys matching `telegram_user_id`, `bot_token`, `cookie`, `hole_cards`, `private_state_json`, and `deck_cards`.

`/health/live` reports process liveness only. `/health/ready` checks database connectivity, Alembic revision, catalogue seed, runtime restore completion, and absence of a global ledger-integrity failure.

- [ ] **Step 4: Write the operational runbook**

`docs/runbooks/online-mvp.md` includes exact Windows and Docker Compose commands for install, migrate, run, stop, backup with `pg_dump`, restore into a new database, inspect paused tables, revoke sessions, and execute all release gates.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_observability.py -q
```

Expected: all tests pass.

```powershell
git add online/logging.py online/health.py online/events.py app/routers/health.py tests/online/test_observability.py docs/runbooks/online-mvp.md
git commit -m "feat: add online operations visibility"
```

### Task 9: Add mobile E2E, restart, and target-load gates

**Files:**
- Modify: `requirements.txt`
- Create: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_mobile_online_flow.py`
- Create: `tests/load/online_mvp_load.py`
- Create: `tests/load/seed_load_tables.py`
- Create: `tests/online/test_no_cash_runtime.py`

- [ ] **Step 1: Add browser/load dependencies**

Append:

```text
playwright>=1.54,<2
pytest-playwright>=0.7,<1
websockets>=15,<16
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

- [ ] **Step 2: Write the full mobile acceptance test**

At a 360×800 viewport, `test_mobile_online_flow.py` must:

1. authenticate a development profile;
2. see six lobby cards and bot-inclusive occupancy;
3. use Quick Play and confirm a 40 BB buy-in;
4. enter the chosen available table as a spectator, submit Ready, observe `waiting`, process the deterministic boundary, and observe `seated`;
5. receive private cards visible only in that browser context;
6. perform one legal action;
7. open/send/receive chat;
8. disconnect and reconnect to the same seat;
9. finish a deterministic test hand;
10. see result for four seconds;
11. see a clean three-second countdown;
12. see new private cards at second seven;
13. return to lobby and use Return to table;
14. open profile and see the hand plus ledger journal.

Use a test-only deterministic table fixture injected through the application factory, never a production endpoint.

- [ ] **Step 3: Write the target-load probe**

`tests/load/seed_load_tables.py` uses the online services directly to create test-only users, session cookies, and tables in the configured test database; it refuses to run unless `POKER8_ENV=test`. `tests/load/online_mvp_load.py` accepts `--base-url`, `--connections`, `--tables`, `--duration`, and the generated session manifest, distributes 100 WebSockets across 20 tables, sends pings/resyncs, and reports connect failures, unexpected disconnects, p50/p95 event latency, stale revisions, and duplicate command results. Exit nonzero if connection failure exceeds 1%, any duplicate effect occurs, or p95 server event latency exceeds 500 ms on the agreed local reference machine. Do not add a production seed endpoint.

- [ ] **Step 4: Add a no-cash runtime guard**

`tests/online/test_no_cash_runtime.py` introspects `app.routes`, SQLAlchemy metadata table names, transaction-kind constraints, and `PlayLedger.ASSET == "PLAY"`. Assert there is no deposit, withdrawal, KYC, blockchain, cash-wallet, conversion, or payout surface. Do not scan arbitrary source text.

- [ ] **Step 5: Run release tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/e2e/test_mobile_online_flow.py -m e2e -q
.\.venv\Scripts\python.exe tests/load/online_mvp_load.py --base-url http://127.0.0.1:8000 --connections 100 --tables 20 --duration 120
.\.venv\Scripts\python.exe -m pytest tests/online/test_no_cash_runtime.py -q
```

Expected: browser flow passes, load probe exits zero, and no cash runtime is detected.

- [ ] **Step 6: Commit**

```powershell
git add requirements.txt tests/e2e tests/load tests/online/test_no_cash_runtime.py
git commit -m "test: gate online MVP release"
```

### Task 10: Switch production entrypoint and run the complete release gate

**Files:**
- Move: `app/main.py` to `app/legacy.py`
- Create: `app/main.py`
- Modify: `tests/test_v091_spectator_infinite.py`
- Modify: `tests/test_v10_humanized_bot_steps.py`
- Modify: `README.md`

- [ ] **Step 1: Preserve legacy test imports**

Move the current local trainer application to `app/legacy.py`. Update only legacy tests that monkeypatch `app.main` globals to import `app.legacy as main`. Do not import or instantiate `TrainingStore` from the new production entrypoint.

- [ ] **Step 2: Create the thin production entrypoint**

Create `app/main.py`:

```python
import os

from app.online import create_app
from online.config import Settings


app = create_app(Settings.from_mapping(os.environ))
```

- [ ] **Step 3: Update README startup and product boundaries**

Document PostgreSQL startup, Alembic migration, development profiles, Telegram production auth, lobby/table/profile URLs, test commands, and the explicit play-money-only boundary. Link the approved MVP specification and Product Vision.

- [ ] **Step 4: Run the complete gate**

Run:

```powershell
docker compose up -d postgres postgres_test
$env:POKER8_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5432/poker8'
$env:POKER8_TEST_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5433/poker8_test'
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -m postgres -q
.\.venv\Scripts\python.exe -m pytest tests/e2e -m e2e -q
.\.venv\Scripts\python.exe tests/load/online_mvp_load.py --base-url http://127.0.0.1:8000 --connections 100 --tables 20 --duration 120
node --check static/app.js
node --check static/online-transport.js
node --check static/lobby.js
node --check static/profile.js
git diff --check
```

Expected: every command exits zero. Confirm `git status --short` does not stage or modify `data/poker_trainer.sqlite3`, its WAL/SHM files, or `.superpowers/`.

- [ ] **Step 5: Commit**

```powershell
git add app/main.py app/legacy.py tests/test_v091_spectator_infinite.py tests/test_v10_humanized_bot_steps.py README.md
git commit -m "feat: make online network the production app"
```
