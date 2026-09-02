from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from cash.amounts import kopecks_to_rub, micros_to_units, micros_to_usdt, usdt_to_micros
from cash.fiat_p2p import quote_with_fee, usdt_micros_to_case8_amount
from cash.ledger import CashLedger, IdempotencyConflict
from online.schema import (
    cash_accounts, cash_fiat_events, cash_fiat_orders, cash_partner_cursors,
)


PROVIDER = "case8-p2p"
# Poker8 keeps its deposit fee here; the partner's own fee is inside its quote.
FEE_ACCOUNT = "case8-p2p-fee"
ACTIVE_STATES = ("requesting", "awaiting_user", "waiting_trader", "clarifying")
# A partner answer that never arrived leaves a row nobody can finish. It stops
# holding the user's one open slot after this, and an operator gets to see it.
LOST_ANSWER_SECONDS = 300


class ActiveFiatOrderExists(Exception):
    """The database allows one open RUB order per user."""


async def fiat_credit_postings(session, order, account):
    """The clearing account pays the whole charge: the quote to the user, the fee to us."""
    wallet = await account(session, "available", order["user_id"], order["user_id"])
    clearing = await account(session, "clearing", None, PROVIDER)
    postings = {
        clearing: -(order["requested_micros"] + order["fee_micros"]),
        wallet: order["requested_micros"],
    }
    if order["fee_micros"]:
        postings[await account(session, "clearing", None, FEE_ACCOUNT)] = order["fee_micros"]
    return postings


