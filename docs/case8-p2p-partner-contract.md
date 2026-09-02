# CASE8 P2P partner contract

Source: private repository `VIPASANA8/case8`, commit
`8173c733d71f012537cb08d035777fe9e04b9f83`. This document records only what
is present in that pinned source. The partner is not named there and no public
API documentation or real sandbox URL is committed.

## Pilot boundary

- Poker8 accepts only `RUB` fiat deposits in the first pilot.
- Fiat withdrawal is out of scope; withdrawal remains USDT TRC20.
- Confirmed USDT is credited through the existing `CashLedger` at
  `1 USDT = 10 CASH`.
- The CASE8 `mock` gateway is the only verified sandbox substitute. A real
  partner environment cannot be enabled until its URL, token and certificate
  are supplied and checked independently.

## Partner HTTP protocol

All partner calls send `X-Token: <token>`. CASE8 does not sign requests and the
partner does not call a webhook. Completion is received by outbound long
polling. Poker8 must therefore preserve a durable poll offset and durable raw
events instead of inventing a webhook contract.

| Operation | Request | Verified response |
|---|---|---|
| Create order | `POST /order?amount=<integer>&currency=RUB` | `204` means no trader. Success JSON accepts upper- or lower-case keys: `ID`, `Amount`, `Method`, `Expires`, optional `Username`. |
| Business/health data | `GET /me` | `ID`, `Title`, `Fee`, `CreatedAt`, `Deposit`. |
| User paid / cancel | `POST /notify?order_id=<integer>&cancel=false|true` | Any successful HTTP response; the call itself never credits CASH. |
| Poll outcomes | `GET /events?offset=<integer>` | `204` means no events. Success is a JSON list. Every usable item has integer `ID`, string `Status`, and integer `OrderID`. |

CASE8 represents requested USDT in integer hundredths: `2000` means 20.00 USDT
and its accepted range is 20.00–1000.00 USDT. The returned `Amount` is RUB with
kopecks after a comma (`1850,75`), confirmed by the project owner on 2026-09-02;
the pinned source does not state it. Poker8 stores it as integer kopecks in
`cash_fiat_orders.fiat_kopecks` and accepts `1850`, `1850,75` and `1850.75`,
rejecting anything else rather than rounding it. The sandbox must still confirm
this before real orders are enabled, and whether `Amount` already includes the
partner commission is still open.

`Expires` accepts ISO-8601, with or without a timezone; Poker8 will normalize
it to UTC. `Method` contains the payment requisites shown to the user.

## Event statuses

| Partner status | Poker8 meaning |
|---|---|
| `WaitingUser` | Informational; advance the offset, keep waiting for the user. |
| `WaitingTrader` | Informational; advance the offset, keep waiting for the trader. |
| `Expired` | Terminal failure, no credit. |
| `Clarifying` | Manual review; retain optional `Reason`/`Message`, no credit. |
| `CanceledByUser` | Terminal cancellation, no credit. |
| `CanceledByTrader` | Terminal cancellation, no credit. |
| `CanceledBySupport` | Terminal cancellation, no credit. |
| `CompletedByTrader` | Credit the order's originally stored USDT amount once. |
| `CompletedBySupport` | Credit the order's originally stored USDT amount once. |

The gateway also parses four legacy event shapes (`RequestAccepted`,
`RequestExpired`, `OrderExpired`, `OrderFinished`). They are compatibility
input only. New Poker8 rows use the current status protocol above.

An unknown or malformed event is a poison event: do not advance beyond it and
raise an operator-visible reconciliation incident. The offset is committed
only after the corresponding order transition and ledger posting commit.
Duplicate delivery is expected and must remain harmless. The same event id
carrying different content is not: Poker8 stores a hash of every delivery, and
a changed redelivery applies nothing and moves that event to
`review_required`, because one of the two deliveries is a lie and only an
operator can say which.

## Timeouts and failures

- order and notify deadline: 5 seconds;
- event long poll: 35 seconds;
- at most three retries for order/notify, within the same total deadline;
- `409`, `429`, and `503` from `/events` are transient;
- `Retry-After` is used when it is an integer, otherwise the retry is 5 seconds;
- `400`, `422`, and `500` are surfaced for operator attention;
- network timeout never changes a balance and never proves cancellation.

## What Poker8 runs today

- `cash/fiat_poller.py` owns the long poll: one leader per database chosen with
  a PostgreSQL advisory lock, `GET /me` on start for health and the `Fee`
  snapshot, exponential backoff honouring an integer `Retry-After`, and a stop
  that never interrupts a committed transition.
- A malformed or unknown event poisons the loop on purpose: the offset stays
  where it is, `cash.partner_poller.poisoned` goes true in `/metrics` and an
  operator has to look. Alert on `seconds_since_success`, not on error counts.
- One open RUB order per user is a partial unique index over
  `('requesting', 'awaiting_user', 'waiting_trader', 'clarifying')`, not a
  service-level check, so a second tab cannot open a second order.

The pinned source defaults `PARTNER_TLS_VERIFY=false` and comments that the
current endpoint uses a self-signed certificate on an IP address. Poker8 will
not carry that setting over. TLS verification is mandatory; a real adapter is
disabled until the partner supplies a hostname and trusted certificate (or a
separately approved certificate-pinning design).

## Internal order model

Store at least: local UUID, content-bound request key, user/tenant, currency,
requested USDT micros, partner order ID, fiat amount and its unit, payment
requisites, optional trader username, commission snapshot, expiry, state,
last error, timestamps and version. Only one active RUB order per user is
allowed. A repeated request key with different content is a conflict.

The minimal states are `created`, `trader_found`, `user_confirmed`,
`awaiting_result`, `clarifying`, `completed`, `cancelled`, `expired`, and
`failed`. The user button records confirmation and calls `/notify`; only a
durable `CompletedByTrader` or `CompletedBySupport` event may post funds.

CASE8 contains an ambiguity around commission: it adds commission to the USDT
amount sent to `/order`, then also derives a fiat commission from the returned
amount for display. Poker8 does not copy that formula. It charges its own
deposit fee — `POKER8_CASH_FIAT_FEE_BPS`, 100 basis points by default — on top
of what the user is credited: `/order` asks for credit plus fee, rounded up to
a whole USDT cent, and the RUB total the partner returns is the whole amount
the user pays. `fee_micros` on the order is that snapshot. The partner's own
`Fee` from `/me` is a separate number, recorded in `/health/metrics` for
comparison and never used in a calculation.

## Pinned evidence

- partner transport: `pservice-master/infrastructure/partner_gateways/current_partner/gateway.py`;
- configuration and unsafe TLS default: `pservice-master/config.py`;
- internal routes and service-key auth: `pservice-master/api/routes/payments.py`,
  `pservice-master/api/routes/orders.py`, `pservice-master/api/dependencies.py`;
- order states and transitions: `pservice-master/domain/enums/order_status.py`,
  `pservice-master/domain/entities/payment_order.py`;
- completion and reconciliation ordering:
  `pservice-master/application/use_cases/process_partner_event.py`,
  `pservice-master/infrastructure/polling/long_poll_worker.py`;
- local sandbox substitute:
  `pservice-master/infrastructure/partner_gateways/mock_gateway.py`.
