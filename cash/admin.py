from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from cash.access import CashOperator
from cash.antifraud import cancelled_after_payment
from cash.amounts import micros_to_units, micros_to_usdt
from cash.cube import CUBE_ACCOUNT
from cash.fiat_orders import fiat_credit_postings
from cash.fiat_reconciliation import daily_fiat_reconciliation
from cash.game import RAKE_ACCOUNT
from cash.ledger import CashLedger, IdempotencyConflict
from cash.withdrawals import (
    FEE_ACCOUNT, MockPayoutExecutor, P2P_CLEARING, P2P_RUB, TRC20, WithdrawalStateError,
)
from online.catalogue import CASH_USDT
from online.schema import (
    cash_accounts, cash_audit_events, cash_deposits, cash_payment_events,
    cash_fiat_events, cash_fiat_orders, cash_user_holds, cash_withdrawals, cube_adjustments,
    cube_rounds, partner_settlements, partner_shares, poker_tables, referral_settlements,
    referrals, table_runtimes, users,
)


#: Where a hand-made correction is booked. A clearing account like the rake and
#: the deposit fee: money appearing on a player's side has to come from
#: somewhere the books can name.
ADJUSTMENT_ACCOUNT = "manual-adjustment"
#: Ten thousand dollars. Not a policy about how much anyone may give away --
#: it is the size at which a slipped decimal point stops being recoverable.
MAX_ADJUSTMENT_MICROS = 10_000 * 1_000_000


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
    "fee_micros", "reserve_account_id", "payout_id", "tx_hash", "fiat_kopecks",
    "status", "detail", "submitted_at", "confirmed_at",
)
EVENT_FIELDS = (
    "id", "provider", "external_event_id", "tx_hash", "event_index", "network",
    "token_contract", "destination_address", "amount_micros", "occurred_at", "status", "deposit_id",
)
FIAT_ORDER_FIELDS = (
    "id", "user_id", "tenant_id", "partner_order_id", "currency", "requested_micros",
    "fee_micros", "fiat_kopecks", "status", "detail", "expires_at",
)
FIAT_EVENT_FIELDS = (
    "provider", "event_id", "partner_order_id", "fiat_order_id", "event_type", "status", "detail",
)
PROVIDER = "case8-p2p"


def _mask(value):
    """Trader requisites are payment data: an operator sees only the tail."""
    return None if not value else "…" + str(value)[-4:]


