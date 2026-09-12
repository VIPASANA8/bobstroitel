"""The RUB payout rail: reserved by the system, paid by a person.

There is no executor here on purpose. Fiat leaves only after a named operator
says they sent it, so what this has to prove is that the money moves exactly
once, that it moves only on their say-so, and that what they sent is written
down beside the USDT that was debited.
"""
from datetime import timedelta

import pytest
from sqlalchemy import select

from cash.access import CashOperator
from cash.admin import CashAdminService, OperatorAccessDenied
from cash.deposits import DepositService
from cash.ledger import IdempotencyConflict
from cash.rates import set_rub_rate
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.withdrawals import (
    FEE_ACCOUNT, P2P_CLEARING, P2P_RUB, TRC20, RubRateUnset, WithdrawalService,
    WithdrawalStateError,
)
from online.schema import cash_accounts, cash_audit_events, cash_withdrawals

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
OPERATOR = CashOperator("operator", 1001, "tenant", "operator")
CARD = "2200 7007 1234 5678"


async def fund(cash_db, key="fund", user_id="alice"):
    deposits = DepositService(cash_db)
    deposit = await deposits.create(
        user_id=user_id, tenant_id="tenant", amount_usdt="50", request_key=key,
    )
    await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id=f"e-{key}", tx_hash=f"tx-{key}", event_index=0,
        network=MOCK_NETWORK, token_contract=deposit["token_contract"],
        destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
        occurred_at=deposit["created_at"] + timedelta(seconds=1),
    ))


async def rate(cash_db, kopecks_per_usdt=9_000):
    """A card withdrawal is quoted in roubles, so a test that opens one needs a rate."""
    async with cash_db() as session:
        async with session.begin():
            await set_rub_rate(session, kopecks_per_usdt=kopecks_per_usdt, actor="test")


async def balance(cash_db, kind, reference):
    async with cash_db() as session:
        return await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == kind, cash_accounts.c.reference_id == reference,
        )) or 0


async def test_a_p2p_payout_moves_only_when_an_operator_says_they_paid(cash_db):
    await fund(cash_db)
    await rate(cash_db)
    service = WithdrawalService(cash_db, fee_micros=5_000_000)
    admin = CashAdminService(cash_db)
    row = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="30",
        destination_address=CARD, request_key="p2p-1", rail=P2P_RUB,
    )
    assert row["network"] == P2P_RUB and row["status"] == "reserved"
    assert await balance(cash_db, "available", "alice") == 20_000_000
    assert await balance(cash_db, "clearing", P2P_CLEARING) == 0

    # Nothing may settle it before an operator approves it.
    with pytest.raises(WithdrawalStateError, match="approved payout"):
        await admin.settle_p2p_withdrawal(
            row["id"], OPERATOR, fiat_kopecks=270_000, reason="too early", key="k0",
        )
    await admin.approve_withdrawal(row["id"], OPERATOR, reason="checked", key="k1")

    after = await admin.settle_p2p_withdrawal(
        row["id"], OPERATOR, fiat_kopecks=270_050, reason="paid to card", key="k2",
    )
    assert after["status"] == "submitted" and after["fiat_kopecks"] == 270_050
    # 30 USDT left the reserve: 25 to the payout clearing, 5 kept as the fee.
    assert await balance(cash_db, "clearing", P2P_CLEARING) == 25_000_000
    assert await balance(cash_db, "clearing", FEE_ACCOUNT) == 5_000_000
    assert await balance(cash_db, "available", "alice") == 20_000_000

    async with cash_db() as session:
        action = await session.scalar(select(cash_audit_events.c.action).where(
            cash_audit_events.c.target_id == row["id"],
            cash_audit_events.c.idempotency_key == "k2",
        ))
    assert action == "withdrawal.settle_p2p"


async def test_the_same_payout_is_never_recorded_twice(cash_db):
    await fund(cash_db)
    await rate(cash_db)
    service = WithdrawalService(cash_db)
    admin = CashAdminService(cash_db)
    row = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address=CARD, request_key="p2p-2", rail=P2P_RUB,
    )
    await admin.approve_withdrawal(row["id"], OPERATOR, reason="checked", key="a")
    first = await admin.settle_p2p_withdrawal(
        row["id"], OPERATOR, fiat_kopecks=90_000, reason="paid", key="same",
    )
    replay = await admin.settle_p2p_withdrawal(
        row["id"], OPERATOR, fiat_kopecks=90_000, reason="paid", key="same",
    )
    assert replay == first
    assert await balance(cash_db, "clearing", P2P_CLEARING) == 10_000_000

    # The same key with a different amount is a mistake, not a retry.
    with pytest.raises(IdempotencyConflict):
        await admin.settle_p2p_withdrawal(
            row["id"], OPERATOR, fiat_kopecks=95_000, reason="paid", key="same",
        )


