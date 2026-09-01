# CASH package 4: simulated C2C TRC20

## Scope

This package implements a PostgreSQL-only simulation boundary for the first complete CASH funding cycle. It does not connect TronGrid, store a private key, send a blockchain transaction, expose a provider webhook, or enable CASH in production. `POKER8_CASH_MODE=mock` remains limited to development/test and now fails startup unless the database is PostgreSQL.

The fixed product denomination remains `1 USDT = 10 CASH units`; every authoritative amount is an integer micro-USDT.

## Deposit contract

- A user requests 1–100 USDT and receives the mock TRC20 address plus a permanently unique exact amount. The allocator tries offsets `0.00` through `0.09` USDT and never crosses 100 USDT.
- The observable initial state is `awaiting_transfer`; expiry is 30 minutes. Cancelled, expired, or reviewed rows remain in the database, so their address/amount pair is never reassigned.
- “I paid” only acknowledges the request. It cannot credit the wallet.
- A durable payment event is keyed both by provider event ID and by transaction hash/event index. Network, token contract, address, exact amount, and event time must all match.
- A valid event posts the whole unique amount from the mock external clearing account to the user's available account, once. Invalid, ambiguous, late, and terminal events are retained as `review_required` without a balance change.
- The reconciler expires overdue requests and replays durable `observed` events after a process restart.

## Withdrawal contract

- A user may request 0.01–100 USDT to an immutable TRC20 address. The mock fee is zero.
- Creation and `available → withdrawal reserve` posting commit in one transaction. Identical concurrent request keys serialize through a PostgreSQL advisory transaction lock and remain content-bound.
- Cancellation or mock rejection returns the reserve exactly once. A successful mock send posts `reserve → external clearing`, records a stable payout ID and mock transaction hash, then can be confirmed. An unknown outcome stays `unknown` with the reserve untouched.
- User lookup is always scoped by authenticated user ID. No operator approval/execution route is public in this package.

## Verification commands

Run with the local `postgres_test` service:

```powershell
$env:POKER8_CASH_TEST_DATABASE_URL='postgresql+psycopg://poker8:poker8@localhost:5433/poker8_test'
python -m pytest tests/cash -q -m postgres
python -m pytest -q
python -m alembic heads
```

The focused PostgreSQL suite covers unique allocation and exhaustion, content-bound retries, duplicate concurrent transfer delivery, invalid/late event retention, restart reconciliation, reserve cancellation, successful/unknown payout outcomes, ownership, and migration downgrade refusal.
