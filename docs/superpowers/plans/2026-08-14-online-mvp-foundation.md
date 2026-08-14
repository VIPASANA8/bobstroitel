# Poker8 Online MVP Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a green baseline, PostgreSQL schema, tenant-aware Telegram identity, global play ledger, and six-table lobby data without changing the current table UI.

**Architecture:** Add a new `online` package beside the legacy SQLite store. Use SQLAlchemy Core with async sessions and Alembic migrations; represent all play values as integer hundredths. Expose the new foundation through `app/online.py` while leaving `app/main.py` runnable until the client cutover plan.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, PostgreSQL 16, psycopg 3, aiosqlite for isolated unit tests, pytest, Starlette TestClient.

---

### Task 1: Restore a green 6-max baseline

**Files:**
- Modify: `tests/test_table_store.py`

- [ ] **Step 1: Correct the obsolete bot-only fixture**

Replace `test_six_bot_seats_can_be_activated` with this exact 6-max test:

```python
def test_six_bot_seats_can_be_activated_when_human_leaves(tmp_path):
    store = TrainingStore(tmp_path / "trainer.sqlite3")
    store.clear_seat(0)

    for seat in range(1, 7):
        store.add_bot(seat, f"Test {seat}", "hard")

    active = [row for row in store.get_table() if row["active"]]
    assert len(active) == 6
    assert all(row["occupant_type"] == "bot" for row in active)
```

- [ ] **Step 2: Run the focused test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_table_store.py -q
```

Expected: `2 passed`.

- [ ] **Step 3: Run the entire legacy suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: `57 passed`.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_table_store.py
git commit -m "test: align bot capacity with six max"
```

### Task 2: Add online dependencies and strict configuration

**Files:**
- Modify: `requirements.txt`
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `online/__init__.py`
- Create: `online/config.py`
- Test: `tests/online/test_config.py`

- [ ] **Step 1: Write failing configuration tests**

Create `tests/online/test_config.py`:

```python
import pytest

from online.config import Settings


def test_production_requires_database_and_bot_token():
    with pytest.raises(ValueError, match="POKER8_DATABASE_URL"):
        Settings.from_mapping({"POKER8_ENV": "production"})


def test_development_accepts_named_profiles_without_bot_token():
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "POKER8_DEV_PROFILES": "101:Марта,202:Илья",
    })
    assert settings.environment == "development"
    assert settings.dev_profiles == {101: "Марта", 202: "Илья"}
    assert settings.default_tenant_slug == "poker8"
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_config.py -q
```

Expected: collection fails because `online.config` does not exist.

- [ ] **Step 3: Pin the online runtime dependencies**

Append to `requirements.txt`:

```text
sqlalchemy[asyncio]>=2.0,<3
alembic>=1.16,<2
psycopg[binary,pool]>=3.2,<4
aiosqlite>=0.21,<1
httpx>=0.28,<1
```

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Expected: installation completes without dependency conflicts.

- [ ] **Step 4: Implement immutable settings parsing**

Create `online/config.py` with this public contract:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    default_tenant_slug: str
    default_bot_token: str | None
    session_cookie_name: str
    session_ttl_seconds: int
    telegram_auth_max_age_seconds: int
    dev_profiles: dict[int, str]

    @classmethod
    def from_mapping(cls, source: Mapping[str, str]) -> "Settings":
        environment = source.get("POKER8_ENV", "development").strip().lower()
        database_url = source.get("POKER8_DATABASE_URL", "").strip()
        bot_token = source.get("POKER8_DEFAULT_BOT_TOKEN", "").strip() or None
        if environment == "production" and not database_url:
            raise ValueError("POKER8_DATABASE_URL is required in production")
        if environment == "production" and not bot_token:
            raise ValueError("POKER8_DEFAULT_BOT_TOKEN is required in production")
        if not database_url:
            database_url = "sqlite+aiosqlite:///./data/poker8_online_dev.sqlite3"

        profiles: dict[int, str] = {}
        for item in filter(None, source.get("POKER8_DEV_PROFILES", "101:Dev Player").split(",")):
            raw_id, name = item.split(":", 1)
            profiles[int(raw_id.strip())] = name.strip()

        return cls(
            environment=environment,
            database_url=database_url,
            default_tenant_slug=source.get("POKER8_DEFAULT_TENANT", "poker8").strip(),
            default_bot_token=bot_token,
            session_cookie_name="poker8_session",
            session_ttl_seconds=7 * 24 * 60 * 60,
            telegram_auth_max_age_seconds=15 * 60,
            dev_profiles=profiles,
        )