async def test_the_two_rails_never_settle_each_other(cash_db):
    await fund(cash_db, key="fund-rails")
    service = WithdrawalService(cash_db)
    admin = CashAdminService(cash_db)
    # One live withdrawal per user, so the two rails need two people.
    await fund(cash_db, key="fund-bob", user_id="bob")
    await rate(cash_db)
    chain = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="5",
        destination_address="TUserWallet", request_key="chain", rail=TRC20,
    )
    fiat = await service.create(
        user_id="bob", tenant_id="tenant", amount_usdt="5",
        destination_address=CARD, request_key="fiat", rail=P2P_RUB,
    )
    await admin.approve_withdrawal(chain["id"], OPERATOR, reason="checked", key="c1")
    await admin.approve_withdrawal(fiat["id"], OPERATOR, reason="checked", key="f1")

    # A payout provider must not touch money a person owes by hand...
    with pytest.raises(WithdrawalStateError, match="not by a payout provider"):
        await admin.execute_mock(
            fiat["id"], OPERATOR, outcome="success", reason="wrong rail", key="f2",
        )
    with pytest.raises(WithdrawalStateError, match="not by a payout provider"):
        await service.execute(fiat["id"], "success")
    # ...and a hand-written receipt does not belong to a chain payout.
    with pytest.raises(WithdrawalStateError, match="only a P2P payout"):
        await admin.settle_p2p_withdrawal(
            chain["id"], OPERATOR, fiat_kopecks=45_000, reason="wrong rail", key="c2",
        )


async def test_a_rejected_p2p_payout_returns_the_whole_reserve(cash_db):
    await fund(cash_db, key="fund-reject")
    await rate(cash_db)
    service = WithdrawalService(cash_db, fee_micros=5_000_000)
    admin = CashAdminService(cash_db)
    row = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="30",
        destination_address=CARD, request_key="p2p-3", rail=P2P_RUB,
    )
    await admin.reject_withdrawal(row["id"], OPERATOR, reason="bad requisites", key="r1")
    # Nothing was sent, so nothing was spent: the fee is not kept either.
    assert await balance(cash_db, "available", "alice") == 50_000_000
    assert await balance(cash_db, "clearing", FEE_ACCOUNT) == 0
    assert await balance(cash_db, "clearing", P2P_CLEARING) == 0


async def test_the_receipt_has_to_be_a_real_amount(cash_db):
    await fund(cash_db, key="fund-bad")
    await rate(cash_db)
    service = WithdrawalService(cash_db)
    admin = CashAdminService(cash_db)
    row = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address=CARD, request_key="p2p-4", rail=P2P_RUB,
    )
    await admin.approve_withdrawal(row["id"], OPERATOR, reason="checked", key="b1")
    for bad in (0, -1, 1.5, "90000", None):
        with pytest.raises(ValueError, match="RUB actually sent"):
            await admin.settle_p2p_withdrawal(
                row["id"], OPERATOR, fiat_kopecks=bad, reason="paid", key=f"b-{bad}",
            )
    async with cash_db() as session:
        status = await session.scalar(select(cash_withdrawals.c.status).where(
            cash_withdrawals.c.id == row["id"]
        ))
    assert status == "approved"


async def test_an_unknown_rail_is_refused_before_any_money_moves(cash_db):
    await fund(cash_db, key="fund-rail")
    with pytest.raises(ValueError, match="withdrawal rail"):
        await WithdrawalService(cash_db).create(
            user_id="alice", tenant_id="tenant", amount_usdt="10",
            destination_address=CARD, request_key="bad-rail", rail="SWIFT",
        )
    assert await balance(cash_db, "available", "alice") == 50_000_000


