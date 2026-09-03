from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from cash.holds import assert_not_frozen
from cash.amounts import micros_to_units, micros_to_usdt, usdt_to_micros
from cash.ledger import CashLedger, IdempotencyConflict
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, MOCK_USDT_CONTRACT, TransferEvent
from online.schema import cash_accounts, cash_deposits, cash_payment_events


class DepositUnavailable(ValueError):
    pass


def _hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class DepositService:
    MIN = 1_000_000
    # A C2C deposit is not capped by policy: the chain does not care and an
    # incoming transfer costs us nothing to receive. It is still bounded,
    # because the ceiling is what the uniqueness nudge below searches within --
    # two pending deposits are told apart by their exact amount, so the range
    # has to be finite. 100_000 USDT is past anything a pilot will see.
    MAX = 100_000_000_000
    STEP = 10_000

    def __init__(self, session_factory, *, ledger=None, now=None,
                 address=None, contract=None):
        self.sessions = session_factory
        self.ledger = ledger or CashLedger()
        self.now = now or (lambda: datetime.now(timezone.utc))
        # One receiving address, and the one token that counts as a deposit on
        # it. Defaults keep the mock contour unchanged.
        self.address = address or MOCK_ADDRESS
        self.contract = contract or MOCK_USDT_CONTRACT

    async def create(self, *, user_id: str, tenant_id: str, amount_usdt: str, request_key: str):
        amount = usdt_to_micros(amount_usdt)
        if not self.MIN <= amount <= self.MAX:
            raise ValueError("deposit amount must be between 1 and 100000 USDT")
        if not request_key or len(request_key) > 200:
            raise ValueError("invalid request key")
        fingerprint = _hash({"amount_micros": amount, "tenant_id": tenant_id})
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                if session.get_bind().dialect.name != "postgresql":
                    raise ValueError("cash deposits require PostgreSQL")
                await assert_not_frozen(session, user_id)
                await session.execute(text("LOCK TABLE cash_deposits IN SHARE ROW EXCLUSIVE MODE"))
                existing = (await session.execute(select(cash_deposits).where(
                    cash_deposits.c.user_id == user_id,
                    cash_deposits.c.request_key == request_key,
                ))).mappings().first()
                if existing:
                    if existing["request_hash"] != fingerprint:
                        raise IdempotencyConflict("same deposit key with different content")
                    return dict(existing)
                used = set((await session.execute(select(cash_deposits.c.expected_micros).where(
                    cash_deposits.c.destination_address == self.address,
                    cash_deposits.c.expected_micros.between(amount, min(amount + 9 * self.STEP, self.MAX)),
                ))).scalars())
                expected = next((amount + offset * self.STEP for offset in range(10)
                                 if amount + offset * self.STEP <= self.MAX
                                 and amount + offset * self.STEP not in used), None)
                if expected is None:
                    raise DepositUnavailable("no unique deposit amount is available")
                deposit_id = uuid4().hex
                await session.execute(cash_deposits.insert().values(
                    id=deposit_id, user_id=user_id, tenant_id=tenant_id,
                    request_key=request_key, request_hash=fingerprint,
                    network=MOCK_NETWORK, token_contract=self.contract,
                    destination_address=self.address, requested_micros=amount,
                    expected_micros=expected, status="created", expires_at=now + timedelta(minutes=30),
                    created_at=now, updated_at=now,
                ))
                await session.execute(update(cash_deposits).where(cash_deposits.c.id == deposit_id).values(
                    status="awaiting_transfer", updated_at=now,
                ))
                row = (await session.execute(select(cash_deposits).where(
                    cash_deposits.c.id == deposit_id))).mappings().one()
                return dict(row)

    async def expire_due(self):
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                result = await session.execute(update(cash_deposits).where(
                    cash_deposits.c.status == "awaiting_transfer",
                    cash_deposits.c.expires_at < now,
                ).values(status="expired", updated_at=now).returning(cash_deposits.c.id))
                return len(result.all())

    async def get(self, deposit_id: str, user_id: str):
        async with self.sessions() as session:
            row = (await session.execute(select(cash_deposits).where(
                cash_deposits.c.id == deposit_id, cash_deposits.c.user_id == user_id,
            ))).mappings().first()
            return dict(row) if row else None

    async def cancel(self, deposit_id: str, user_id: str):
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                row = (await session.execute(select(cash_deposits).where(
                    cash_deposits.c.id == deposit_id, cash_deposits.c.user_id == user_id,
                ).with_for_update())).mappings().first()
                if row is None:
                    return None
                if row["status"] in {"created", "awaiting_transfer"}:
                    await session.execute(update(cash_deposits).where(cash_deposits.c.id == deposit_id).values(
                        status="cancelled", updated_at=now,
                    ))
                    row = dict(row); row["status"] = "cancelled"; row["updated_at"] = now
                return dict(row)

    async def observe(self, event: TransferEvent, *, process: bool = True):
        event.validate()
        payload = {
            "tx_hash": event.tx_hash, "event_index": event.event_index, "network": event.network,
            "token_contract": event.token_contract, "destination_address": event.destination_address,
            "amount_micros": event.amount_micros, "occurred_at": event.occurred_at.isoformat(),
        }
        fingerprint = _hash(payload)
        async with self.sessions() as session:
            async with session.begin():
                claimed = await session.scalar(insert(cash_payment_events).values(
                    id=uuid4().hex, provider=event.provider, external_event_id=event.external_event_id,
                    event_hash=fingerprint, tx_hash=event.tx_hash, event_index=event.event_index,
                    network=event.network, token_contract=event.token_contract,
                    destination_address=event.destination_address, amount_micros=event.amount_micros,
                    occurred_at=event.occurred_at, status="observed", detail_json={},
                ).on_conflict_do_nothing().returning(cash_payment_events.c.id))
                existing = (await session.execute(select(cash_payment_events).where(
                    cash_payment_events.c.provider == event.provider,
                    cash_payment_events.c.external_event_id == event.external_event_id,
                ).with_for_update())).mappings().first()
                if existing is None:
                    existing = (await session.execute(select(cash_payment_events).where(
                        cash_payment_events.c.provider == event.provider,
                        cash_payment_events.c.tx_hash == event.tx_hash,
                        cash_payment_events.c.event_index == event.event_index,
                    ).with_for_update())).mappings().one()
                if existing["event_hash"] != fingerprint:
                    raise IdempotencyConflict("same payment event key with different content")
                if process and existing["status"] == "observed":
                    await self._process(session, existing)
                final = (await session.execute(select(cash_payment_events).where(
                    cash_payment_events.c.id == existing["id"]))).mappings().one()
                return dict(final)

    async def _process(self, session, event):
        now = self.now()
        candidates = (await session.execute(select(cash_deposits).where(
            cash_deposits.c.destination_address == event["destination_address"],
            cash_deposits.c.expected_micros == event["amount_micros"],
        ).with_for_update())).mappings().all()
        deposit = candidates[0] if len(candidates) == 1 else None
        valid = deposit is not None and deposit["status"] == "awaiting_transfer" and (
            event["network"] == deposit["network"]
            and event["token_contract"] == deposit["token_contract"]
            and deposit["created_at"] <= event["occurred_at"] <= deposit["expires_at"]
        )
        if not valid:
            detail = "unmatched, invalid, late, or terminal transfer"
            await session.execute(update(cash_payment_events).where(
                cash_payment_events.c.id == event["id"]
            ).values(status="review_required", deposit_id=deposit["id"] if deposit else None,
                     detail_json={"reason": detail}, processed_at=now))
            if deposit and deposit["status"] == "awaiting_transfer":
                await session.execute(update(cash_deposits).where(cash_deposits.c.id == deposit["id"]).values(
                    status="review_required", updated_at=now,
                ))
            return
        await session.execute(update(cash_deposits).where(cash_deposits.c.id == deposit["id"]).values(
            status="confirmed", updated_at=now,
        ))
        wallet_id = await self._account(session, "available", deposit["user_id"], deposit["user_id"])
        clearing_id = await self._account(session, "clearing", None, "c2c-mock")
        await self.ledger.post(
            session, scope="deposit", key=f'{event["provider"]}:{event["external_event_id"]}',
            kind="deposit", reference_id=deposit["id"], actor="mock-trc20-reconciler",
            postings={clearing_id: -event["amount_micros"], wallet_id: event["amount_micros"]},
        )
        await session.execute(update(cash_deposits).where(cash_deposits.c.id == deposit["id"]).values(
            status="credited", updated_at=now,
        ))
        await session.execute(update(cash_payment_events).where(
            cash_payment_events.c.id == event["id"]
        ).values(status="processed", deposit_id=deposit["id"], processed_at=now))

    async def _account(self, session, kind, user_id, reference_id):
        account_id = f"cash-{kind}-{reference_id}"
        await session.execute(insert(cash_accounts).values(
            id=account_id, kind=kind, user_id=user_id, reference_id=reference_id,
        ).on_conflict_do_nothing(index_elements=[cash_accounts.c.kind, cash_accounts.c.reference_id]))
        return await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == kind, cash_accounts.c.reference_id == reference_id,
        ))

    @staticmethod
    def public(row):
        return {
            "id": row["id"], "status": row["status"], "network": row["network"],
            "address": row["destination_address"],
            "requested_usdt": micros_to_usdt(row["requested_micros"]),
            "expected_usdt": micros_to_usdt(row["expected_micros"]),
            "expected_units": micros_to_units(row["expected_micros"]),
            "expires_at": row["expires_at"],
        }