```

Create an empty `online/__init__.py`.

- [ ] **Step 5: Add reproducible local PostgreSQL configuration**

Create `.env.example`:

```text
POKER8_ENV=development
POKER8_DATABASE_URL=postgresql+psycopg://poker8:poker8@127.0.0.1:5432/poker8
POKER8_DEFAULT_TENANT=poker8
POKER8_DEFAULT_BOT_TOKEN=
POKER8_DEV_PROFILES=101:Dev Player,202:Second Player
```

Create `compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: poker8
      POSTGRES_USER: poker8
      POSTGRES_PASSWORD: poker8
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U poker8 -d poker8"]
      interval: 2s
      timeout: 2s
      retries: 20
    volumes:
      - poker8_pgdata:/var/lib/postgresql/data

  postgres_test:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: poker8_test
      POSTGRES_USER: poker8
      POSTGRES_PASSWORD: poker8
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U poker8 -d poker8_test"]
      interval: 2s
      timeout: 2s
      retries: 20
    tmpfs:
      - /var/lib/postgresql/data

volumes:
  poker8_pgdata:
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_config.py -q
```

Expected: `2 passed`.

```powershell
git add requirements.txt .env.example compose.yaml online tests/online/test_config.py
git commit -m "build: add online service configuration"
```

### Task 3: Create the PostgreSQL schema and migration boundary

**Files:**
- Create: `online/database.py`
- Create: `online/schema.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/20260814_0001_online_foundation.py`
- Create: `tests/online/conftest.py`
- Create: `tests/online/test_schema.py`
- Modify: `pytest.ini`

- [ ] **Step 1: Write failing schema tests**

Create `tests/online/test_schema.py`:

```python
import asyncio

from sqlalchemy import select

from online.schema import tenants, users


def test_one_telegram_identity_is_global(db_session_factory):
    async def run():
        async with db_session_factory() as session:
            await session.execute(tenants.insert().values(id="t1", slug="poker8", name="Poker8"))
            await session.execute(users.insert().values(
                id="u1", telegram_user_id=777, display_name="One", acquisition_tenant_id="t1"
            ))
            await session.commit()
            rows = (await session.execute(select(users.c.id))).all()
            assert rows == [("u1",)]

    asyncio.run(run())
```

Create `tests/online/conftest.py` with an async SQLite fixture using `StaticPool`, calling `metadata.create_all` before a test and `metadata.drop_all` afterward. The fixture must yield `async_sessionmaker(engine, expire_on_commit=False)`.

- [ ] **Step 2: Verify the schema test fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_schema.py -q
```

Expected: import failure for `online.schema`.

- [ ] **Step 3: Define the async database boundary**

