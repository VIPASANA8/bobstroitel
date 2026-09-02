# CASH mock pilot runbook

This runbook is only for the isolated development/test contour. The application has no production CASH mode: `POKER8_CASH_MODE` accepts only `off`, or `mock` in development/test.

## Start the local pilot

```powershell
docker compose up -d postgres_test
$env:POKER8_ENV='test'
$env:POKER8_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5433/poker8_test'
$env:POKER8_CASH_MODE='mock'
$env:POKER8_CASH_ALLOWLIST='101,202'
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

Use only Telegram IDs belonging to pilot testers. An empty `POKER8_CASH_ALLOWLIST` allows every otherwise valid test identity and is intended for local development only.

The RUB flow uses the CASE8-compatible in-process partner mock. A user creates a 20–1000 USDT order, sees the RUB total with kopecks and the requisites, and presses **Я оплатил**. That notification never changes the balance. The credit happens only when the partner poller reads a `CompletedByTrader`/`CompletedBySupport` event and posts it through `CashLedger`; the UI displays it at `1 USDT = 10 CASH`. A user has one open RUB order at a time, enforced by the database, and an unfinished order comes back with its countdown after a page reload. Withdrawals remain TRC20 mock only.

## Observe and reconcile

Check `GET /health/metrics`. The `cash` section must normally contain zeros for:

- `expired_deposits_pending_reconciliation`
- `unknown_withdrawals`
- `fiat_orders_requiring_attention`
- `fiat_events_requiring_review`
- `paused_tables`

`cash.partner_poller` reports the long poll itself:

- `leader` is true in exactly one process; the others idle by design.
- `seconds_since_success` is the alert. A stalled poll means paid orders are not being credited, long before a user complains. Page on it, not on error counts.
- `poisoned` true means an unknown or malformed event stopped the loop with the offset intact. Read the raw event, fix or agree the mapping, then restart the process; never edit the cursor forward to skip it.
- `partner_fee` is the `Fee` from `/me` at start. Against a real partner, compare it with the fee the pilot charges before the first order.

`partner_event_offset` must never move backwards after a restart. Use the admin bot `/queue` for item details. `requesting` may mean the process stopped during partner order creation; do not automatically create another external order because CASE8 exposes no client idempotency key. An unknown completed partner order stays in `review_required` and must not be credited without a verified user/order mapping.

## Stop CASH without stopping PLAY

1. Set `POKER8_CASH_MODE=off` and restart the application.
2. Confirm the REAL CASH tab is hidden and CASH API requests return 404/403.
3. Confirm the training lobby, PLAY tables and `/health/ready` still work.
4. Keep PostgreSQL and the admin audit available until every reserved withdrawal, occupied CASH seat and review item is reconciled.

Do not delete payment, event, cursor, audit or ledger rows. Downgrades intentionally refuse to remove non-empty CASH history.

## Acceptance gate

```powershell
$env:POKER8_CASH_TEST_DATABASE_URL='postgresql+psycopg://poker8:poker8@127.0.0.1:5433/poker8_test'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -m postgres -q
.venv\Scripts\python.exe -m pytest -m e2e -q tests\e2e\test_cash_flow.py
node --check static\lobby.js
```

Before any real-money design, separately approve the partner URL and credentials, confirmed fee semantics, KYC/AML and sanctions process, custody and refund ownership, daily independent reconciliation, alert recipients, and legal jurisdiction.
