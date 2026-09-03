import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from cash.access import CashOperator
from cash.admin import CashAdminService, OperatorAccessDenied
from cash.deposits import DepositService
from cash.fiat_orders import FiatOrderService
from cash.ledger import IdempotencyConflict
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.withdrawals import WithdrawalService
from online.schema import (
    cash_accounts, cash_audit_events, cash_payment_events,
    cash_transactions,
)


pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
OPERATOR = CashOperator("operator", 1001, "tenant", "operator")
REVIEWER = CashOperator("reviewer", 1002, "tenant", "reviewer")
OTHER = CashOperator("other-operator", 1003, "tenant-other", "operator")
ADMIN = CashOperator("global-admin", 1004, None, "admin")


async def funded_withdrawal(cash_db, amount="3", request="withdraw"):
    deposits = DepositService(cash_db)
    deposit = await deposits.create(user_id="alice", tenant_id="tenant", amount_usdt="10", request_key=f"fund-{request}")
    await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id=f"event-{request}", tx_hash=f"tx-{request}", event_index=0,
        network=MOCK_NETWORK, token_contract=deposit["token_contract"], destination_address=MOCK_ADDRESS,
        amount_micros=deposit["expected_micros"], occurred_at=deposit["created_at"] + timedelta(seconds=1),
    ))
    return await WithdrawalService(cash_db).create(
        user_id="alice", tenant_id="tenant", amount_usdt=amount,
        destination_address="TUserWallet", request_key=request,
    )


async def account_balance(cash_db, account_id):
    async with cash_db() as session:
        return await session.scalar(select(cash_accounts.c.balance_micros).where(cash_accounts.c.id == account_id))


async def audit_count(cash_db):
    async with cash_db() as session:
        return await session.scalar(select(func.count()).select_from(cash_audit_events))


async def test_approval_and_rejection_are_scoped_audited_and_content_bound(cash_db):
    withdrawal = await funded_withdrawal(cash_db)
    service = CashAdminService(cash_db)
    approved = await service.approve_withdrawal(
        withdrawal["id"], OPERATOR, reason="wallet checked", key="approve-1",
    )
    replay = await service.approve_withdrawal(
        withdrawal["id"], OPERATOR, reason="wallet checked", key="approve-1",
    )
    assert approved == replay
    assert approved["status"] == "approved"
    assert await audit_count(cash_db) == 1
    with pytest.raises(IdempotencyConflict):
        await service.approve_withdrawal(
            withdrawal["id"], OPERATOR, reason="different reason", key="approve-1",
        )
    rejected = await service.reject_withdrawal(
        withdrawal["id"], OPERATOR, reason="user requested rejection", key="reject-1",
    )
    assert rejected["status"] == "rejected"
    assert await account_balance(cash_db, withdrawal["reserve_account_id"]) == 0
    assert await account_balance(cash_db, "alice-wallet") == 10_000_000
    assert await audit_count(cash_db) == 2


async def test_reviewer_and_wrong_tenant_cannot_mutate_even_by_direct_id(cash_db):
    withdrawal = await funded_withdrawal(cash_db, request="scope")
    service = CashAdminService(cash_db)
    with pytest.raises(OperatorAccessDenied, match="read-only"):
        await service.approve_withdrawal(withdrawal["id"], REVIEWER, reason="looks fine", key="reviewer")
    with pytest.raises(OperatorAccessDenied, match="tenant"):
        await service.approve_withdrawal(withdrawal["id"], OTHER, reason="looks fine", key="wrong")
    assert await audit_count(cash_db) == 0


async def test_concurrent_operator_retry_changes_state_and_audit_once(cash_db):
    withdrawal = await funded_withdrawal(cash_db, request="concurrent")
    service = CashAdminService(cash_db)
    rows = await asyncio.gather(*[
        service.approve_withdrawal(withdrawal["id"], OPERATOR, reason="manual review passed", key="same")
        for _ in range(5)
    ])
    assert {row["status"] for row in rows} == {"approved"}
    assert await audit_count(cash_db) == 1


