from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from cash.access import CashOperator
from cash.amounts import micros_to_units, micros_to_usdt
from cash.ledger import CashLedger, IdempotencyConflict
from cash.withdrawals import MockPayoutExecutor, WithdrawalStateError
from online.catalogue import CASH_USDT
from online.schema import (
    cash_accounts, cash_audit_events, cash_deposits, cash_payment_events,
    cash_fiat_events, cash_fiat_orders, cash_withdrawals, poker_tables, table_runtimes, users,
)


class OperatorAccessDenied(ValueError):
    pass


def _json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _snapshot(row, fields):
    return {field: _json(row[field]) for field in fields}


def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


WITHDRAWAL_FIELDS = (
    "id", "user_id", "tenant_id", "network", "destination_address", "amount_micros",
    "fee_micros", "reserve_account_id", "payout_id", "tx_hash", "status", "detail",
    "submitted_at", "confirmed_at",
)
EVENT_FIELDS = (
    "id", "provider", "external_event_id", "tx_hash", "event_index", "network",
    "token_contract", "destination_address", "amount_micros", "occurred_at", "status", "deposit_id",
)
FIAT_ORDER_FIELDS = (
    "id", "user_id", "tenant_id", "partner_order_id", "currency", "requested_micros",
    "fiat_kopecks", "status", "detail", "expires_at",
)
FIAT_EVENT_FIELDS = (
    "provider", "event_id", "partner_order_id", "fiat_order_id", "event_type", "status", "detail",
)
PROVIDER = "case8-p2p"


def _mask(value):
    """Trader requisites are payment data: an operator sees only the tail."""
    return None if not value else "…" + str(value)[-4:]


