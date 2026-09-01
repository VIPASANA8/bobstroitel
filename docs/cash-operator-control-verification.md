# CASH package 5: operator control

## Boundary

The operator bot is an adapter, not a financial authority. It has no database connection, wallet credentials, Tron client, private key, seed phrase, or endpoint that sets a balance. Every Telegram update checks the operator against the backend, and every mutation performs a second backend request that rechecks the service key, active database role, and tenant scope.

`POKER8_CASH_MODE=mock` and PostgreSQL are still mandatory. There is no production/live switch in this package.

## Adaptation from case8

The useful patterns retained from `VIPASANA8/case8/foodcamera_admin_bot-master` are backend-owned roles, a service API key, explicit operator identity, API error handling, queue navigation, a reason step, and final confirmation. The Poker8 bot is a separate standard-library process, avoiding case8's aiogram/Pydantic dependency constraints.

The case8 balance setters, treasury/risk pool flows, cases, prizes, promotions, disabled-TLS option, and direct configuration of a receiving wallet were deliberately omitted.

## Backend guarantees

- Roles are `reviewer` (read only), tenant-scoped `operator`, and global `admin`. Revoked rows fail every new request even if the bot still shows an old button.
- Operator bootstrap reads `POKER8_CASH_ADMIN_OPERATORS_JSON` only to create missing rows. It does not reactivate or overwrite an existing database role.
- All decisions require a 3–500 character reason and an idempotency key. The target change, reserve ledger posting, and append-only `cash_audit_events` row commit in one PostgreSQL transaction.
- Reusing a command key with identical content returns the recorded result. Reusing it with changed content fails.
- A rejected withdrawal releases reserve once. Mock success consumes reserve once. `unknown` retains reserve and cannot be sent again; it can only be resolved from a verified transaction reference or verified non-payment.
- Reviewed payment events can be credited only when linked to their reviewed deposit. Unmatched events can only be rejected by a global admin.
- Queue and user lookup are tenant-scoped. The user view keeps available, table escrow, and withdrawal reserve separate in both USDT and CASH units.
- Paused CASH tables appear in the same operator queue. This package does not add an unsafe “resume” button.

## Configuration

Example backend bootstrap value:

```json
[
  {"telegram_user_id": 10001, "role": "admin"},
  {"telegram_user_id": 10002, "role": "operator", "tenant_slug": "poker8"},
  {"telegram_user_id": 10003, "role": "reviewer", "tenant_slug": "poker8"}
]
```

Set it as `POKER8_CASH_ADMIN_OPERATORS_JSON` together with a service secret of at least 16 characters in `POKER8_CASH_ADMIN_API_KEY`. The standalone bot additionally needs `POKER8_CASH_ADMIN_BOT_TOKEN` and `POKER8_CASH_ADMIN_API_URL`. Non-local API URLs must use HTTPS with normal certificate verification.

## Verification

The PostgreSQL suite covers content-bound concurrent approval, role revocation, tenant isolation by direct object ID, reserve release, unknown payout resolution without resend, manual payment review, audit isolation, user lookup, schema parity, and downgrade refusal. The standalone bot tests service/actor headers, idempotency headers, backend denial handling, HTTPS enforcement, and exact amount formatting.