async def test_real_money_records_the_usdt_the_operator_sent_and_refuses_the_mock(cash_db):
    """The pilot host has real CASH and no payout provider. A TRC20 payout
    there is sent by a person from a wallet and recorded with its hash; the
    mock executor, which mints a fake hash on a real debit, is refused."""
    await fund(cash_db, key="fund-real")
    service = WithdrawalService(cash_db, fee_micros=5_000_000)
    admin = CashAdminService(cash_db, mock_rails=False)
    row = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="30",
        destination_address="TDestination", request_key="trc20-real", rail=TRC20,
    )
    await admin.approve_withdrawal(row["id"], OPERATOR, reason="checked", key="k1")
    with pytest.raises(ValueError, match="record the payout you sent"):
        await admin.execute_mock(row["id"], OPERATOR, outcome="success", reason="mock", key="k2")
    with pytest.raises(ValueError, match="transaction hash"):
        await admin.settle_trc20_withdrawal(row["id"], OPERATOR, tx_hash="", reason="sent", key="k3")

    after = await admin.settle_trc20_withdrawal(
        row["id"], OPERATOR, tx_hash="0xreal", reason="sent from the cold wallet", key="k4",
    )
    assert after["status"] == "submitted" and after["tx_hash"] == "0xreal"
    # 30 USDT left the reserve: 25 out on chain, 5 kept as the fee. The chain
    # clearing account also absorbed the 50 USDT mock deposit that funded alice.
    assert await balance(cash_db, "clearing", "c2c-mock") == -50_000_000 + 25_000_000
    assert await balance(cash_db, "clearing", FEE_ACCOUNT) == 5_000_000
    assert await balance(cash_db, "available", "alice") == 20_000_000
    async with cash_db() as session:
        action = await session.scalar(select(cash_audit_events.c.action).where(
            cash_audit_events.c.target_id == row["id"],
            cash_audit_events.c.idempotency_key == "k4",
        ))
    assert action == "withdrawal.settle_trc20"
    # The P2P recorder still refuses a crypto row, as before.
    with pytest.raises(WithdrawalStateError):
        await admin.settle_p2p_withdrawal(row["id"], OPERATOR, fiat_kopecks=1, reason="wrong rail", key="k5")


async def test_a_card_payout_is_quoted_at_the_rate_of_its_moment(cash_db):
    """The player is promised roubles, so there is no card withdrawal until an
    operator has set a rate; once there is one, the quote is fixed at the
    moment of asking and a later rate does not move it."""
    await fund(cash_db, key="fund-rate")
    service = WithdrawalService(cash_db, fee_micros=5_000_000)
    admin = CashAdminService(cash_db)
    global_admin = CashOperator("global-admin", 1004, None, "admin")
    with pytest.raises(RubRateUnset):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="30",
                             destination_address=CARD, request_key="rub-0", rail=P2P_RUB)
    with pytest.raises(ValueError, match="kopecks per USDT"):
        await admin.set_rub_rate(global_admin, kopecks_per_usdt=0, reason="typo", key="r0")

    # The rate is global money policy: a tenant operator may not set it.
    with pytest.raises(OperatorAccessDenied):
        await admin.set_rub_rate(OPERATOR, kopecks_per_usdt=9_250, reason="market", key="r1")
    assert await admin.set_rub_rate(global_admin, kopecks_per_usdt=9_250, reason="market", key="r1") == {
        "kopecks_per_usdt": 9_250,
    }
    row = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="30",
                               destination_address=CARD, request_key="rub-1", rail=P2P_RUB)
    # 30 USDT minus the 5 USDT fee, at 92.50: 2 312,50 ₽.
    assert row["quote_kopecks"] == 231_250
    assert WithdrawalService.public(row)["quote_rub"] == "2312,50"
    assert (await admin.overview(global_admin))["rub_rate_kopecks"] == 9_250

    await admin.set_rub_rate(global_admin, kopecks_per_usdt=9_000, reason="moved", key="r2")
    assert (await service.get(row["id"], "alice"))["quote_kopecks"] == 231_250
    # A TRC20 withdrawal is quoted in nothing but itself.
    await service.cancel(row["id"], "alice")
    crypto = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="10",
                                  destination_address="TDest", request_key="trc-1", rail=TRC20)
    assert crypto["quote_kopecks"] is None


async def test_a_card_payout_under_five_thousand_roubles_is_refused(cash_db):
    await fund(cash_db, key="fund-min-1")
    await fund(cash_db, key="fund-min-2")   # 100 USDT: enough for a 65 USDT withdrawal
    await rate(cash_db, kopecks_per_usdt=8_400)
    service = WithdrawalService(cash_db, fee_micros=5_000_000)
    # (64 - 5) * 84 = 4 956 ₽: under the floor. (65 - 5) * 84 = 5 040 ₽: over it.
    with pytest.raises(ValueError, match="at least 5000,00 RUB"):
        await service.create(user_id="alice", tenant_id="tenant", amount_usdt="64",
                             destination_address=CARD, request_key="min-1", rail=P2P_RUB)
    # Refused before anything was reserved: the wallet is untouched.
    assert await balance(cash_db, "available", "alice") == 100_000_000
    row = await service.create(user_id="alice", tenant_id="tenant", amount_usdt="65",
                               destination_address=CARD, request_key="min-2", rail=P2P_RUB)
    assert row["quote_kopecks"] == 504_000
