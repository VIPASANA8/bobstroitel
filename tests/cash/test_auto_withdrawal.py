"""Small TRC20 withdrawals send themselves; everything else waits for a person.

The ceiling is a convenience, not a loosening of safety: it only applies to the
crypto rail, only below a set amount, and only against a real automatic
executor. The pilot's mock executor is not automatic, so none of this fires
there however the threshold is configured.
"""
from datetime import timedelta

import pytest
from sqlalchemy import select

from cash.deposits import DepositService
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.withdrawals import MockPayoutExecutor, P2P_RUB, TRC20, WithdrawalService
from cash.wallet import WalletService
from online.schema import cash_accounts

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
FIFTY = 50_000_000


async def fund(cash_db, amount="200", key="fund", user="alice"):
    deposits = DepositService(cash_db)
    row = await deposits.create(user_id=user, tenant_id="tenant", amount_usdt=amount, request_key=key)
    await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id=f"e-{key}", tx_hash=f"tx-{key}", event_index=0,
        network=MOCK_NETWORK, token_contract=row["token_contract"],
        destination_address=MOCK_ADDRESS, amount_micros=row["expected_micros"],
        occurred_at=row["created_at"] + timedelta(seconds=1),
    ))


def auto_service(cash_db, **kw):
    return WithdrawalService(
        cash_db, auto_micros=FIFTY,
        executor=MockPayoutExecutor(automatic=True), **kw,
    )


async def balance(cash_db, kind, ref):
    async with cash_db() as session:
        return await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == kind, cash_accounts.c.reference_id == ref,
        )) or 0


async def test_a_small_trc20_withdrawal_sends_itself(cash_db):
    await fund(cash_db)
    row = await auto_service(cash_db, fee_micros=5_000_000).create(
        user_id="alice", tenant_id="tenant", amount_usdt="50",
        destination_address="TAliceWallet", request_key="w-auto",
    )
    # No operator touched it: straight to submitted, on chain. The fee account
    # and the wallet are the clean signals (c2c-mock clearing is shared with
    # deposits, so its absolute balance is not just this payout).
    assert row["status"] == "submitted" and row["tx_hash"]
    assert await balance(cash_db, "clearing", "withdrawal-fee") == 5_000_000
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == "150"


async def test_above_the_ceiling_waits_for_an_operator(cash_db):
    await fund(cash_db)
    row = await auto_service(cash_db).create(
        user_id="alice", tenant_id="tenant", amount_usdt="51",
        destination_address="TAliceWallet", request_key="w-big",
    )
    assert row["status"] == "reserved"
    assert await balance(cash_db, "clearing", "withdrawal-fee") == 0  # nothing sent


async def test_the_p2p_rail_is_never_auto(cash_db):
    await fund(cash_db)
    row = await auto_service(cash_db).create(
        user_id="alice", tenant_id="tenant", amount_usdt="30",
        destination_address="2200 7007 1234 5678", request_key="w-fiat", rail=P2P_RUB,
    )
    # Under the ceiling, but a human pays rubles -- it stays reserved.
    assert row["status"] == "reserved" and row["network"] == P2P_RUB


async def test_a_non_automatic_executor_never_auto_sends(cash_db):
    await fund(cash_db)
    # The pilot's default: a mock that is not automatic, threshold or not.
    row = await WithdrawalService(
        cash_db, auto_micros=FIFTY, executor=MockPayoutExecutor(automatic=False),
    ).create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address="TAliceWallet", request_key="w-noexec",
    )
    assert row["status"] == "reserved"


async def test_off_by_default_keeps_everything_manual(cash_db):
    await fund(cash_db)
    # auto_micros defaults to 0 even with an automatic executor.
    row = await WithdrawalService(
        cash_db, executor=MockPayoutExecutor(automatic=True),
    ).create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address="TAliceWallet", request_key="w-off",
    )
    assert row["status"] == "reserved"


async def test_a_failed_auto_send_leaves_the_withdrawal_for_an_operator(cash_db):
    await fund(cash_db)
    # An automatic executor whose send rejects: the reserve stays, no money moved.
    row = await WithdrawalService(
        cash_db, auto_micros=FIFTY,
        executor=MockPayoutExecutor(automatic=True, outcome="failure"),
    ).create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address="TAliceWallet", request_key="w-fail",
    )
    # A rejected send refunds the reserve to the wallet, exactly like the
    # operator path, and never counts as sent.
    assert row["status"] == "rejected"
    assert await balance(cash_db, "clearing", "withdrawal-fee") == 0
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == "200"