Create `online/database.py`:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def create_database(database_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 4: Define the complete foundation metadata**

Create `online/schema.py` using SQLAlchemy Core. Define these exact tables and constraints:

```text
tenants(id PK, slug UNIQUE, name, status, created_at)
tenant_bots(id PK, tenant_id FK, telegram_bot_id, secret_ref, enabled, created_at)
users(id PK, telegram_user_id BIGINT UNIQUE, display_name, acquisition_tenant_id FK, wins, hands_played, created_at, updated_at)
user_tenant_visits(id PK, user_id FK, tenant_id FK, first_seen_at, last_seen_at, UNIQUE(user_id, tenant_id))
auth_sessions(id PK, user_id FK, tenant_id FK, token_hash UNIQUE, expires_at, revoked_at, created_at)
system_players(id PK, name, difficulty CHECK easy/normal/hard/maximum, wins, hands_played, active, created_at)
play_accounts(id PK, owner_kind CHECK user/system/table, owner_id, account_kind CHECK wallet/escrow/faucet, balance_units BIGINT, created_at, UNIQUE(owner_kind, owner_id, account_kind), CHECK(account_kind = faucet OR balance_units >= 0))
play_transactions(id PK, kind CHECK faucet_grant/buy_in/add_on/settlement/return, idempotency_key UNIQUE, reference_type, reference_id, status CHECK pending/posted, created_at, posted_at)
play_entries(id PK, transaction_id FK, account_id FK, amount_units BIGINT CHECK <> 0, created_at)
poker_tables(id PK, tenant_id nullable FK, scope CHECK network/tenant, name, small_blind_units, big_blind_units, min_buy_in_bb, max_buy_in_bb, max_seats CHECK = 6, status, button_seat, created_at, updated_at)
table_seats(id PK, table_id FK, seat_no CHECK 0..5, occupant_kind CHECK empty/user/system, user_id nullable FK, system_player_id nullable FK, escrow_account_id nullable FK, stack_units BIGINT CHECK >= 0, state CHECK empty/seated/held/leaving, disconnected_at, hold_until, updated_at, UNIQUE(table_id, seat_no))
seat_queue(id PK, table_id FK, user_id FK, requested_buy_in_units, state CHECK waiting/cancelled/seated/expired, position_seq BIGINT, created_at, expires_at, UNIQUE(table_id, user_id))
```

Use timezone-aware UTC timestamps with server defaults. Add partial unique indexes preventing one `user_id` or one `system_player_id` from appearing in more than one `table_seats` row whose state is `seated`, `held`, or `leaving`.

- [ ] **Step 5: Configure Alembic and create the initial migration**

Configure `migrations/env.py` to import `online.schema.metadata` and read `POKER8_DATABASE_URL`. The initial migration must create the tables and indexes above and install a PostgreSQL trigger that rejects changing a play transaction to `posted` unless the sum of its entries is zero.

Register markers in `pytest.ini`:

```ini
[pytest]
pythonpath = .
addopts = -m "not postgres and not e2e"
markers =
    postgres: requires the PostgreSQL service from compose.yaml
    e2e: browser acceptance test
```

- [ ] **Step 6: Run unit and PostgreSQL migration checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_schema.py -q
docker compose up -d postgres
$env:POKER8_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5432/poker8'
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe downgrade base
.\.venv\Scripts\alembic.exe upgrade head
```

Expected: schema test passes and all three Alembic commands exit zero.

- [ ] **Step 7: Commit**

```powershell
git add online/database.py online/schema.py alembic.ini migrations tests/online/conftest.py tests/online/test_schema.py pytest.ini
git commit -m "feat: add online PostgreSQL schema"
```

### Task 4: Implement tenant-aware Telegram authentication

**Files:**
- Create: `online/auth.py`
- Create: `app/dependencies.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/auth.py`
- Test: `tests/online/test_auth.py`

- [ ] **Step 1: Write failing initData and attribution tests**

Create `tests/online/test_auth.py` with a local signing helper and these cases:

```python
@pytest.mark.anyio
async def test_valid_init_data_creates_one_global_user(auth_service, signed_init_data):
    first = await auth_service.authenticate("poker8", signed_init_data(user_id=55, name="Марта"))
    second = await auth_service.authenticate("partner-b", signed_init_data(user_id=55, name="Марта", token="token-b"))
    assert first.user_id == second.user_id
    assert second.acquisition_tenant_slug == "poker8"
    assert second.access_tenant_slug == "partner-b"


@pytest.mark.anyio
async def test_wrong_bot_signature_is_rejected(auth_service, signed_init_data):
    with pytest.raises(AuthenticationError, match="signature"):
        await auth_service.authenticate("partner-b", signed_init_data(user_id=55, name="Марта"))


@pytest.mark.anyio
async def test_expired_init_data_is_rejected(auth_service, signed_init_data):
    with pytest.raises(AuthenticationError, match="expired"):
        await auth_service.authenticate("poker8", signed_init_data(user_id=55, auth_date=1))
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_auth.py -q
```

Expected: import failure for `online.auth`.

- [ ] **Step 3: Implement Telegram verification**

In `online/auth.py`, implement:

```python
def verify_init_data(init_data: str, bot_token: str, now: int, max_age_seconds: int) -> dict:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    supplied_hash = pairs.pop("hash", "")
    check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hash):
        raise AuthenticationError("invalid Telegram signature")
    auth_date = int(pairs["auth_date"])
    if now - auth_date > max_age_seconds or auth_date > now + 30:
        raise AuthenticationError("Telegram initData expired")
    return json.loads(pairs["user"])
