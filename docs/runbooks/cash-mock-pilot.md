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

Poker8 charges its own deposit fee on top of the credit — `POKER8_CASH_FIAT_FEE_BPS`, 1% by default — so a user asking for 20 USDT of CASH pays roubles for 20.20 USDT, is credited exactly 20, and the fee lands in the `case8-p2p-fee` clearing account. The partner's own `Fee` from `/me` is reported in metrics for comparison and is not part of that arithmetic.

The RUB flow uses the CASE8-compatible in-process partner mock. A user creates a 20–500 USDT order, sees the RUB total with kopecks and the requisites, and presses **Я оплатил**. That notification never changes the balance. The credit happens only when the partner poller reads a `CompletedByTrader`/`CompletedBySupport` event and posts it through `CashLedger`; the UI displays it at `1 USDT = 10 CASH`. A user has one open RUB order at a time, enforced by the database, and an unfinished order comes back with its countdown after a page reload. Withdrawals remain TRC20 mock only.

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

## RUB disputes, late payments and unknown events

`/order ID` in the admin bot opens one order by its Poker8 id or by the partner's number, with every event the poller stored for it. Trader requisites are payment data: the card shows only the last four characters, and nothing in the bot or the audit log carries the full string.

- **Changed redelivery.** The partner sent event 41 as `CompletedByTrader` and later as `CanceledBySupport`. Poker8 applies neither the second time: the event goes to `review_required` with both statuses named, and whatever the first delivery already did stands until an operator says otherwise.
- **Unknown partner order.** A completed event whose order Poker8 never stored stays in `review_required` and credits nothing. An operator presses **Привязать и зачислить**, types the Poker8 order id, and gives a reason. The credit uses the poller's own ledger key, so a later partner replay of that event cannot pay twice, and the decision is in `cash_audit_events` with the operator's Telegram id.
- **Late payment.** The user paid after the quote expired, the order is already terminal, and the partner's completion lands in `review_required`. Same button; answer `-` when the event already names the order.
- **No payment.** **Отклонить** closes the event without touching the ledger.
- **Stuck order.** `requesting`, `clarifying` and `review_required` orders hold the user's one open RUB slot. **Закрыть заявку** cancels such an order. It never credits: only a durable partner event moves money, by design.

Reviewers see the queue and read the cards; only `operator` and `admin` roles may decide, and every decision demands a reason of at least three characters.

## Alerts and the daily sweep

Metrics say what is wrong; the watchdog is what wakes somebody. It runs inside the coordinator — deliberately not inside the partner poller, because a stopped poller is one of the things it reports — and sends one message when a finding appears and one when it clears, through `POKER8_ESCROW_ALERT_WEBHOOK_URL` and/or `POKER8_ALERT_TELEGRAM_BOT_TOKEN` + `POKER8_ALERT_TELEGRAM_CHAT_ID`. Without those it still fills `cash.watchdog.open_findings` in `/health/metrics`, and `alerts_configured` is then `false` — check that before a pilot session.

It alerts on: a stalled or poisoned partner poll, partner events on review, orders stuck in `requesting`, orders waiting for an operator, `unknown` withdrawals, paused CASH tables, and a day whose reconciliation does not balance. Findings live in memory, so a restart repeats a standing alert once.

`/recon` in the admin bot (or `GET /api/cash-admin/reconciliation?day=YYYY-MM-DD`, admin role only) rebuilds the day independently: it reads the credited orders and the ledger separately and only then asks whether they agree, order by order. `balanced: false` names the specific order and what disagreed — a credit with no posting, a credited amount that is not the quote, a fee that is not the fee, or clearing that did not move the whole charge. The watchdog runs the same sweep for today and yesterday every hour, so nobody has to remember to.

Trader requisites are erased seven days after the order is created; the same hourly housekeeping does it, and the admin bot only ever showed their last four characters.

## Holding an account, and the limits that run without one

**A hold** is the manual stop. In the bot, `/user ID` now carries a **Заморозить** / **Разморозить** button; it asks for a reason like every other operator decision, is idempotent by key and lands in `cash_audit_events` with the operator's Telegram id. The API is `POST /api/cash-admin/users/{id}/freeze` and `/unfreeze`.

