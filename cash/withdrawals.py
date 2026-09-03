from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from cash.holds import assert_not_frozen
from cash.amounts import kopecks_to_rub, micros_to_units, micros_to_usdt, usdt_to_micros
from cash.ledger import CashLedger, IdempotencyConflict
from cash.trc20 import MOCK_NETWORK
from online.schema import cash_accounts, cash_withdrawals


#: House revenue, kept as a clearing account beside the fiat deposit fee.
FEE_ACCOUNT = "withdrawal-fee"

#: The two ways money leaves. TRC20 is executed by a payout provider; P2P_RUB is
#: paid by an operator out of band, exactly as CASE8 does it, and therefore has
#: no executor at all -- the operator is the executor.
TRC20 = MOCK_NETWORK
P2P_RUB = "P2P_RUB"
RAILS = (TRC20, P2P_RUB)

#: Where a paid-out P2P payout lands, beside the C2C clearing account.
P2P_CLEARING = "p2p-payout"

#: A withdrawal that has not finished one way or the other. One of these per
#: user at a time, so a queue of payouts cannot be built up faster than the
#: operator reviewing them.
ACTIVE_STATES = ("requested", "reserved", "approved", "sending", "submitted", "unknown")


class ActiveWithdrawalExists(ValueError):
    """One payout at a time: the database says so, not just this service."""


class WithdrawalStateError(ValueError):
    pass


def _hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MockPayoutExecutor:
    def send(self, payout_id: str, outcome: str):
        if outcome == "success":
            return {"status": "submitted", "tx_hash": f"mock-{payout_id}"}
        if outcome == "failure":
            return {"status": "rejected", "detail": "mock payout rejected"}
        if outcome == "unknown":
            return {"status": "unknown", "detail": "mock payout outcome unknown"}
        raise ValueError("mock outcome must be success, failure, or unknown")