```

Add `AuthService.authenticate(tenant_slug, init_data)` that resolves the tenant's secret, upserts the global user by `telegram_user_id`, inserts or updates `user_tenant_visits`, preserves the existing acquisition tenant, creates a 32-byte opaque session token, stores only its SHA-256 hash, and returns the raw token once.

- [ ] **Step 4: Implement production and development login routes**

`POST /api/auth/telegram` accepts `{ "init_data": "query_id=AAE&user=%7B%22id%22%3A55%7D&auth_date=1770000000&hash=hex" }`, resolves the tenant from the server-configured request-host binding (the single default tenant in MVP development), sets the opaque token in an HttpOnly, SameSite=Lax cookie, and returns the public session user. Reject a host that is not mapped; never accept tenant identity from request JSON, query parameters, or client headers.

`POST /api/auth/dev/{telegram_user_id}` exists only when `settings.environment == "development"` and only accepts IDs declared in `POKER8_DEV_PROFILES`.

`POST /api/auth/logout` revokes the session and clears the cookie.

`app/dependencies.py` must hash the cookie token, reject expired/revoked sessions, and return `AuthenticatedUser(user_id, tenant_id, telegram_user_id, display_name)`.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_auth.py -q
```

Expected: all auth tests pass.

```powershell
git add online/auth.py app/dependencies.py app/routers tests/online/test_auth.py
git commit -m "feat: authenticate global Telegram users"
```

### Task 5: Implement the balanced play ledger

**Files:**
- Create: `online/amounts.py`
- Create: `online/ledger.py`
- Test: `tests/online/test_ledger.py`

- [ ] **Step 1: Write failing conversion and ledger tests**

Create `tests/online/test_ledger.py`:

```python
from decimal import Decimal

import pytest

from online.amounts import from_units, to_units
from online.ledger import InsufficientPlayBalance


def test_play_amounts_use_integer_hundredths():
    assert to_units(Decimal("0.50")) == 50
    assert from_units(128000) == Decimal("1280.00")


@pytest.mark.anyio
async def test_repeating_faucet_request_posts_once(ledger, user_id):
    first = await ledger.grant(user_id, 100_000, "grant:u1:first")
    second = await ledger.grant(user_id, 100_000, "grant:u1:first")
    assert first.transaction_id == second.transaction_id
    assert await ledger.available_units(user_id) == 100_000


@pytest.mark.anyio
async def test_buy_in_cannot_overdraw_wallet(ledger, user_id, table_id):
    await ledger.grant(user_id, 4_000, "grant:u1:small")
    with pytest.raises(InsufficientPlayBalance):
        await ledger.reserve_buy_in(user_id, table_id, 4_001, "buyin:u1:t1")
```

Use `@pytest.mark.anyio` on every async test and provide an `anyio_backend` fixture returning `"asyncio"` in `tests/online/conftest.py`.

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_ledger.py -q
```

Expected: import failure for `online.amounts`.

- [ ] **Step 3: Implement exact integer conversion**

Create `online/amounts.py`:

```python
from decimal import Decimal, ROUND_HALF_UP

SCALE = Decimal("100")


def to_units(value: Decimal | str | int | float) -> int:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * SCALE)


def from_units(value: int) -> Decimal:
    return (Decimal(value) / SCALE).quantize(Decimal("0.01"))