def _hash(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class FiatOrderService:
    def __init__(self, session_factory, *, partner, ledger=None, now=None, fee_bps=100):
        self.sessions = session_factory
        self.partner = partner
        self.fee_bps = fee_bps
        self.ledger = ledger or CashLedger()
        self.now = now or (lambda: datetime.now(timezone.utc))

    async def create(self, *, user_id: str, tenant_id: str, amount_usdt: str, request_key: str):
        amount = usdt_to_micros(amount_usdt)
        charged, fee = quote_with_fee(amount, self.fee_bps)
        usdt_micros_to_case8_amount(charged)
        fingerprint = _hash({"amount_micros": amount, "currency": "RUB", "fee_micros": fee})
        now = self.now()
        order_id = uuid4().hex
        await self._release_stale(user_id, now)
        try:
            async with self.sessions() as session:
                async with session.begin():
                    await session.execute(insert(cash_fiat_orders).values(
                        id=order_id, user_id=user_id, tenant_id=tenant_id,
                        request_key=request_key, request_hash=fingerprint,
                        currency="RUB", requested_micros=amount, fee_micros=fee,
                        status="requesting",
                        created_at=now, updated_at=now,
                    ).on_conflict_do_nothing(index_elements=["user_id", "request_key"]))
                    row = await self._by_request_key(session, user_id, request_key)
        except IntegrityError as exc:
            # The unique index over open states rejected a second order. A replay
            # of the same key can land here too, because either index may be the
            # one the database checks first.
            async with self.sessions() as session:
                row = await self._by_request_key(session, user_id, request_key)
            if row is None or row["request_hash"] != fingerprint:
                raise ActiveFiatOrderExists("finish or cancel the open RUB order first") from exc
        if row["request_hash"] != fingerprint:
            raise IdempotencyConflict("same fiat order key with different content")
        if row["status"] != "requesting" or row["id"] != order_id:
            return dict(row)

        partner_order = await self.partner.create_order(charged, "RUB")
        values = {"updated_at": self.now()}
        if partner_order is None:
            values.update(status="unavailable", detail="no trader is currently available")
        else:
            values.update(
                partner_order_id=partner_order.partner_order_id,
                fiat_kopecks=partner_order.fiat_kopecks,
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

    async def purge_requisites(self, before):
        """Trader requisites are payment data and are not kept past retention."""
        async with self.sessions() as session:
            async with session.begin():
                result = await session.execute(update(cash_fiat_orders).where(
                    cash_fiat_orders.c.requisites.is_not(None),
                    cash_fiat_orders.c.created_at < before,
                ).values(requisites=None))
                return result.rowcount or 0

    async def _release_stale(self, user_id, now):
        """Free the user's open slot from orders the partner can no longer finish."""
        async with self.sessions() as session:
            async with session.begin():
                # The user never claimed to have paid, and the quote is dead.
                # CASE8 expires its own side, so there is nothing to notify.
                await session.execute(update(cash_fiat_orders).where(
                    cash_fiat_orders.c.user_id == user_id,
                    cash_fiat_orders.c.status == "awaiting_user",
                    cash_fiat_orders.c.expires_at < now,
                ).values(status="expired", detail="expired before the user confirmed payment", updated_at=now))
                # The /order call never came back, so the partner may hold an
                # order this row cannot name. That is an operator's decision.
                await session.execute(update(cash_fiat_orders).where(
                    cash_fiat_orders.c.user_id == user_id,
                    cash_fiat_orders.c.status == "requesting",
                    cash_fiat_orders.c.created_at < now - timedelta(seconds=LOST_ANSWER_SECONDS),
                ).values(status="review_required", detail="partner answer was lost", updated_at=now))

    @staticmethod
    async def _by_request_key(session, user_id, request_key):
        row = (await session.execute(select(cash_fiat_orders).where(
            cash_fiat_orders.c.user_id == user_id,
            cash_fiat_orders.c.request_key == request_key,
        ))).mappings().first()
        return dict(row) if row else None

    async def active(self, user_id: str):
        """The one open order the database allows, so a reload can resume it."""
        async with self.sessions() as session:
            row = (await session.execute(select(cash_fiat_orders).where(
                cash_fiat_orders.c.user_id == user_id,
                cash_fiat_orders.c.status.in_(ACTIVE_STATES),
            ))).mappings().first()
            return dict(row) if row else None

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
                fingerprint = _hash({
                    "partner_order_id": event.partner_order_id,
                    "status": event.status, "detail": event.detail,
                })
                inserted = await session.scalar(insert(cash_fiat_events).values(
                    provider=PROVIDER, event_id=event.event_id,
                    partner_order_id=event.partner_order_id,
                    event_type=event.status, event_hash=fingerprint,
                    status="observed", detail=event.detail, created_at=now,
                ).on_conflict_do_nothing().returning(cash_fiat_events.c.event_id))
                if inserted is None:
                    # A duplicate is expected and harmless. The same event id
                    # carrying different content is neither: apply nothing and
                    # let an operator decide which delivery was the truth.
                    stored = (await session.execute(select(cash_fiat_events).where(
                        cash_fiat_events.c.provider == PROVIDER,
                        cash_fiat_events.c.event_id == event.event_id,
                    ).with_for_update())).mappings().one()
                    changed = stored["event_hash"] not in (None, fingerprint)
                    if changed and stored["status"] != "review_required":
                        await session.execute(update(cash_fiat_events).where(
                            cash_fiat_events.c.provider == PROVIDER,
                            cash_fiat_events.c.event_id == event.event_id,
                        ).values(
                            status="review_required", processed_at=now,
                            detail=f"partner redelivered event {event.event_id} as {event.status}"[:500],
                        ))
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
                    await self.ledger.post(
                        session, scope="fiat-deposit", key=f"{PROVIDER}:{event.event_id}",
                        kind="deposit", reference_id=order["id"], actor="case8-p2p-reconciler",
                        postings=await fiat_credit_postings(session, order, self._account),
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

    @staticmethod
    def public(row):
        return {
            "id": row["id"], "status": row["status"], "currency": row["currency"],
            "requested_usdt": micros_to_usdt(row["requested_micros"]),
            "requested_units": micros_to_units(row["requested_micros"]),
            "fee_usdt": micros_to_usdt(row["fee_micros"]),
            "charged_usdt": micros_to_usdt(row["requested_micros"] + row["fee_micros"]),
            "fiat_kopecks": row["fiat_kopecks"],
            "fiat_rub": None if row["fiat_kopecks"] is None else kopecks_to_rub(row["fiat_kopecks"]),
            "requisites": row["requisites"],
            "trader_username": row["trader_username"], "detail": row["detail"],
            "expires_at": row["expires_at"],
        }