class CashAdminService:
    def __init__(self, session_factory, *, ledger=None, executor=None, now=None):
        self.sessions = session_factory
        self.ledger = ledger or CashLedger()
        self.executor = executor or MockPayoutExecutor()
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _require_scope(operator: CashOperator, tenant_id: str | None):
        if not operator.can_access(tenant_id):
            raise OperatorAccessDenied("operator cannot access this tenant")

    @staticmethod
    def _require_mutation(operator: CashOperator):
        if not operator.can_mutate():
            raise OperatorAccessDenied("reviewer role is read-only")

    async def queue(self, operator: CashOperator):
        async with self.sessions() as session:
            withdrawal_query = select(cash_withdrawals).where(
                cash_withdrawals.c.status.in_(("reserved", "approved", "unknown", "submitted"))
            )
            event_query = select(cash_payment_events, cash_deposits.c.tenant_id).outerjoin(
                cash_deposits, cash_deposits.c.id == cash_payment_events.c.deposit_id,
            ).where(cash_payment_events.c.status == "review_required")
            fiat_order_query = select(cash_fiat_orders).where(
                cash_fiat_orders.c.status.in_(("requesting", "clarifying", "review_required"))
            )
            fiat_event_query = select(cash_fiat_events, cash_fiat_orders.c.tenant_id).outerjoin(
                cash_fiat_orders, cash_fiat_orders.c.id == cash_fiat_events.c.fiat_order_id,
            ).where(cash_fiat_events.c.status == "review_required")
            table_query = select(
                poker_tables.c.id, poker_tables.c.tenant_id, poker_tables.c.name,
                table_runtimes.c.paused_reason, table_runtimes.c.updated_at,
            ).join(table_runtimes, table_runtimes.c.table_id == poker_tables.c.id).where(
                poker_tables.c.asset == CASH_USDT, table_runtimes.c.phase == "paused",
            )
            if operator.role != "admin":
                withdrawal_query = withdrawal_query.where(cash_withdrawals.c.tenant_id == operator.tenant_id)
                event_query = event_query.where(cash_deposits.c.tenant_id == operator.tenant_id)
                fiat_order_query = fiat_order_query.where(cash_fiat_orders.c.tenant_id == operator.tenant_id)
                fiat_event_query = fiat_event_query.where(cash_fiat_orders.c.tenant_id == operator.tenant_id)
                table_query = table_query.where(poker_tables.c.tenant_id == operator.tenant_id)
            withdrawals = (await session.execute(withdrawal_query.order_by(
                cash_withdrawals.c.created_at
            ))).mappings().all()
            events = (await session.execute(event_query.order_by(
                cash_payment_events.c.created_at
            ))).mappings().all()
            fiat_orders = (await session.execute(fiat_order_query.order_by(
                cash_fiat_orders.c.created_at
            ))).mappings().all()
            fiat_events = (await session.execute(fiat_event_query.order_by(
                cash_fiat_events.c.created_at
            ))).mappings().all()
            paused = (await session.execute(table_query.order_by(poker_tables.c.id))).mappings().all()
        return {
            "withdrawals": [_snapshot(row, WITHDRAWAL_FIELDS) for row in withdrawals],
            "payment_reviews": [_snapshot(row, EVENT_FIELDS) | {"tenant_id": row["tenant_id"]} for row in events],
            "fiat_orders": [_snapshot(row, FIAT_ORDER_FIELDS) for row in fiat_orders],
            "fiat_reviews": [_snapshot(row, FIAT_EVENT_FIELDS) | {"tenant_id": row["tenant_id"]}
                              for row in fiat_events],
            "paused_tables": [dict(row) for row in paused],
        }

    async def audit(self, operator: CashOperator, limit=100):
        limit = max(1, min(int(limit), 500))
        async with self.sessions() as session:
            query = select(cash_audit_events).order_by(cash_audit_events.c.created_at.desc()).limit(limit)
            if operator.role != "admin":
                query = query.where(cash_audit_events.c.tenant_id == operator.tenant_id)
            rows = (await session.execute(query)).mappings().all()
            return [dict(row) for row in rows]

    async def user(self, operator: CashOperator, identifier: str):
        if not identifier or len(identifier) > 64:
            raise ValueError("invalid user identifier")
        async with self.sessions() as session:
            condition = users.c.id == identifier
            try:
                condition = condition | (users.c.telegram_user_id == int(identifier))
            except ValueError:
                pass
            user = (await session.execute(select(users).where(condition))).mappings().first()
            if user is None:
                raise LookupError("user not found")
            self._require_scope(operator, user["acquisition_tenant_id"])
            accounts = (await session.execute(select(
                cash_accounts.c.kind, cash_accounts.c.balance_micros
            ).where(cash_accounts.c.user_id == user["id"]))).all()
            deposits = (await session.execute(select(cash_deposits).where(
                cash_deposits.c.user_id == user["id"]
            ).order_by(cash_deposits.c.created_at.desc()).limit(20))).mappings().all()
            withdrawals = (await session.execute(select(cash_withdrawals).where(
                cash_withdrawals.c.user_id == user["id"]
            ).order_by(cash_withdrawals.c.created_at.desc()).limit(20))).mappings().all()
            fiat_orders = (await session.execute(select(cash_fiat_orders).where(
                cash_fiat_orders.c.user_id == user["id"]
            ).order_by(cash_fiat_orders.c.created_at.desc()).limit(20))).mappings().all()
        balances = {kind: sum(amount for row_kind, amount in accounts if row_kind == kind)
                    for kind in ("available", "escrow", "withdrawal")}
        return {
            "id": user["id"], "telegram_user_id": user["telegram_user_id"],
            "display_name": user["display_name"], "tenant_id": user["acquisition_tenant_id"],
            "balances": {kind: {"usdt": micros_to_usdt(amount), "units": micros_to_units(amount)}
                         for kind, amount in balances.items()},
            "deposits": [{"id": row["id"], "status": row["status"],
                          "expected_usdt": micros_to_usdt(row["expected_micros"])} for row in deposits],
            "withdrawals": [{"id": row["id"], "status": row["status"],
                             "amount_usdt": micros_to_usdt(row["amount_micros"])} for row in withdrawals],
            "fiat_orders": [{
                "id": row["id"], "partner_order_id": row["partner_order_id"],
                "status": row["status"], "currency": row["currency"],
                "fiat_kopecks": row["fiat_kopecks"],
                "requested_usdt": micros_to_usdt(row["requested_micros"]),
            } for row in fiat_orders],
        }

    async def approve_withdrawal(self, withdrawal_id, operator, *, reason, key):
        self._require_mutation(operator)
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "withdrawal.approve", withdrawal_id, reason, {},
                )
                if replay is not None:
                    return replay
                row = await self._withdrawal(session, withdrawal_id)
                self._require_scope(operator, row["tenant_id"])
                if row["status"] != "reserved":
                    raise WithdrawalStateError("only a reserved withdrawal can be approved")
                before = _snapshot(row, WITHDRAWAL_FIELDS)
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(status="approved", detail=reason, updated_at=self.now()))
                after = before | {"status": "approved", "detail": reason}
                await self._audit(session, operator, row["tenant_id"], "withdrawal.approve",
                                  "withdrawal", withdrawal_id, reason, key, fingerprint, before, after)
                return after

    async def reject_withdrawal(self, withdrawal_id, operator, *, reason, key):
        self._require_mutation(operator)
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "withdrawal.reject", withdrawal_id, reason, {},
                )
                if replay is not None:
                    return replay
                row = await self._withdrawal(session, withdrawal_id)
                self._require_scope(operator, row["tenant_id"])
                if row["status"] not in {"reserved", "approved"}:
                    raise WithdrawalStateError("withdrawal cannot be rejected in its current state")
                before = _snapshot(row, WITHDRAWAL_FIELDS)
                wallet_id = await self._account(session, "available", row["user_id"], row["user_id"])
                await self.ledger.post(
                    session, scope="withdrawal-release", key=withdrawal_id, kind="release",
                    reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                    postings={row["reserve_account_id"]: -row["amount_micros"], wallet_id: row["amount_micros"]},
                )
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(status="rejected", detail=reason, updated_at=self.now()))
                after = before | {"status": "rejected", "detail": reason}
                await self._audit(session, operator, row["tenant_id"], "withdrawal.reject",
                                  "withdrawal", withdrawal_id, reason, key, fingerprint, before, after)
                return after

    async def execute_mock(self, withdrawal_id, operator, *, outcome, reason, key):
        self._require_mutation(operator)
        if outcome not in {"success", "failure", "unknown"}:
            raise ValueError("invalid mock payout outcome")
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "withdrawal.execute_mock", withdrawal_id,
                    reason, {"outcome": outcome},
                )
                if replay is not None:
                    return replay
                row = await self._withdrawal(session, withdrawal_id)
                self._require_scope(operator, row["tenant_id"])
                if row["status"] != "approved":
                    raise WithdrawalStateError("only an approved withdrawal can be sent")
                before = _snapshot(row, WITHDRAWAL_FIELDS)
                result = self.executor.send(row["payout_id"], outcome)
                now = self.now()
                if result["status"] == "submitted":
                    clearing = await self._account(session, "clearing", None, "c2c-mock")
                    await self.ledger.post(
                        session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                        reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                        postings={row["reserve_account_id"]: -row["amount_micros"], clearing: row["amount_micros"]},
                    )
                    values = {"status": "submitted", "tx_hash": result["tx_hash"],
                              "detail": reason, "submitted_at": now, "updated_at": now}
                elif result["status"] == "unknown":
                    values = {"status": "unknown", "detail": reason, "updated_at": now}
                else:
                    wallet = await self._account(session, "available", row["user_id"], row["user_id"])
                    await self.ledger.post(
                        session, scope="withdrawal-release", key=withdrawal_id, kind="release",
                        reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                        postings={row["reserve_account_id"]: -row["amount_micros"], wallet: row["amount_micros"]},
                    )
                    values = {"status": "rejected", "detail": reason, "updated_at": now}
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(**values))
                after = before | {name: _json(value) for name, value in values.items() if name in WITHDRAWAL_FIELDS}
                await self._audit(session, operator, row["tenant_id"], "withdrawal.execute_mock",
                                  "withdrawal", withdrawal_id, reason, key, fingerprint, before, after)
                return after

    async def resolve_withdrawal(self, withdrawal_id, operator, *, decision, tx_hash, reason, key):
        self._require_mutation(operator)
        if decision not in {"confirmed", "rejected"}:
            raise ValueError("resolution must be confirmed or rejected")
        if decision == "confirmed" and (not tx_hash or len(tx_hash) > 128):
            raise ValueError("a verified transaction reference is required")
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "withdrawal.resolve", withdrawal_id,
                    reason, {"decision": decision, "tx_hash": tx_hash},
                )
                if replay is not None:
                    return replay
                row = await self._withdrawal(session, withdrawal_id)
                self._require_scope(operator, row["tenant_id"])
                if row["status"] not in {"unknown", "submitted"}:
                    raise WithdrawalStateError("only unknown or submitted payouts can be resolved")
                before = _snapshot(row, WITHDRAWAL_FIELDS)
                now = self.now()
                if decision == "confirmed":
                    if row["status"] == "unknown":
                        clearing = await self._account(session, "clearing", None, "c2c-mock")
                        await self.ledger.post(
                            session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                            reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                            postings={row["reserve_account_id"]: -row["amount_micros"], clearing: row["amount_micros"]},
                        )
                    values = {"status": "confirmed", "tx_hash": tx_hash,
                              "detail": reason, "confirmed_at": now, "updated_at": now}
                else:
                    if row["status"] != "unknown":
                        raise WithdrawalStateError("a submitted payout cannot be rejected")
                    wallet = await self._account(session, "available", row["user_id"], row["user_id"])
                    await self.ledger.post(
                        session, scope="withdrawal-release", key=withdrawal_id, kind="release",
                        reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                        postings={row["reserve_account_id"]: -row["amount_micros"], wallet: row["amount_micros"]},
                    )
                    values = {"status": "rejected", "detail": reason, "updated_at": now}
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(**values))
                after = before | {name: _json(value) for name, value in values.items() if name in WITHDRAWAL_FIELDS}
                await self._audit(session, operator, row["tenant_id"], "withdrawal.resolve",
                                  "withdrawal", withdrawal_id, reason, key, fingerprint, before, after)
                return after

    async def resolve_payment(self, event_id, operator, *, decision, reason, key):
        self._require_mutation(operator)
        if decision not in {"credit", "reject"}:
            raise ValueError("payment resolution must be credit or reject")
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "payment.resolve", event_id, reason, {"decision": decision},
                )
                if replay is not None:
                    return replay
                event = (await session.execute(select(cash_payment_events).where(
                    cash_payment_events.c.id == event_id
                ).with_for_update())).mappings().one_or_none()
                if event is None:
                    raise LookupError("payment event not found")
                deposit = None
                if event["deposit_id"]:
                    deposit = (await session.execute(select(cash_deposits).where(
                        cash_deposits.c.id == event["deposit_id"]
                    ).with_for_update())).mappings().one()
                tenant_id = deposit["tenant_id"] if deposit else None
                self._require_scope(operator, tenant_id)
                if event["status"] != "review_required":
                    raise ValueError("payment event is not awaiting review")
                if decision == "credit" and (deposit is None or deposit["status"] != "review_required"):
                    raise ValueError("payment event cannot be credited without its reviewed deposit")
                before = _snapshot(event, EVENT_FIELDS)
                if decision == "credit":
                    wallet = await self._account(session, "available", deposit["user_id"], deposit["user_id"])
                    clearing = await self._account(session, "clearing", None, "c2c-mock")
                    await self.ledger.post(
                        session, scope="deposit-review", key=event["id"], kind="deposit",
                        reference_id=deposit["id"], actor=f"operator:{operator.telegram_user_id}",
                        postings={clearing: -event["amount_micros"], wallet: event["amount_micros"]},
                    )
                    await session.execute(update(cash_deposits).where(
                        cash_deposits.c.id == deposit["id"]
                    ).values(status="credited", updated_at=self.now()))
                    status = "resolved_credited"
                else:
                    if deposit and deposit["status"] == "review_required":
                        await session.execute(update(cash_deposits).where(
                            cash_deposits.c.id == deposit["id"]
                        ).values(status="cancelled", updated_at=self.now()))
                    status = "resolved_rejected"
                await session.execute(update(cash_payment_events).where(
                    cash_payment_events.c.id == event_id
                ).values(status=status, detail_json={"operator_reason": reason}, processed_at=self.now()))
                after = before | {"status": status}
                await self._audit(session, operator, tenant_id, "payment.resolve", "payment_event",
                                  event_id, reason, key, fingerprint, before, after)
                return after

    async def fiat_order(self, operator: CashOperator, identifier: str):
        """One RUB order by Poker8 id or partner order id, with its raw events."""
        identifier = str(identifier or "")
        if not identifier or len(identifier) > 64:
            raise ValueError("invalid fiat order identifier")
        async with self.sessions() as session:
            condition = cash_fiat_orders.c.id == identifier
            if identifier.isdigit():
                condition = condition | (cash_fiat_orders.c.partner_order_id == int(identifier))
            row = (await session.execute(select(cash_fiat_orders).where(condition))).mappings().first()
            if row is None:
                raise LookupError("fiat order not found")
            self._require_scope(operator, row["tenant_id"])
            events = (await session.execute(select(cash_fiat_events).where(
                (cash_fiat_events.c.fiat_order_id == row["id"])
                | (cash_fiat_events.c.partner_order_id == row["partner_order_id"])
            ).order_by(cash_fiat_events.c.event_id))).mappings().all()
        return _snapshot(row, FIAT_ORDER_FIELDS) | {
            "trader_username": row["trader_username"],
            "requisites_tail": _mask(row["requisites"]),
            "created_at": _json(row["created_at"]), "updated_at": _json(row["updated_at"]),
            "events": [_snapshot(event, FIAT_EVENT_FIELDS) | {"processed_at": _json(event["processed_at"])}
                       for event in events],
        }

    async def resolve_fiat_event(self, event_id, operator, *, decision, reason, key, order_id=None):
        """Bind a partner event to its order and credit it once, or close it unpaid."""
        self._require_mutation(operator)
        if decision not in {"credit", "reject"}:
            raise ValueError("fiat event resolution must be credit or reject")
        if order_id is not None and (not order_id or len(order_id) > 64):
            raise ValueError("invalid fiat order identifier")
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "fiat_event.resolve", str(event_id), reason,
                    {"decision": decision, "order_id": order_id},
                )
                if replay is not None:
                    return replay
                event = (await session.execute(select(cash_fiat_events).where(
                    cash_fiat_events.c.provider == PROVIDER,
                    cash_fiat_events.c.event_id == int(event_id),
                ).with_for_update())).mappings().one_or_none()
                if event is None:
                    raise LookupError("fiat event not found")
                if event["status"] != "review_required":
                    raise ValueError("fiat event is not awaiting review")
                target_id = order_id or event["fiat_order_id"]
                if not target_id:
                    raise ValueError("this event names no Poker8 order; supply the one it belongs to")
                order = (await session.execute(select(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == target_id
                ).with_for_update())).mappings().one_or_none()
                if order is None:
                    raise LookupError("fiat order not found")
                self._require_scope(operator, order["tenant_id"])
                before = _snapshot(event, FIAT_EVENT_FIELDS)
                now = self.now()
                if decision == "credit":
                    if event["event_type"] != "completed":
                        raise ValueError("only a completed partner event can credit an order")
                    if order["status"] == "credited":
                        raise ValueError("the order is already credited")
                    wallet = await self._account(session, "available", order["user_id"], order["user_id"])
                    clearing = await self._account(session, "clearing", None, PROVIDER)
                    # The poller's ledger key, so a later partner replay of the same
                    # event cannot credit this order a second time.
                    await self.ledger.post(
                        session, scope="fiat-deposit", key=PROVIDER + ":" + str(event["event_id"]),
                        kind="deposit", reference_id=order["id"],
                        actor="operator:" + str(operator.telegram_user_id),
                        postings={clearing: -order["requested_micros"], wallet: order["requested_micros"]},
                    )
                    await session.execute(update(cash_fiat_orders).where(
                        cash_fiat_orders.c.id == order["id"]
                    ).values(status="credited", detail=reason, updated_at=now))
                values = {
                    "status": "processed", "fiat_order_id": order["id"], "processed_at": now,
                    "detail": ("operator " + decision + ": " + reason.strip())[:500],
                }
                await session.execute(update(cash_fiat_events).where(
                    cash_fiat_events.c.provider == PROVIDER,
                    cash_fiat_events.c.event_id == event["event_id"],
                ).values(**values))
                after = before | {name: _json(value) for name, value in values.items()
                                  if name in FIAT_EVENT_FIELDS}
                await self._audit(session, operator, order["tenant_id"], "fiat_event.resolve",
                                  "fiat_event", str(event_id), reason, key, fingerprint, before, after)
                return after

    async def close_fiat_order(self, order_id, operator, *, reason, key):
        """Close a stuck order. It never credits: only a partner event moves money."""
        self._require_mutation(operator)
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "fiat_order.close", order_id, reason, {},
                )
                if replay is not None:
                    return replay
                row = (await session.execute(select(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == order_id
                ).with_for_update())).mappings().one_or_none()
                if row is None:
                    raise LookupError("fiat order not found")
                self._require_scope(operator, row["tenant_id"])
                if row["status"] not in {"requesting", "clarifying", "review_required"}:
                    raise ValueError("only a stuck fiat order can be closed by an operator")
                before = _snapshot(row, FIAT_ORDER_FIELDS)
                await session.execute(update(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == order_id
                ).values(status="cancelled", detail=reason, updated_at=self.now()))
                after = before | {"status": "cancelled", "detail": reason}
                await self._audit(session, operator, row["tenant_id"], "fiat_order.close",
                                  "fiat_order", order_id, reason, key, fingerprint, before, after)
                return after

    async def _claim(self, session, operator, key, action, target_id, reason, details):
        if not key or len(key) > 200:
            raise ValueError("invalid idempotency key")
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
            raise ValueError("operator reason must contain 3 to 500 characters")
        payload = {"action": action, "target_id": target_id, "reason": reason.strip(), **details}
        fingerprint = _fingerprint(payload)
        await session.execute(text(
            "SELECT pg_advisory_xact_lock(hashtextextended(:request, 0))"
        ), {"request": f"cash-admin:{operator.id}:{key}"})
        existing = (await session.execute(select(cash_audit_events).where(
            cash_audit_events.c.operator_id == operator.id,
            cash_audit_events.c.idempotency_key == key,
        ))).mappings().first()
        if existing:
            if existing["request_hash"] != fingerprint:
                raise IdempotencyConflict("same operator key with different content")
            self._require_scope(operator, existing["tenant_id"])
            return dict(existing["after_json"]), fingerprint
        return None, fingerprint

    async def _audit(self, session, operator, tenant_id, action, target_type, target_id,
                     reason, key, fingerprint, before, after):
        await session.execute(cash_audit_events.insert().values(
            id=uuid4().hex, operator_id=operator.id,
            actor_telegram_user_id=operator.telegram_user_id, tenant_id=tenant_id,
            action=action, target_type=target_type, target_id=target_id,
            reason=reason.strip(), idempotency_key=key, request_hash=fingerprint,
            before_json=before, after_json=after,
        ))

    async def _withdrawal(self, session, withdrawal_id):
        row = (await session.execute(select(cash_withdrawals).where(
            cash_withdrawals.c.id == withdrawal_id
        ).with_for_update())).mappings().one_or_none()
        if row is None:
            raise LookupError("withdrawal not found")
        return row

    async def _account(self, session, kind, user_id, reference_id):
        account_id = f"cash-{kind}-{reference_id}"
        await session.execute(insert(cash_accounts).values(
            id=account_id, kind=kind, user_id=user_id, reference_id=reference_id,
        ).on_conflict_do_nothing(index_elements=[cash_accounts.c.kind, cash_accounts.c.reference_id]))
        return await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == kind, cash_accounts.c.reference_id == reference_id,
        ))