```

- [ ] **Step 4: Implement ledger transaction methods**

Create `online/ledger.py` with `ASSET = "PLAY"`, a frozen `LedgerResult(transaction_id: str, idempotency_key: str, available_units: int)` dataclass, and these public async methods on `PlayLedger`: `ensure_user_wallet`, `available_units`, `grant`, `reserve_buy_in`, `add_on`, `fund_system_seat`, `release_system_seat`, `settle_hand`, `return_stack`, and `journal`. Their argument and result units are always integer hundredths; only `journal` returns serialized entry dictionaries. Mutating methods accept an optional keyword-only `session: AsyncSession | None` so seating and settlement can join the caller's atomic transaction.

When no session is supplied, a mutating method starts and commits one database transaction. When a session is supplied, it performs the same work without committing. In both cases it locks affected account rows in deterministic account-ID order, rejects negative protected-account results, inserts one `play_transactions` row, inserts balanced entries, updates cached account balances, and marks the transaction posted. On a duplicate idempotency key, return the already posted result without changing balances.

`grant` transfers units from the singleton `owner_kind=system, owner_id=play_faucet, account_kind=faucet` contra-account to a user wallet. `fund_system_seat` transfers a fixed 100 BB stack from that faucet to a system player's table escrow, and `release_system_seat` returns the bot's remaining escrow to the faucet when the bot leaves. These two methods are server-internal and have no HTTP route. The faucet may be negative; user wallets, table escrows, and seat stacks may not. Only these explicit issuance paths may use transaction kind `faucet_grant`.

- [ ] **Step 5: Run ledger tests and PostgreSQL trigger test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_ledger.py -q
.\.venv\Scripts\python.exe -m pytest -m postgres tests/online/test_ledger.py -q
```

Expected: all tests pass; a deliberately unbalanced posted transaction is rejected by PostgreSQL.

- [ ] **Step 6: Commit**

```powershell
git add online/amounts.py online/ledger.py tests/online/test_ledger.py
git commit -m "feat: add balanced play wallet ledger"
```

### Task 6: Seed the six-table network catalogue and Quick Play

**Files:**
- Create: `online/catalogue.py`
- Create: `app/routers/lobby.py`
- Test: `tests/online/test_catalogue.py`

- [ ] **Step 1: Write failing table seed and selection tests**

Create `tests/online/test_catalogue.py`:

```python
@pytest.mark.anyio
async def test_seed_creates_exactly_six_network_tables(catalogue):
    await catalogue.seed_defaults()
    rows = await catalogue.list_tables(page=1, per_page=6)
    assert [(row.small_blind_units, row.big_blind_units) for row in rows] == [
        (50, 100), (50, 100),
        (100, 200), (100, 200),
        (500, 1_000), (500, 1_000),
    ]
    assert all(row.scope == "network" and row.max_seats == 6 for row in rows)


@pytest.mark.anyio
async def test_quick_play_prefers_most_occupied_affordable_lowest_stake(catalogue, user_id):
    await catalogue.seed_defaults()
    chosen = await catalogue.quick_play(user_id=user_id, available_units=8_000)
    assert chosen.big_blind_units == 100
    assert chosen.min_buy_in_units == 4_000
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_catalogue.py -q
```

Expected: import failure for `online.catalogue`.

- [ ] **Step 3: Implement idempotent seed and lobby queries**

Create `online/catalogue.py` with six deterministic table seed keys:

```python
DEFAULT_TABLES = (
    ("micro-a", "Micro A", 50, 100),
    ("micro-b", "Micro B", 50, 100),
    ("low-a", "Low A", 100, 200),
    ("low-b", "Low B", 100, 200),
    ("mid-a", "Mid A", 500, 1000),
    ("mid-b", "Mid B", 500, 1000),
)
```

Every table has `scope=network`, `min_buy_in_bb=40`, `max_buy_in_bb=100`, and `max_seats=6`. Occupancy includes both users and system players and exposes `occupied_count`, `human_count`, `system_count`, and `human_join_available` (true for an empty seat or a system seat that can yield at the next boundary).

Seed at least 36 reusable named system players without an `AI` label so the six default tables can be filled without reusing one identity. Give them the same visible wins, hands, and level calculation as users, while keeping `difficulty` server-only. Table population uses `easy`/`normal` at 0.5/1, `normal`/`hard` at 1/2, and `hard`/`maximum` at 5/10.

Quick Play filters tables whose minimum buy-in is affordable, prefers `human_join_available`, then sorts by `big_blind_units ASC`, `occupied_count DESC`, and stable table ID. A table containing a system player remains joinable because that seat can yield between hands. If every qualifying table has six human seats, return the most occupied affordable table with `join_mode="queue"`.

- [ ] **Step 4: Add lobby endpoints**

Add:

```text
GET  /api/lobby/tables?page=1&per_page=6
POST /api/lobby/quick-play {}
```