async def test_unknown_payout_is_never_resent_and_can_be_resolved_from_evidence(cash_db):
    withdrawal = await funded_withdrawal(cash_db, request="unknown-admin")
    service = CashAdminService(cash_db)
    await service.approve_withdrawal(withdrawal["id"], OPERATOR, reason="approved for mock", key="a")
    unknown = await service.execute_mock(
        withdrawal["id"], OPERATOR, outcome="unknown", reason="executor timed out", key="send",
    )
    assert unknown["status"] == "unknown"
    assert await account_balance(cash_db, withdrawal["reserve_account_id"]) == 3_000_000
    confirmed = await service.resolve_withdrawal(
        withdrawal["id"], OPERATOR, decision="confirmed", tx_hash="verified-chain-reference",
        reason="provider lookup confirmed payout", key="resolve",
    )
    assert confirmed["status"] == "confirmed"
    assert await account_balance(cash_db, withdrawal["reserve_account_id"]) == 0
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(cash_transactions).where(
            cash_transactions.c.scope == "withdrawal-payout"
        )) == 1


async def test_unknown_failure_releases_reserve_once(cash_db):
    withdrawal = await funded_withdrawal(cash_db, request="unknown-reject")
    service = CashAdminService(cash_db)
    await service.approve_withdrawal(withdrawal["id"], OPERATOR, reason="approved for mock", key="a2")
    await service.execute_mock(
        withdrawal["id"], OPERATOR, outcome="unknown", reason="executor timed out", key="send2",
    )
    rejected = await service.resolve_withdrawal(
        withdrawal["id"], OPERATOR, decision="rejected", tx_hash=None,
        reason="provider lookup found no payout", key="resolve2",
    )
    assert rejected["status"] == "rejected"
    assert await account_balance(cash_db, "alice-wallet") == 10_000_000
    assert await account_balance(cash_db, withdrawal["reserve_account_id"]) == 0


async def test_reviewed_payment_requires_scope_and_manual_reason(cash_db):
    deposits = DepositService(cash_db)
    deposit = await deposits.create(user_id="alice", tenant_id="tenant", amount_usdt="5", request_key="review")
    reviewed = await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id="bad-token", tx_hash="bad-token-tx", event_index=0,
        network=MOCK_NETWORK, token_contract="wrong-token", destination_address=MOCK_ADDRESS,
        amount_micros=deposit["expected_micros"], occurred_at=deposit["created_at"] + timedelta(seconds=1),
    ))
    service = CashAdminService(cash_db)
    with pytest.raises(OperatorAccessDenied):
        await service.resolve_payment(reviewed["id"], OTHER, decision="credit", reason="verified separately", key="wrong")
    resolved = await service.resolve_payment(
        reviewed["id"], OPERATOR, decision="credit",
        reason="verified test transfer manually", key="credit-review",
    )
    assert resolved["status"] == "resolved_credited"
    assert await account_balance(cash_db, "alice-wallet") == 5_000_000
    async with cash_db() as session:
        assert await session.scalar(select(cash_payment_events.c.status).where(
            cash_payment_events.c.id == reviewed["id"]
        )) == "resolved_credited"


async def test_queue_and_audit_are_tenant_scoped(cash_db):
    withdrawal = await funded_withdrawal(cash_db, request="queue")
    service = CashAdminService(cash_db)
    assert [row["id"] for row in (await service.queue(OPERATOR))["withdrawals"]] == [withdrawal["id"]]
    assert (await service.queue(OTHER))["withdrawals"] == []
    await service.approve_withdrawal(withdrawal["id"], OPERATOR, reason="queue reviewed", key="queue-audit")
    assert len(await service.audit(OPERATOR)) == 1
    assert await service.audit(OTHER) == []
    assert len(await service.audit(ADMIN)) == 1


async def test_user_lookup_reports_separate_balances_and_obeys_tenant_scope(cash_db):
    await funded_withdrawal(cash_db, amount="2", request="lookup")
    service = CashAdminService(cash_db)
    user = await service.user(OPERATOR, "1")
    assert user["id"] == "alice"
    assert user["balances"]["available"] == {"usdt": "8", "units": "80"}
    assert user["balances"]["withdrawal"] == {"usdt": "2", "units": "20"}
    assert user["withdrawals"][0]["status"] == "reserved"
    with pytest.raises(OperatorAccessDenied):
        await service.user(OTHER, "alice")

