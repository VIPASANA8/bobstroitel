from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cash.amounts import MAX_MICROS
from online.schema import cash_accounts, cash_entries, cash_transactions


class InsufficientCash(ValueError):
    pass


class IdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True)
class CashReceipt:
    transaction_id: str
    created: bool


def _identifier(value: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("invalid cash operation identifier")


class CashLedger:
    ASSET = "CASH_USDT"
    KINDS = {"deposit", "reserve", "release", "settlement", "payout", "adjustment"}

    async def post(
        self, session: AsyncSession, *, scope: str, key: str, kind: str,
        reference_id: str, actor: str, postings: Mapping[str, int],
    ) -> CashReceipt:
        """Post inside the caller's transaction; never authenticate an external event."""
        if session.get_bind().dialect.name != "postgresql":
            raise ValueError("cash posting requires PostgreSQL row locks")
        if not session.in_transaction():
            raise ValueError("cash posting requires the caller's transaction")
        for value, limit in ((scope, 64), (key, 200), (reference_id, 100), (actor, 100)):
            _identifier(value, limit)
        if not isinstance(kind, str) or kind not in self.KINDS:
            raise ValueError("invalid cash operation kind")
        if not isinstance(postings, Mapping) or len(postings) < 2:
            raise ValueError("cash postings must contain at least two accounts")
        amounts = dict(postings)
        for account_id, amount in amounts.items():
            _identifier(account_id, 64)
            if type(amount) is not int or amount == 0 or abs(amount) > MAX_MICROS:
                raise ValueError("cash postings require nonzero signed integer micros in range")
        if sum(amounts.values()) != 0:
            raise ValueError("cash postings must balance to zero")
        payload = json.dumps(
            {"kind": kind, "reference_id": reference_id, "actor": actor, "postings": sorted(amounts.items())},
            sort_keys=True, separators=(",", ":"),
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        # A failed operation must not poison a caller that catches the error.
        # The outer transaction still owns commit/rollback of its workflow.
        async with session.begin_nested():
            transaction_id = uuid4().hex
            claimed = await session.scalar(
                insert(cash_transactions).values(
                    id=transaction_id, scope=scope, idempotency_key=key,
                    request_hash=fingerprint, kind=kind,
                    reference_id=reference_id, actor=actor,
                )
                .on_conflict_do_nothing(index_elements=["scope", "idempotency_key"])
                .returning(cash_transactions.c.id)
            )
            if claimed is None:
                existing = (await session.execute(
                    select(cash_transactions.c.id, cash_transactions.c.request_hash).where(
                        cash_transactions.c.scope == scope,
                        cash_transactions.c.idempotency_key == key,
                    )
                )).mappings().one()
                if existing["request_hash"] != fingerprint:
                    raise IdempotencyConflict("same cash key with different content")
                return CashReceipt(existing["id"], False)

            ids = sorted(amounts)
            accounts = (await session.execute(
                select(cash_accounts)
                .where(cash_accounts.c.id.in_(ids))
                .order_by(cash_accounts.c.id)
                .with_for_update()
            )).mappings().all()
            if len(accounts) != len(ids):
                raise ValueError("unknown cash account")
            updated = {}
            for account in accounts:
                balance = int(account["balance_micros"]) + amounts[account["id"]]
                if not -MAX_MICROS <= balance <= MAX_MICROS:
                    raise ValueError("cash balance exceeds supported range")
                if account["kind"] != "clearing" and balance < 0:
                    raise InsufficientCash("insufficient available or reserved cash")
                updated[account["id"]] = balance

            await session.execute(cash_entries.insert(), [
                {"transaction_id": transaction_id, "account_id": account_id, "amount_micros": amounts[account_id]}
                for account_id in ids
            ])
            for account_id in ids:
                await session.execute(
                    update(cash_accounts).where(cash_accounts.c.id == account_id)
                    .values(balance_micros=updated[account_id])
                )
            return CashReceipt(transaction_id, True)
