from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from cash.amounts import usdt_to_micros
from cash.fiat_p2p import usdt_micros_to_case8_amount
from cash.ledger import CashLedger, IdempotencyConflict
from online.schema import (
    cash_accounts, cash_fiat_events, cash_fiat_orders, cash_partner_cursors,
)


PROVIDER = "case8-p2p"


def _hash(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class FiatOrderService:
    def __init__(self, session_factory, *, partner, ledger=None, now=None):
        self.sessions = session_factory
        self.partner = partner
        self.ledger = ledger or CashLedger()
        self.now = now or (lambda: datetime.now(timezone.utc))

    async def create(self, *, user_id: str, tenant_id: str, amount_usdt: str, request_key: str):
        amount = usdt_to_micros(amount_usdt)
        usdt_micros_to_case8_amount(amount)
        fingerprint = _hash({"amount_micros": amount, "currency": "RUB"})
        now = self.now()
        order_id = uuid4().hex
        async with self.sessions() as session:
            async with session.begin():
                await session.execute(insert(cash_fiat_orders).values(
                    id=order_id, user_id=user_id, tenant_id=tenant_id,
                    request_key=request_key, request_hash=fingerprint,
                    currency="RUB", requested_micros=amount, status="requesting",
                    created_at=now, updated_at=now,
                ).on_conflict_do_nothing(index_elements=["user_id", "request_key"]))
                row = (await session.execute(select(cash_fiat_orders).where(
                    cash_fiat_orders.c.user_id == user_id,
                    cash_fiat_orders.c.request_key == request_key,
                ))).mappings().one()
                if row["request_hash"] != fingerprint:
                    raise IdempotencyConflict("same fiat order key with different content")
                if row["status"] != "requesting" or row["id"] != order_id:
                    return dict(row)

        partner_order = await self.partner.create_order(amount, "RUB")
        values = {"updated_at": self.now()}
        if partner_order is None:
            values.update(status="unavailable", detail="no trader is currently available")
        else:
            values.update(
                partner_order_id=partner_order.partner_order_id,
                fiat_amount=partner_order.fiat_amount,
                requisites=partner_order.requisites,
                trader_username=partner_order.trader_username,
                expires_at=partner_order.expires_at,
                status="awaiting_user",
            )
        async with self.sessions() as session:
            async with session.begin():
                await session.execute(update(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == order_id,
                    cash_fiat_orders.c.status == "requesting",
                ).values(**values))
                row = (await session.execute(select(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == order_id,
                ))).mappings().one()
                return dict(row)

    async def get(self, order_id: str, user_id: str):
        async with self.sessions() as session:
            row = (await session.execute(select(cash_fiat_orders).where(
                cash_fiat_orders.c.id == order_id,
                cash_fiat_orders.c.user_id == user_id,
            ))).mappings().first()
            return dict(row) if row else None

    async def mark_paid(self, order_id: str, user_id: str):
        row = await self.get(order_id, user_id)
        if row is None:
            return None
        if row["status"] == "waiting_trader":
            return row
        if row["status"] != "awaiting_user":
            raise ValueError("fiat order cannot be marked paid in its current state")
        await self.partner.notify(row["partner_order_id"], cancel=False)
        return await self._set_user_state(order_id, user_id, "awaiting_user", "waiting_trader")

    async def cancel(self, order_id: str, user_id: str):
        row = await self.get(order_id, user_id)
        if row is None:
            return None
        if row["status"] == "cancelled":
            return row
        if row["status"] not in {"awaiting_user", "waiting_trader", "clarifying"}:
            raise ValueError("fiat order cannot be cancelled in its current state")
        await self.partner.notify(row["partner_order_id"], cancel=True)
        return await self._set_user_state(order_id, user_id, row["status"], "cancelled")

    async def _set_user_state(self, order_id, user_id, previous, status):
        async with self.sessions() as session:
            async with session.begin():
                await session.execute(update(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == order_id,
                    cash_fiat_orders.c.user_id == user_id,
                    cash_fiat_orders.c.status == previous,
                ).values(status=status, updated_at=self.now()))
                row = (await session.execute(select(cash_fiat_orders).where(
                    cash_fiat_orders.c.id == order_id,
                    cash_fiat_orders.c.user_id == user_id,
                ))).mappings().one()
                return dict(row)

    async def poll_once(self):
        async with self.sessions() as session:
            offset = await session.scalar(select(cash_partner_cursors.c.offset).where(
                cash_partner_cursors.c.provider == PROVIDER,
            )) or 0
        events, next_offset = await self.partner.poll_events(offset)
        for event in events:
            await self._process_event(event)
        if next_offset != offset:
            async with self.sessions() as session:
                async with session.begin():
                    await session.execute(insert(cash_partner_cursors).values(
                        provider=PROVIDER, offset=next_offset, updated_at=self.now(),
                    ).on_conflict_do_update(
                        index_elements=["provider"],
                        set_={"offset": next_offset, "updated_at": self.now()},
                    ))
        return len(events)

    async def _process_event(self, event):
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                inserted = await session.scalar(insert(cash_fiat_events).values(
                    provider=PROVIDER, event_id=event.event_id,
                    partner_order_id=event.partner_order_id,
                    event_type=event.status, status="observed", detail=event.detail,
                    created_at=now,
                ).on_conflict_do_nothing().returning(cash_fiat_events.c.event_id))
                if inserted is None:
                    return
                order = (await session.execute(select(cash_fiat_orders).where(
                    cash_fiat_orders.c.partner_order_id == event.partner_order_id,
                ).with_for_update())).mappings().first()
                if order is None:
                    await session.execute(update(cash_fiat_events).where(
                        cash_fiat_events.c.provider == PROVIDER,
                        cash_fiat_events.c.event_id == event.event_id,
                    ).values(status="review_required", detail="unknown partner order", processed_at=now))
                    return
                event_values = {"fiat_order_id": order["id"], "status": "processed", "processed_at": now}
                terminal = order["status"] in {"credited", "expired", "cancelled", "review_required"}
                if event.status == "completed" and not terminal:
                    wallet = await self._account(session, "available", order["user_id"], order["user_id"])
                    clearing = await self._account(session, "clearing", None, PROVIDER)
                    await self.ledger.post(
                        session, scope="fiat-deposit", key=f"{PROVIDER}:{event.event_id}",
                        kind="deposit", reference_id=order["id"], actor="case8-p2p-reconciler",
                        postings={clearing: -order["requested_micros"], wallet: order["requested_micros"]},
                    )
                    await session.execute(update(cash_fiat_orders).where(
                        cash_fiat_orders.c.id == order["id"],
                    ).values(status="credited", updated_at=now))
                elif event.status in {"expired", "cancelled"} and order["status"] != "credited":
                    await session.execute(update(cash_fiat_orders).where(
                        cash_fiat_orders.c.id == order["id"],
                    ).values(status=event.status, detail=event.detail, updated_at=now))
                elif event.status == "clarifying" and not terminal:
                    await session.execute(update(cash_fiat_orders).where(
                        cash_fiat_orders.c.id == order["id"],
                    ).values(status="clarifying", detail=event.detail, updated_at=now))
                elif event.status == "completed":
                    event_values.update(status="review_required", detail="completion for terminal order")
                await session.execute(update(cash_fiat_events).where(
                    cash_fiat_events.c.provider == PROVIDER,
                    cash_fiat_events.c.event_id == event.event_id,
                ).values(**event_values))

    @staticmethod
    async def _account(session, kind, user_id, reference_id):
        account_id = f"cash-{kind}-{reference_id}"
        await session.execute(insert(cash_accounts).values(
            id=account_id, kind=kind, user_id=user_id, reference_id=reference_id,
        ).on_conflict_do_nothing(index_elements=["kind", "reference_id"]))
        return await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == kind,
            cash_accounts.c.reference_id == reference_id,
        ))
