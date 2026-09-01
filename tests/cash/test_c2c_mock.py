import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from cash.amounts import micros_to_units
from cash.deposits import DepositService, DepositUnavailable
from cash.ledger import IdempotencyConflict
from cash.reconciliation import DepositReconciler
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, MOCK_USDT_CONTRACT, TransferEvent
from cash.wallet import WalletService
from cash.withdrawals import WithdrawalService, WithdrawalStateError
from online.schema import cash_accounts, cash_deposits, cash_payment_events, cash_transactions


pytestmark = [pytest.mark.anyio, pytest.mark.postgres]


def transfer(deposit, *, event_id="event-1", tx_hash="tx-1", **changes):
    values = dict(
        provider="mock-trc20", external_event_id=event_id, tx_hash=tx_hash, event_index=0,
        network=MOCK_NETWORK, token_contract=MOCK_USDT_CONTRACT,
        destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
        occurred_at=deposit["created_at"] + timedelta(seconds=1),
    )
    values.update(changes)
    return TransferEvent(**values)


async def balance(factory, account_id):
    async with factory() as session:
        return await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.id == account_id
        ))


async def test_unique_amounts_are_exact_bounded_and_never_reused(cash_db):
    service = DepositService(cash_db)
    rows = await asyncio.gather(*[
        service.create(user_id="alice", tenant_id="tenant", amount_usdt="10", request_key=f"d-{i}")
        for i in range(10)
    ])
    assert sorted(row["expected_micros"] for row in rows) == [10_000_000 + i * 10_000 for i in range(10)]
    with pytest.raises(DepositUnavailable):
        await service.create(user_id="bob", tenant_id="tenant", amount_usdt="10", request_key="exhausted")
    with pytest.raises(ValueError, match="between 1 and 100"):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="0.99", request_key="small")
    top = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="100", request_key="top")
    assert top["expected_micros"] == 100_000_000
    with pytest.raises(DepositUnavailable):
        await service.create(user_id="bob", tenant_id="tenant", amount_usdt="100", request_key="top-2")


async def test_deposit_idempotency_is_content_bound(cash_db):
    service = DepositService(cash_db)
    first = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="3", request_key="same")
    again = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="3", request_key="same")
    assert again["id"] == first["id"]
    with pytest.raises(IdempotencyConflict):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="4", request_key="same")


async def test_valid_transfer_credits_full_unique_amount_exactly_once(cash_db):
    service = DepositService(cash_db)
    deposit = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="10", request_key="credit")
    event = transfer(deposit)
    first, second = await asyncio.gather(service.observe(event), service.observe(event))
    assert first["status"] == second["status"] == "processed"
    assert (await service.get(deposit["id"], "alice"))["status"] == "credited"
    assert await balance(cash_db, "alice-wallet") == deposit["expected_micros"]
    assert micros_to_units(deposit["expected_micros"]) == "100"
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(cash_transactions).where(
            cash_transactions.c.kind == "deposit"
        )) == 1


async def test_bad_or_late_transfer_is_retained_for_review_and_never_credits(cash_db):
    service = DepositService(cash_db)
    deposit = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="7", request_key="bad")
    result = await service.observe(transfer(deposit, token_contract="wrong-contract"))
    assert result["status"] == "review_required"
    assert result["deposit_id"] == deposit["id"]
    assert (await service.get(deposit["id"], "alice"))["status"] == "review_required"
    assert await balance(cash_db, "alice-wallet") == 0
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(cash_payment_events)) == 1


async def test_observed_event_reconciles_after_service_restart(cash_db):
    service = DepositService(cash_db)
    deposit = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="5", request_key="restart")
    assert (await service.observe(transfer(deposit), process=False))["status"] == "observed"
    restarted = DepositService(cash_db)
    assert await DepositReconciler(restarted).run_once() == 1
    assert (await restarted.get(deposit["id"], "alice"))["status"] == "credited"
    assert await balance(cash_db, "alice-wallet") == 5_000_000


async def test_withdrawal_reserves_releases_and_completes_without_double_spend(cash_db):
    deposits = DepositService(cash_db)
    deposit = await deposits.create(user_id="alice", tenant_id="tenant", amount_usdt="10", request_key="fund")
    await deposits.observe(transfer(deposit))
    service = WithdrawalService(cash_db)

    same_a, same_b = await asyncio.gather(*[
        service.create(user_id="alice", tenant_id="tenant", amount_usdt="0.5",
                       destination_address="TUserWallet", request_key="same-withdrawal")
        for _ in range(2)
    ])
    assert same_a["id"] == same_b["id"]
    await service.cancel(same_a["id"], "alice")
    with pytest.raises(IdempotencyConflict):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="0.6",
                             destination_address="TUserWallet", request_key="same-withdrawal")

    cancelled = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="2",
                                     destination_address="TUserWallet", request_key="cancel")
    assert await balance(cash_db, "alice-wallet") == 8_000_000
    await asyncio.gather(service.cancel(cancelled["id"], "alice"), service.cancel(cancelled["id"], "alice"))
    assert await balance(cash_db, "alice-wallet") == 10_000_000
    assert await balance(cash_db, cancelled["reserve_account_id"]) == 0

    paid = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="4",
                                destination_address="TUserWallet", request_key="paid")
    await service.approve(paid["id"])
    submitted = await service.execute(paid["id"], "success")
    assert submitted["status"] == "submitted"
    assert (await service.confirm(paid["id"]))["status"] == "confirmed"
    assert await balance(cash_db, paid["reserve_account_id"]) == 0
    assert await balance(cash_db, "alice-wallet") == 6_000_000
    with pytest.raises(WithdrawalStateError):
        await service.cancel(paid["id"], "alice")


async def test_unknown_payout_keeps_reserve_and_direct_ids_enforce_ownership(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(cash_accounts.update().where(cash_accounts.c.id == "alice-wallet").values(
                balance_micros=3_000_000
            ))
    service = WithdrawalService(cash_db)
    row = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="1",
                               destination_address="TUserWallet", request_key="unknown")
    assert await service.get(row["id"], "bob") is None
    await service.approve(row["id"])
    assert (await service.execute(row["id"], "unknown"))["status"] == "unknown"
    assert await balance(cash_db, row["reserve_account_id"]) == 1_000_000
    assert await balance(cash_db, "alice-wallet") == 2_000_000


async def test_wallet_reports_usdt_units_and_journal(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(cash_accounts.update().where(cash_accounts.c.id == "alice-wallet").values(
                balance_micros=1_250_000
            ))
    wallet = await WalletService(cash_db).get("alice")
    assert wallet["available_usdt"] == "1.25"
    assert wallet["available_units"] == "12.5"


async def test_expiry_is_terminal_and_a_late_transfer_goes_to_review(cash_db):
    clock = [datetime.now(timezone.utc)]
    service = DepositService(cash_db, now=lambda: clock[0])
    deposit = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="2", request_key="expire")
    clock[0] += timedelta(minutes=31)
    assert await service.expire_due() == 1
    assert (await service.get(deposit["id"], "alice"))["status"] == "expired"
    result = await service.observe(transfer(
        deposit, occurred_at=deposit["expires_at"] + timedelta(seconds=1),
    ))
    assert result["status"] == "review_required"
    assert await balance(cash_db, "alice-wallet") == 0