The list endpoint requires an authenticated session. Quick Play returns the chosen table and whether the client should open the buy-in modal or enter the spectator queue; it does not choose a buy-in or reserve chips by itself.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_catalogue.py -q
```

Expected: all catalogue tests pass.

```powershell
git add online/catalogue.py app/routers/lobby.py tests/online/test_catalogue.py
git commit -m "feat: seed public network tables"
```

### Task 7: Assemble the foundation application and API contract

**Files:**
- Create: `app/online.py`
- Modify: `app/routers/auth.py`
- Create: `app/routers/health.py`
- Create: `app/routers/profiles.py`
- Create: `tests/online/test_foundation_api.py`
- Create: `tests/online/test_postgres_integration.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/online/test_foundation_api.py`:

```python
def test_unauthenticated_lobby_is_rejected(client):
    assert client.get("/api/lobby/tables").status_code == 401


def test_dev_login_returns_same_global_profile_and_six_tables(client):
    login = client.post("/api/auth/dev/101")
    assert login.status_code == 200
    assert login.json()["display_name"] == "Dev Player"
    assert login.json()["available_units"] == 100_000
    lobby = client.get("/api/lobby/tables")
    assert lobby.status_code == 200
    assert len(lobby.json()["tables"]) == 6


def test_repeated_login_does_not_repeat_welcome_grant(client):
    client.post("/api/auth/dev/101")
    client.post("/api/auth/dev/101")
    assert client.get("/api/profile").json()["available_units"] == 100_000


def test_play_top_up_is_idempotent(client):
    client.post("/api/auth/dev/101")
    first = client.post("/api/profile/play-top-up", json={"amount_units": 100_000, "request_id": "topup-1"})
    second = client.post("/api/profile/play-top-up", json={"amount_units": 100_000, "request_id": "topup-1"})
    assert first.json()["available_units"] == second.json()["available_units"] == 200_000
```

- [ ] **Step 2: Verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online/test_foundation_api.py -q
```

Expected: fixture or import failure because `app.online` does not exist.

- [ ] **Step 3: Build the FastAPI application factory**

Create `app/online.py` with `create_app(settings: Settings) -> FastAPI`. Its lifespan must:

1. create the async database engine and session factory;
2. verify the current Alembic revision in production;
3. ensure the default tenant and bot metadata exist;
4. ensure the play faucet account exists;
5. seed the six default network tables;
6. store services on `app.state`;
7. dispose the engine on shutdown.

Mount existing `/static` assets and include auth, lobby, profile, and health routers. Do not switch `app/main.py` yet.

Complete the auth route by ensuring a wallet and calling `grant` with key `welcome:{user_id}` for `100_000` units (1,000.00 play chips) after every successful identity upsert. Ledger idempotency makes the welcome grant happen exactly once, even under concurrent or repeated login.

- [ ] **Step 4: Add profile and health endpoints**

Add:

```text
GET  /api/profile
GET  /api/profile/play-journal?limit=50
POST /api/profile/play-top-up
GET  /health/live
GET  /health/ready
```

The profile endpoint returns global user ID, Telegram user ID, display name, wins, hands, level, available units, and active table stack units. Level thresholds are `0, 10, 50, 100, 200, 500` wins. `POST /api/profile/play-top-up` accepts `1..100_000_000` units per request, has no request-count or lifetime limit in this play-money MVP, requires a client `request_id`, and credits only the wallet; it never changes a currently seated stack. Readiness fails with HTTP 503 if PostgreSQL cannot answer `SELECT 1` or the migration revision is wrong.

- [ ] **Step 5: Add a marked PostgreSQL integration test**

`tests/online/test_postgres_integration.py` must create a user, grant play units, reserve a buy-in, close the session, open a new session, and assert both wallet and escrow balances survived. Mark it `@pytest.mark.postgres` and read only `POKER8_TEST_DATABASE_URL`.

- [ ] **Step 6: Run the foundation gate**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/online -m "not postgres" -q
docker compose up -d postgres_test
$env:POKER8_TEST_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5433/poker8_test'
.\.venv\Scripts\python.exe -m pytest tests/online/test_postgres_integration.py -m postgres -q
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all new foundation tests pass and the legacy suite remains green.

- [ ] **Step 7: Commit**

```powershell
git add app/online.py app/routers/auth.py app/routers/health.py app/routers/profiles.py tests/online
git commit -m "feat: expose authenticated online foundation"
```