class WithdrawalService:
    MIN = 10_000
    # Matches the C2C deposit ceiling. They have to agree: capped lower, a
    # player who deposited 500 USDT had to take it out in five payouts and pay
    # the flat fee five times. Nothing here is automatic -- create() only
    # reserves, and no payout leaves without an operator moving it through
    # approve() first -- so the ceiling bounds one approved payout, not a
    # self-service withdrawal of that size.
    MAX = 100_000_000_000

    def __init__(self, session_factory, *, ledger=None, executor=None, now=None,
                 fee_micros: int = 0):
        self.sessions = session_factory
        self.ledger = ledger or CashLedger()
        self.executor = executor or MockPayoutExecutor()
        self.now = now or (lambda: datetime.now(timezone.utc))
        if type(fee_micros) is not int or fee_micros < 0:
            raise ValueError("the withdrawal fee must be a nonnegative integer of micros")
        self.fee_micros = fee_micros

    async def create(self, *, user_id: str, tenant_id: str, amount_usdt: str,
                     destination_address: str, request_key: str, rail: str = TRC20):
        if rail not in RAILS:
            raise ValueError(f"withdrawal rail must be one of {', '.join(RAILS)}")
        amount = usdt_to_micros(amount_usdt)
        if not self.MIN <= amount <= self.MAX:
            raise ValueError("withdrawal amount must be between 0.01 and 100000 USDT")
        # A payout costs real money to send on chain. Below the fee the request
        # is not a small withdrawal, it is a way to make us pay for a transfer
        # of nothing, so the floor is the fee rather than a second constant.
        if amount <= self.fee_micros:
            raise ValueError(
                f"withdrawal must exceed the {micros_to_usdt(self.fee_micros)} USDT payout fee"
            )
        if not destination_address or len(destination_address) > 128:
            raise ValueError("invalid destination address")
        if not request_key or len(request_key) > 200:
            raise ValueError("invalid request key")
        fingerprint = _hash({"amount_micros": amount, "address": destination_address,
                             "network": rail, "tenant_id": tenant_id,
                             "fee_micros": self.fee_micros})
        now = self.now()
        try:
            return await self._reserve(
                user_id=user_id, tenant_id=tenant_id, amount=amount, rail=rail,
                destination_address=destination_address, request_key=request_key,
                fingerprint=fingerprint, now=now,
            )
        except IntegrityError as exc:
            # The partial unique index got there first. Only the database can
            # settle a race between two different request keys, so the friendly
            # error is reconstructed here rather than trusted to the check above.
            async with self.sessions() as session:
                replay = (await session.execute(select(cash_withdrawals).where(
                    cash_withdrawals.c.user_id == user_id,
                    cash_withdrawals.c.request_key == request_key,
                ))).mappings().first()
            if replay is not None and replay["request_hash"] == fingerprint:
                return dict(replay)
            raise ActiveWithdrawalExists("finish or cancel the open withdrawal first") from exc

    async def _reserve(self, *, user_id, tenant_id, amount, rail, destination_address,
                       request_key, fingerprint, now):
        async with self.sessions() as session:
            async with session.begin():
                if session.get_bind().dialect.name != "postgresql":
                    raise ValueError("cash withdrawals require PostgreSQL")
                # Serialize only identical user request keys. Different requests
                # still run concurrently and meet at the wallet row lock.
                await assert_not_frozen(session, user_id)
                await session.execute(text(
                    "SELECT pg_advisory_xact_lock(hashtextextended(:request, 0))"
                ), {"request": f"cash-withdrawal:{user_id}:{request_key}"})
                existing = (await session.execute(select(cash_withdrawals).where(
                    cash_withdrawals.c.user_id == user_id,
                    cash_withdrawals.c.request_key == request_key,
                ).with_for_update())).mappings().first()
                if existing:
                    if existing["request_hash"] != fingerprint:
                        raise IdempotencyConflict("same withdrawal key with different content")
                    return dict(existing)
                withdrawal_id = uuid4().hex
                reserve_id = await self._account(session, "withdrawal", user_id, withdrawal_id)
                wallet_id = await self._account(session, "available", user_id, user_id)
                live = await session.scalar(select(cash_withdrawals.c.id).where(
                    cash_withdrawals.c.user_id == user_id,
                    cash_withdrawals.c.status.in_(ACTIVE_STATES),
                ))
                if live is not None:
                    raise ActiveWithdrawalExists(
                        "finish or cancel the open withdrawal first"
                    )
                await session.execute(cash_withdrawals.insert().values(
                    id=withdrawal_id, user_id=user_id, tenant_id=tenant_id,
                    request_key=request_key, request_hash=fingerprint, network=rail,
                    destination_address=destination_address, amount_micros=amount,
                    fee_micros=self.fee_micros, reserve_account_id=reserve_id,
                    payout_id=uuid4().hex,
                    status="requested", updated_at=now,
                ))
                await self.ledger.post(
                    session, scope="withdrawal-reserve", key=withdrawal_id, kind="reserve",
                    reference_id=withdrawal_id, actor=user_id,
                    postings={wallet_id: -amount, reserve_id: amount},
                )
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(status="reserved", updated_at=now))
                row = (await session.execute(select(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id))).mappings().one()
                return dict(row)

    async def settle_p2p(self, withdrawal_id: str, *, fiat_kopecks: int, actor: str,
                         detail: str | None = None):
        """Record a RUB payout a person made by hand, outside this system.

        There is no executor to call and nothing to poll: the operator has
        already sent the money, so this writes down what they sent and moves the
        reserve out. The USDT debit stays the authoritative amount; the kopecks
        are the receipt beside it.
        """
        if type(fiat_kopecks) is not int or fiat_kopecks <= 0:
            raise ValueError("a P2P payout must record the RUB actually sent, in kopecks")
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                row = (await session.execute(select(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).with_for_update())).mappings().one_or_none()
                if row is None:
                    return None
                if row["network"] != P2P_RUB:
                    raise WithdrawalStateError("only a P2P payout is settled by hand")
                if row["status"] in {"submitted", "confirmed"}:
                    return dict(row)
                if row["status"] != "approved":
                    raise WithdrawalStateError("only an approved payout can be recorded as paid")
                fee = row["fee_micros"]
                clearing = await self._account(session, "clearing", None, P2P_CLEARING)
                postings = {row["reserve_account_id"]: -row["amount_micros"],
                            clearing: row["amount_micros"] - fee}
                if fee:
                    postings[await self._account(session, "clearing", None, FEE_ACCOUNT)] = fee
                await self.ledger.post(
                    session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                    reference_id=withdrawal_id, actor=actor, postings=postings,
                )
                values = {"status": "submitted", "fiat_kopecks": fiat_kopecks,
                          "detail": detail, "submitted_at": now, "updated_at": now}
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(**values))
                return dict(row) | values

    async def get(self, withdrawal_id: str, user_id: str | None = None):
        conditions = [cash_withdrawals.c.id == withdrawal_id]
        if user_id is not None:
            conditions.append(cash_withdrawals.c.user_id == user_id)
        async with self.sessions() as session:
            row = (await session.execute(select(cash_withdrawals).where(*conditions))).mappings().first()
            return dict(row) if row else None

    async def cancel(self, withdrawal_id: str, user_id: str):
        return await self._release(withdrawal_id, "cancelled", user_id=user_id)

    async def reject(self, withdrawal_id: str, detail="mock payout rejected"):
        return await self._release(withdrawal_id, "rejected", detail=detail)

    async def _release(self, withdrawal_id, status, *, user_id=None, detail=None):
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                conditions = [cash_withdrawals.c.id == withdrawal_id]
                if user_id is not None:
                    conditions.append(cash_withdrawals.c.user_id == user_id)
                row = (await session.execute(select(cash_withdrawals).where(*conditions).with_for_update())).mappings().first()
                if row is None:
                    return None
                if row["status"] in {"cancelled", "rejected"}:
                    return dict(row)
                if row["status"] not in {"requested", "reserved", "approved"}:
                    raise WithdrawalStateError("withdrawal can no longer release its reserve")
                wallet_id = await self._account(session, "available", row["user_id"], row["user_id"])
                await self.ledger.post(
                    session, scope="withdrawal-release", key=withdrawal_id, kind="release",
                    reference_id=withdrawal_id, actor=user_id or "mock-operator",
                    postings={row["reserve_account_id"]: -row["amount_micros"], wallet_id: row["amount_micros"]},
                )
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(status=status, detail=detail, updated_at=now))
                result = dict(row); result.update(status=status, detail=detail, updated_at=now)
                return result

    async def approve(self, withdrawal_id: str):
        return await self._transition(withdrawal_id, {"reserved"}, "approved")

    async def execute(self, withdrawal_id: str, outcome: str):
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                row = (await session.execute(select(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).with_for_update())).mappings().one_or_none()
                if row is None:
                    return None
                if row["status"] in {"submitted", "confirmed", "rejected", "unknown"}:
                    return dict(row)
                if row["network"] != TRC20:
                    raise WithdrawalStateError(
                        "a P2P payout is settled by an operator, not by a payout provider"
                    )
                if row["status"] != "approved":
                    raise WithdrawalStateError("withdrawal is not approved")
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(status="sending", updated_at=now))
                result = self.executor.send(row["payout_id"], outcome)
                if result["status"] == "submitted":
                    clearing_id = await self._account(session, "clearing", None, "c2c-mock")
                    # The fee is realised here and nowhere earlier: a cancelled
                    # or rejected withdrawal refunds the whole reserve, because
                    # nothing was sent and nothing was spent.
                    fee = row["fee_micros"]
                    postings = {row["reserve_account_id"]: -row["amount_micros"],
                                clearing_id: row["amount_micros"] - fee}
                    if fee:
                        postings[await self._account(
                            session, "clearing", None, FEE_ACCOUNT
                        )] = fee
                    await self.ledger.post(
                        session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                        reference_id=withdrawal_id, actor="mock-payout-executor",
                        postings=postings,
                    )
                    values = {"status": "submitted", "tx_hash": result["tx_hash"],
                              "submitted_at": now, "updated_at": now}
                elif result["status"] == "unknown":
                    values = {"status": "unknown", "detail": result["detail"], "updated_at": now}
                else:
                    wallet_id = await self._account(session, "available", row["user_id"], row["user_id"])
                    await self.ledger.post(
                        session, scope="withdrawal-release", key=withdrawal_id, kind="release",
                        reference_id=withdrawal_id, actor="mock-payout-executor",
                        postings={row["reserve_account_id"]: -row["amount_micros"],
                                  wallet_id: row["amount_micros"]},
                    )
                    values = {"status": "rejected", "detail": result["detail"], "updated_at": now}
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(**values))
                final = dict(row); final.update(values)
                return final

    async def confirm(self, withdrawal_id: str):
        return await self._transition(withdrawal_id, {"submitted"}, "confirmed", confirmed_at=self.now())

    async def _transition(self, withdrawal_id, allowed, status, **extra):
        now = self.now()
        async with self.sessions() as session:
            async with session.begin():
                row = (await session.execute(select(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).with_for_update())).mappings().one_or_none()
                if row is None:
                    return None
                if row["status"] == status:
                    return dict(row)
                if row["status"] not in allowed:
                    raise WithdrawalStateError(f"cannot change {row['status']} to {status}")
                values = {"status": status, "updated_at": now, **extra}
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(**values))
                result = dict(row); result.update(values); return result

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
        return {"id": row["id"], "status": row["status"], "network": row["network"],
                "address": row["destination_address"],
                "amount_usdt": micros_to_usdt(row["amount_micros"]),
                "amount_units": micros_to_units(row["amount_micros"]),
                "fee_usdt": micros_to_usdt(row["fee_micros"]),
                # What actually leaves: the debit minus the fee.
                "payout_usdt": micros_to_usdt(row["amount_micros"] - row["fee_micros"]),
                "fiat_rub": kopecks_to_rub(row["fiat_kopecks"]) if row["fiat_kopecks"] else None,
                "tx_hash": row["tx_hash"]}