A hold stops **new** money: no deposit, no RUB order, no withdrawal, no sitting down at a CASH table. It deliberately does **not** stop money already at risk — a partner completion for an order the user already paid still credits, a seated player still leaves with their escrow, and a settled hand still pays. Freezing an account mid-payment must not turn the user's own money into a hostage of the investigation. The user is told only that their account is on hold; the operator's reason stays with the operator.

**Limits run without anybody watching**:

- `POKER8_CASH_ORDERS_PER_HOUR` — RUB requests per user per hour, default 6, `0` disables it. Refused with `429` before a trader is asked for anything.
- `POKER8_CASH_DAILY_DEPOSIT_USDT` — the 24-hour total a user may ask for, default `0` (off, which is what the pilot chose). Cancelled orders cost the user nothing and do not count; open and credited ones do.

**Signals go to an operator, never to an automatic freeze.** A user who pressed «Я оплатил» and then cancelled three or more times in a day becomes a watchdog alert and a line on their `/user` card. The same pattern fits an honest user whose trader kept going silent, which is exactly why the decision stays human.

Not covered, and not pretendable: repeat accounts. Poker8 has no device, document or payment-instrument identity to compare, so the same person on two Telegram accounts is invisible here. That needs KYC or a real device signal, and both belong to the real-money decision, not this pilot.

## Backup and restore

A backup is only good if restoring it cannot pay anybody twice. The check builds a database that has done every irreversible CASH thing — a credited TRC20 provider event, a credited RUB partner event, a submitted payout, a settled CASH hand — dumps it, restores it into a database that has never run the application, and then replays every one of those operations against the restored copy:

```bash
python tools/cash_backup_restore_check.py
```

It uses `pg_dump`/`psql` from the compose service when no local client is installed, drops its two scratch databases afterwards (`--keep` leaves them), and exits non-zero on the first thing that does not hold. It asserts three separate properties:

1. the restored copy matches the source row for row and balance for balance, and carries the same `alembic_version` the application demands at boot;
2. a redelivered provider event, a redelivered partner completion and a repeated hand command change no balance and add no transaction — the idempotency keys were inside the dump, not in the memory of the process that made them;
3. repeating the payout never reaches the executor, so a restore cannot put a second transfer on chain.

The check has been verified in both directions: with a deliberate second credit posted under a key the dump did not carry, it fails and names the account, the amount and the extra rows.

Before real money, run it against a restore of the actual backup you intend to rely on, not only against this synthetic one — the properties are the same, the data is not.

## What the suite already proves, and what staging still has to

Automated, on every run (`pytest -m postgres`):

- another user's deposit, RUB order or withdrawal id is a 404 on every route that takes one, including the mutating ones;
- the same provider event delivered by four processes at once credits exactly once, and 24 credits landing together on one wallet row and one clearing row stay exact to the micro;
- two withdrawals racing for the same balance end with exactly one reservation — the ledger's non-negative constraint, not application timing, is what stops the second;
- a crash between a partner event and its commit leaves no event row, no posting and an unmoved cursor, so the redelivery credits once;
- leaving a table twice, and leaving again from a second process, returns the escrow once;
- a hand settles exactly with no WebSocket attached at all, so a dropped connection cannot cost or create a chip;
- `POKER8_CASH_MODE=off` answers 404 on the identity gate and an allowlist miss answers 403;
- trader requisites and the partner token appear in no application log line.

That last one holds only while SQLAlchemy engine echo stays off. **Never set `echo=True` or raise `sqlalchemy.engine` to INFO in a pilot**: SQL parameter logging would put card requisites in the log file, and no test can stop it.

Not automated, and the reason a separate staging exists:

- sustained load. `tests/load/online_mvp_load.py` measures PLAY WebSockets against a running deployment, not the ledger. A CASH load run needs a target first — how many concurrent depositors, what latency is acceptable — and a machine that is not production.
- Staging must be its own machine, its own PostgreSQL, its own bot token, its own `POKER8_CASH_ALLOWLIST` and its own alert channel. It must never point at production data, and the backup/restore check belongs there as well as here. Keep it at `POKER8_CASH_MODE=mock` until the partner's sandbox credentials exist; the sandbox is a separate mode and a separate decision.

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
