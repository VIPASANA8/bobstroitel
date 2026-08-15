# Poker8 Online MVP runbook

## Local start

```powershell
uv pip install -r requirements.txt
$env:POKER8_DATABASE_URL='sqlite+aiosqlite:///./data/poker8_online_dev.sqlite3'
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\uvicorn.exe app.production:app --host 127.0.0.1 --port 8000
```

Production uses PostgreSQL, a Telegram bot token in an environment variable, and exact tenant host bindings. Browser responses never contain bot tokens.

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
node --check static/app.js
node --check static/online-transport.js
node --check static/lobby.js
node --check static/profile.js
```