class CashAdminService:
    def __init__(
        self, session_factory, *, ledger=None, executor=None, now=None, settlements=None,
        mock_rails=True,
    ):
        self.sessions = session_factory
        self.ledger = ledger or CashLedger()
        self.executor = executor or MockPayoutExecutor()
        # Where money is real (Settings.cash_mock_rails is False) the mock
        # payout executor is refused: a "Mock success" there is a fake tx hash
        # on a real debit. An operator who sent USDT by hand records it instead.
        self.mock_rails = mock_rails
        self.now = now or (lambda: datetime.now(timezone.utc))
        # The settlement job, so an operator can take back a reward that has
        # not been released yet. None where referrals are not wired up.
        self.settlements = settlements

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
            # A paid order the trader never answered is stuck too: pservice
            # refuses the user's cancel after "paid", so once the quote is
            # past its window only an operator can close it.
            fiat_order_query = select(cash_fiat_orders).where(
                cash_fiat_orders.c.status.in_(("requesting", "clarifying", "review_required"))
                | ((cash_fiat_orders.c.status == "waiting_trader")
                   & (cash_fiat_orders.c.expires_at < self.now() - timedelta(minutes=30)))
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

    async def overview(self, operator: CashOperator):
        """Where the money is, in one glance.

        The books are not split by tenant -- one clearing account funds every
        one of them -- so this is an admin's view or nobody's.
        """
        if operator.role != "admin":
            raise OperatorAccessDenied("this view belongs to a global admin")
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        async with self.sessions() as session:
            balances = dict((await session.execute(
                select(cash_accounts.c.kind, func.coalesce(func.sum(cash_accounts.c.balance_micros), 0))
                .group_by(cash_accounts.c.kind)
            )).all())
            house = await session.scalar(select(cash_accounts.c.balance_micros).where(
                cash_accounts.c.kind == "clearing",
                cash_accounts.c.reference_id == CUBE_ACCOUNT,
            ))
            rake = await session.scalar(select(cash_accounts.c.balance_micros).where(
                cash_accounts.c.kind == "clearing",
                cash_accounts.c.reference_id == RAKE_ACCOUNT,
            ))
            rounds, staked, paid = (await session.execute(select(
                func.count(),
                func.coalesce(func.sum(cube_rounds.c.stake_micros), 0),
                func.coalesce(func.sum(cube_rounds.c.payout_micros), 0),
            ).where(cube_rounds.c.created_at >= day_ago))).one()
            players = await session.scalar(select(func.count()).select_from(users))
            frozen = await session.scalar(select(func.count()).select_from(cash_user_holds).where(
                (cash_user_holds.c.until.is_(None)) | (cash_user_holds.c.until > func.now())
            ))
        return {
            "players": int(players or 0),
            "frozen": int(frozen or 0),
            "available_micros": int(balances.get("available", 0)),
            "escrow_micros": int(balances.get("escrow", 0)),
            "withdrawal_micros": int(balances.get("withdrawal", 0)),
            "cube_house_micros": int(house or 0),
            "poker_house_micros": int(rake or 0),
            "cube_rounds_day": int(rounds or 0),
            "cube_result_day_micros": int(staked or 0) - int(paid or 0),
        }

    async def adjust_balance(self, identifier, operator, *, amount_micros, reason, key):
        """Put money on a player's balance by hand, or take it off.

        The last resort behind every rail: a deposit that arrived some way the
        system never saw, a goodwill payment after an incident, a correction.
        It is the one place money reaches a player without a payment behind it,
        so it is admin-only, it is booked against a clearing account of its own
        rather than out of thin air, and it carries a named person and a reason
        into the audit log like every other decision.

        A debit cannot push the balance below zero -- the ledger refuses that
        -- so taking back more than is there fails instead of going negative.
        """
        self._require_mutation(operator)
        # Money the clearing account absorbs is not any one tenant's, and a
        # correction that crosses tenants would be invisible to the operator
        # who owns only one of them.
        self._require_scope(operator, None)
        if type(amount_micros) is not int or amount_micros == 0:
            raise ValueError("an adjustment has to move a nonzero amount")
        if abs(amount_micros) > MAX_ADJUSTMENT_MICROS:
            raise ValueError(
                f"one adjustment is capped at {micros_to_usdt(MAX_ADJUSTMENT_MICROS)} USDT"
            )
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "user.adjust", str(identifier), reason,
                    {"amount_micros": amount_micros},
                )
                if replay is not None:
                    return replay
                user = await self._find_user(session, identifier)
                tenant_id = user["acquisition_tenant_id"]
                wallet = await self._account(session, "available", user["id"], user["id"])
                clearing = await self._account(session, "clearing", None, ADJUSTMENT_ACCOUNT)
                before_micros = int(await session.scalar(select(
                    cash_accounts.c.balance_micros
                ).where(cash_accounts.c.id == wallet)) or 0)
                await self.ledger.post(
                    session, scope="cash-adjust", key=key, kind="adjustment",
                    reference_id=user["id"], actor=f"operator:{operator.id}",
                    postings={wallet: amount_micros, clearing: -amount_micros},
                )
                before = {"user_id": user["id"], "available_usdt": micros_to_usdt(before_micros)}
                after = {
                    "user_id": user["id"],
                    "amount_usdt": micros_to_usdt(abs(amount_micros)),
                    "direction": "credit" if amount_micros > 0 else "debit",
                    "available_usdt": micros_to_usdt(before_micros + amount_micros),
                    "status": "начислено" if amount_micros > 0 else "списано",
                }
                await self._audit(session, operator, tenant_id, "user.adjust", "user",
                                  user["id"], reason, key, fingerprint, before, after)
                return after

    async def audit(self, operator: CashOperator, limit=100):
        limit = max(1, min(int(limit), 500))
        async with self.sessions() as session:
            query = select(cash_audit_events).order_by(cash_audit_events.c.created_at.desc()).limit(limit)
            if operator.role != "admin":
                query = query.where(cash_audit_events.c.tenant_id == operator.tenant_id)
            rows = (await session.execute(query)).mappings().all()
            return [dict(row) for row in rows]

    @staticmethod
    async def _find_user(session, identifier):
        identifier = str(identifier or "")
        if not identifier or len(identifier) > 64:
            raise ValueError("invalid user identifier")
        condition = users.c.id == identifier
        if identifier.isdigit():
            condition = condition | (users.c.telegram_user_id == int(identifier))
        user = (await session.execute(select(users).where(condition))).mappings().first()
        if user is None:
            raise LookupError("user not found")
        return user

    async def user(self, operator: CashOperator, identifier: str):
        async with self.sessions() as session:
            user = await self._find_user(session, identifier)
            self._require_scope(operator, user["acquisition_tenant_id"])
            hold = (await session.execute(select(cash_user_holds).where(
                cash_user_holds.c.user_id == user["id"],
            ))).mappings().first()
            cancellations = await cancelled_after_payment(
                session, since=self.now() - timedelta(days=1), threshold=1,
            )
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
            "hold": None if hold is None else {
                "reason": hold["reason"], "operator_id": hold["operator_id"],
                "created_at": _json(hold["created_at"]),
            },
            "cancellations_after_payment": cancellations.get(user["id"], 0),
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
        if not self.mock_rails:
            raise ValueError("no mock payouts where money is real: record the payout you sent")
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
                if row["network"] != TRC20:
                    raise WithdrawalStateError(
                        "a P2P payout is settled by an operator, not by a payout provider"
                    )
                if row["status"] != "approved":
                    raise WithdrawalStateError("only an approved withdrawal can be sent")
                before = _snapshot(row, WITHDRAWAL_FIELDS)
                result = self.executor.send(row["payout_id"], outcome)
                now = self.now()
                if result["status"] == "submitted":
                    # The fee is realised here too. This is the path an operator
                    # actually uses, so leaving it out sent the whole amount to
                    # the chain and kept nothing, however the service was set up.
                    await self.ledger.post(
                        session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                        reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                        postings=await self._payout_postings(session, row, "c2c-mock"),
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

    async def settle_p2p_withdrawal(self, withdrawal_id, operator, *, fiat_kopecks, reason, key):
        """The operator has already paid the RUB by hand; this records it.

        The whole rail exists because nothing automatic can be trusted to send
        fiat. So the money moves here only after a named person says they sent
        it, and the audit row carries both who and how much.
        """
        if type(fiat_kopecks) is not int or fiat_kopecks <= 0:
            raise ValueError("a P2P payout must record the RUB actually sent, in kopecks")
        return await self._settle_by_hand(
            withdrawal_id, operator, reason=reason, key=key, network=P2P_RUB,
            clearing=P2P_CLEARING, action="withdrawal.settle_p2p",
            receipt={"fiat_kopecks": fiat_kopecks},
        )

    async def settle_trc20_withdrawal(self, withdrawal_id, operator, *, tx_hash, reason, key):
        """The operator has already sent the USDT from a wallet by hand; this records it.

        The host has no payout provider, so nothing here can send. What it can
        do is write down the transaction the person made, under their name,
        and move the reserve out against it -- the same book entry a provider
        would have produced, with a real hash where the mock put a fake one.
        """
        if not tx_hash or len(tx_hash) > 128:
            raise ValueError("a TRC20 payout must record the transaction hash actually sent")
        return await self._settle_by_hand(
            withdrawal_id, operator, reason=reason, key=key, network=TRC20,
            clearing="c2c-mock", action="withdrawal.settle_trc20", receipt={"tx_hash": tx_hash},
        )

    async def _settle_by_hand(self, withdrawal_id, operator, *, reason, key, network, clearing,
                              action, receipt):
        self._require_mutation(operator)
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, action, withdrawal_id, reason, receipt,
                )
                if replay is not None:
                    return replay
                row = await self._withdrawal(session, withdrawal_id)
                self._require_scope(operator, row["tenant_id"])
                if row["network"] != network:
                    raise WithdrawalStateError(
                        "only a P2P payout is settled by hand" if network == P2P_RUB
                        else "only a TRC20 payout is recorded by its transaction hash"
                    )
                if row["status"] != "approved":
                    raise WithdrawalStateError("only an approved payout can be recorded as paid")
                before = _snapshot(row, WITHDRAWAL_FIELDS)
                now = self.now()
                await self.ledger.post(
                    session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                    reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                    postings=await self._payout_postings(session, row, clearing),
                )
                values = {"status": "submitted", **receipt,
                          "detail": reason, "submitted_at": now, "updated_at": now}
                await session.execute(update(cash_withdrawals).where(
                    cash_withdrawals.c.id == withdrawal_id
                ).values(**values))
                after = before | {name: _json(value) for name, value in values.items()
                                  if name in WITHDRAWAL_FIELDS}
                await self._audit(session, operator, row["tenant_id"], action,
                                  "withdrawal", withdrawal_id, reason, key, fingerprint, before, after)
                return after

    async def _payout_postings(self, session, row, clearing_name):
        """The reserve leaves; the fee stays with us; the rest goes to the rail's clearing."""
        fee = row["fee_micros"]
        clearing = await self._account(session, "clearing", None, clearing_name)
        postings = {row["reserve_account_id"]: -row["amount_micros"],
                    clearing: row["amount_micros"] - fee}
        if fee:
            postings[await self._account(session, "clearing", None, FEE_ACCOUNT)] = fee
        return postings

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
                        # Same split as a send that answered: the fee is ours
                        # whichever way the confirmation arrived.
                        await self.ledger.post(
                            session, scope="withdrawal-payout", key=row["payout_id"], kind="payout",
                            reference_id=withdrawal_id, actor=f"operator:{operator.telegram_user_id}",
                            postings=await self._payout_postings(session, row, "c2c-mock"),
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

    async def freeze_user(self, identifier, operator, *, reason, key):
        """Stop new money in or out for one account. Money already at risk still moves."""
        return await self._set_hold(identifier, operator, reason=reason, key=key, hold=True)

    async def release_user(self, identifier, operator, *, reason, key):
        return await self._set_hold(identifier, operator, reason=reason, key=key, hold=False)

    async def _set_hold(self, identifier, operator, *, reason, key, hold):
        self._require_mutation(operator)
        action = "user.freeze" if hold else "user.release"
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, action, str(identifier), reason, {},
                )
                if replay is not None:
                    return replay
                user = await self._find_user(session, identifier)
                tenant_id = user["acquisition_tenant_id"]
                self._require_scope(operator, tenant_id)
                existing = (await session.execute(select(cash_user_holds).where(
                    cash_user_holds.c.user_id == user["id"],
                ).with_for_update())).mappings().first()
                before = {"user_id": user["id"], "held": existing is not None,
                          "reason": existing["reason"] if existing else None}
                if hold:
                    await session.execute(insert(cash_user_holds).values(
                        user_id=user["id"], tenant_id=tenant_id, reason=reason.strip(),
                        operator_id=operator.id, created_at=self.now(),
                    ).on_conflict_do_update(index_elements=["user_id"], set_={
                        "reason": reason.strip(), "operator_id": operator.id,
                        "created_at": self.now(),
                    }))
                else:
                    await session.execute(cash_user_holds.delete().where(
                        cash_user_holds.c.user_id == user["id"],
                    ))
                after = {"user_id": user["id"], "held": hold,
                         "reason": reason.strip() if hold else None}
                await self._audit(session, operator, tenant_id, action, "user",
                                  user["id"], reason, key, fingerprint, before, after)
                return after

    async def fiat_reconciliation(self, operator: CashOperator, day):
        """Daily RUB sweep. Ledger accounts carry no tenant, so this is admin-only."""
        self._require_scope(operator, None)
        return await daily_fiat_reconciliation(self.sessions, day)

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
                    # The poller's ledger key, so a later partner replay of the same
                    # event cannot credit this order a second time.
                    await self.ledger.post(
                        session, scope="fiat-deposit", key=PROVIDER + ":" + str(event["event_id"]),
                        kind="deposit", reference_id=order["id"],
                        actor="operator:" + str(operator.telegram_user_id),
                        postings=await fiat_credit_postings(session, order, self._account),
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
                if row["status"] not in {"requesting", "clarifying", "review_required", "waiting_trader"}:
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

    async def referral_report(self, operator: CashOperator, *, limit: int = 100):
        """Who earned what, and what their group still owes the house.

        Admin-only for the reason the overview is: the referral books are not
        split by tenant, because the profit they are paid out of is not.
        """
        self._require_scope(operator, None)
        limit = max(1, min(int(limit), 500))
        async with self.sessions() as session:
            rows = (await session.execute(select(referral_settlements).order_by(
                referral_settlements.c.period_start.desc(),
                referral_settlements.c.created_at.desc(),
            ).limit(limit))).mappings().all()
            totals = dict((await session.execute(select(
                referral_settlements.c.status,
                func.coalesce(func.sum(referral_settlements.c.amount_micros), 0),
            ).group_by(referral_settlements.c.status))).all())
            groups = (await session.execute(select(
                referrals.c.referrer_id, func.count().label("invited"),
            ).group_by(referrals.c.referrer_id).order_by(
                func.count().desc()
            ).limit(20))).mappings().all()
        return {
            "settlements": [
                dict(row) | {"amount_usdt": micros_to_usdt(int(row["amount_micros"]))}
                for row in rows
            ],
            "totals_usdt": {
                status: micros_to_usdt(int(value)) for status, value in totals.items()
            },
            "largest_groups": [dict(row) for row in groups],
        }

    async def partner_report(self, operator: CashOperator):
        """Cube gross, what referrals cost it, and the share of what is left."""
        self._require_scope(operator, None)
        async with self.sessions() as session:
            rows = (await session.execute(select(partner_settlements).order_by(
                partner_settlements.c.period_start.desc(),
            ).limit(60))).mappings().all()
            shares = (await session.execute(select(partner_shares).order_by(
                partner_shares.c.effective_from.desc()
            ))).mappings().all()
            adjustments = (await session.execute(select(cube_adjustments).order_by(
                cube_adjustments.c.occurred_on.desc()
            ).limit(50))).mappings().all()
        return {
            "settlements": [
                dict(row) | {"amount_usdt": micros_to_usdt(int(row["amount_micros"]))}
                for row in rows
            ],
            "shares": [dict(row) for row in shares],
            "adjustments": [
                dict(row) | {"amount_usdt": micros_to_usdt(abs(int(row["amount_micros"])))}
                for row in adjustments
            ],
        }

    async def set_partner_share(self, operator, *, effective_from, share_bps, note, reason, key):
        """Fix the partner's share from a date. It never rewrites a settled period.

        Which is why it is a dated row and not a setting: a share that changed
        retroactively would change money both sides had already agreed on.
        """
        self._require_mutation(operator)
        self._require_scope(operator, None)
        effective = date.fromisoformat(str(effective_from))
        if type(share_bps) is not int or not 0 <= share_bps <= 10_000:
            raise ValueError("the partner share is basis points between 0 and 10000")
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "partner.share", effective.isoformat(), reason,
                    {"share_bps": share_bps},
                )
                if replay is not None:
                    return replay
                settled = await session.scalar(select(func.count()).select_from(
                    partner_settlements
                ).where(
                    partner_settlements.c.period_start >= effective,
                    # As above: a week that was only counted is not a week that
                    # was paid, and only what was paid is beyond changing.
                    partner_settlements.c.posted.is_(True),
                ))
                if settled:
                    raise ValueError("a period on or after this date is already paid")
                await session.execute(insert(partner_shares).values(
                    id=uuid4().hex, effective_from=effective, share_bps=share_bps,
                    note=(note or None),
                ).on_conflict_do_update(
                    index_elements=[partner_shares.c.effective_from],
                    set_={"share_bps": share_bps, "note": (note or None)},
                ))
                after = {"effective_from": effective.isoformat(), "share_bps": share_bps}
                await self._audit(session, operator, None, "partner.share", "partner",
                                  effective.isoformat(), reason, key, fingerprint, {}, after)
                return after

    async def record_cube_adjustment(self, operator, *, occurred_on, amount_micros, reason, key):
        """An agreed expense of Cube, or an agreed correction to one.

        Negative is charged against Cube and lowers what the partner shares in;
        positive gives it back. It moves no money itself -- the money moved
        when the fee was paid or the chargeback landed. This is the line in the
        books that says the movement belonged to Cube and not to Poker or to
        the company as a whole.
        """
        self._require_mutation(operator)
        self._require_scope(operator, None)
        occurred = date.fromisoformat(str(occurred_on))
        if type(amount_micros) is not int or amount_micros == 0:
            raise ValueError("an adjustment has to move a nonzero amount")
        if abs(amount_micros) > MAX_ADJUSTMENT_MICROS:
            raise ValueError(
                f"one adjustment is capped at {micros_to_usdt(MAX_ADJUSTMENT_MICROS)} USDT"
            )
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "cube.adjust", occurred.isoformat(), reason,
                    {"amount_micros": amount_micros},
                )
                if replay is not None:
                    return replay
                # Only a period that actually paid is closed to corrections.
                # Both cadences are written down, so counting the reports too
                # would leave a whole month uncorrectable from its second week.
                settled = await session.scalar(select(func.count()).select_from(
                    partner_settlements
                ).where(
                    partner_settlements.c.period_end >= occurred,
                    partner_settlements.c.posted.is_(True),
                ))
                if settled:
                    raise ValueError("the period this day belongs to is already paid")
                adjustment_id = uuid4().hex
                await session.execute(cube_adjustments.insert().values(
                    id=adjustment_id, occurred_on=occurred, amount_micros=amount_micros,
                    reason=reason.strip(), actor=f"operator:{operator.id}",
                ))
                after = {
                    "id": adjustment_id, "occurred_on": occurred.isoformat(),
                    "amount_usdt": micros_to_usdt(abs(amount_micros)),
                    "direction": "credit" if amount_micros > 0 else "charge",
                }
                await self._audit(session, operator, None, "cube.adjust", "cube",
                                  adjustment_id, reason, key, fingerprint, {}, after)
                return after

    async def reverse_referral(self, settlement_id, operator, *, reason, key):
        """Take back a reward still inside its hold: fraud, chargeback, error."""
        self._require_mutation(operator)
        self._require_scope(operator, None)
        if self.settlements is None:
            raise ValueError("referral settlement is not enabled on this deployment")
        # The reversal first, and outside any transaction of ours: it takes its
        # own row lock and posts its own ledger entry. Doing it after the audit
        # entry would let a failed reversal leave the log claiming it happened;
        # doing it twice is a no-op, so this order costs nothing.
        reversed_now = await self.settlements.reverse(
            settlement_id, actor=f"operator:{operator.id}",
        )
        after = {"settlement_id": settlement_id, "reversed": reversed_now}
        async with self.sessions() as session:
            async with session.begin():
                replay, fingerprint = await self._claim(
                    session, operator, key, "referral.reverse", str(settlement_id), reason, {},
                )
                if replay is not None:
                    return replay
                await self._audit(session, operator, None, "referral.reverse", "referral",
                                  str(settlement_id), reason, key, fingerprint, {}, after)
        return after
