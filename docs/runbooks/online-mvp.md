# Poker8 Online MVP runbook

## Local start

```powershell
uv pip install -r requirements.txt
$env:POKER8_DATABASE_URL='sqlite+aiosqlite:///./data/poker8_online_dev.sqlite3'
$env:POKER8_COORDINATOR_ENABLED='1'
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

Production uses PostgreSQL, a Telegram bot token in an environment variable, and exact tenant host bindings. Browser responses never contain bot tokens.

For temporary IP-only staging, set `POKER8_ENV=staging` and `POKER8_OPEN_ACCESS=1`. The browser then receives a guest session with a random `Guest-XXXXXX` nickname. This mode is intentionally disabled in production and must be set back to `0` before enabling Telegram-only access.

## Docker/PostgreSQL

```powershell
docker compose up -d postgres
$env:POKER8_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5432/poker8'
.venv\Scripts\alembic.exe upgrade head
```

## Backup and restore

```powershell
pg_dump "$env:POKER8_DATABASE_URL" --format=custom --file=poker8-backup.dump
createdb poker8_restore
pg_restore --dbname=postgresql://poker8:poker8@127.0.0.1:5432/poker8_restore poker8-backup.dump
```

Inspect `/health/ready`, paused runtimes and `integrity_events` before reopening traffic. Revoke a session through the authenticated logout flow or directly update its `revoked_at` in an emergency.

## Release gate

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -m postgres -q
.venv\Scripts\python.exe -m pytest tests/e2e -m e2e -q
node --check static/app.js
node --check static/online-transport.js
node --check static/lobby.js
node --check static/profile.js

# Test-only 100-connection / 20-table WebSocket gate.
$env:POKER8_ENV='test'
$env:POKER8_TEST_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5433/poker8_test'
.venv\Scripts\python.exe tests/load/seed_load_tables.py --manifest $env:TEMP\poker8-load-manifest.json --tables 20 --connections 100
.venv\Scripts\python.exe tests/load/online_mvp_load.py --base-url http://127.0.0.1:8000 --connections 100 --tables 20 --duration 120 --manifest $env:TEMP\poker8-load-manifest.json
```
