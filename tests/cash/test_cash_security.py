import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.dependencies import AuthenticatedUser, get_cash_user
from app.routers.cash import (
    DepositRequest, FiatOrderRequest, WithdrawalRequest, cancel_deposit, cancel_fiat_order,
    cancel_withdrawal, create_deposit, create_fiat_order, create_withdrawal, get_deposit,
    get_fiat_order, get_withdrawal, mark_deposit_paid, mark_fiat_order_paid,
    simulate_deposit_transfer, simulate_fiat_confirmation,
)
from cash.deposits import DepositService
from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import MockCase8Partner
from cash.ledger import InsufficientCash
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.wallet import WalletService
from cash.withdrawals import ActiveWithdrawalExists, WithdrawalService
from online.config import Settings
from online.schema import cash_accounts, cash_transactions


pytestmark = [pytest.mark.anyio, pytest.mark.postgres]

ALICE = AuthenticatedUser("alice", "tenant", 1, "Alice", "dev")
BOB = AuthenticatedUser("bob", "tenant", 2, "Bob", "dev")


def cash_request(cash_db, partner=None):
    state = SimpleNamespace(
        session_factory=cash_db,
        settings=SimpleNamespace(cash_mode="mock", cash_allowlist=()),
        cash_deposits=DepositService(cash_db),
        cash_fiat_orders=FiatOrderService(cash_db, partner=partner or MockCase8Partner()),
        cash_withdrawals=WithdrawalService(cash_db),
        cash_wallet=WalletService(cash_db),
    )
    return SimpleNamespace(app=SimpleNamespace(state=state))


async def funded(request, user, amount="60"):
    deposit = await create_deposit(
        DepositRequest(amount_usdt=amount, request_id=f"fund-{user.user_id}"), request, user,
    )
    await simulate_deposit_transfer(deposit["id"], request, user)
    return deposit


async def test_another_users_id_is_not_a_key_to_their_money(cash_db):
    request = cash_request(cash_db)
    deposit = await funded(request, ALICE)
    await funded(request, BOB)
    order = await create_fiat_order(
        FiatOrderRequest(amount_usdt="20", request_id="alice-rub"), request, ALICE,
    )
    withdrawal = await create_withdrawal(
        WithdrawalRequest(amount_usdt="5", address="TAliceWallet", request_id="alice-out"),
        request, ALICE,
    )

    attempts = (
        get_deposit(deposit["id"], request, BOB),
        cancel_deposit(deposit["id"], request, BOB),
        mark_deposit_paid(deposit["id"], request, BOB),
        simulate_deposit_transfer(deposit["id"], request, BOB),
        get_fiat_order(order["id"], request, BOB),
        mark_fiat_order_paid(order["id"], request, BOB),
        cancel_fiat_order(order["id"], request, BOB),
        simulate_fiat_confirmation(order["id"], request, BOB),
        get_withdrawal(withdrawal["id"], request, BOB),
        cancel_withdrawal(withdrawal["id"], request, BOB),
    )
    for attempt in attempts:
        with pytest.raises(HTTPException) as refused:
            await attempt
        assert refused.value.status_code == 404

    # Alice's own operations are untouched by the attempts against them.
    assert (await get_deposit(deposit["id"], request, ALICE))["status"] == "credited"
    assert (await get_fiat_order(order["id"], request, ALICE))["status"] == "awaiting_user"
    assert (await get_withdrawal(withdrawal["id"], request, ALICE))["status"] == "reserved"


async def test_two_processes_crediting_the_same_event_credit_it_once(cash_db):
    deposit = await DepositService(cash_db).create(
        user_id="alice", tenant_id="tenant", amount_usdt="30", request_key="concurrent",
    )
    event = TransferEvent(
        provider="mock-trc20", external_event_id="chain-concurrent", tx_hash="tx-concurrent",
        event_index=0, network=MOCK_NETWORK, token_contract=deposit["token_contract"],
        destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
        occurred_at=deposit["created_at"],
    )

    await asyncio.gather(*(DepositService(cash_db).observe(event) for _ in range(4)))

    wallet = await WalletService(cash_db).get("alice")
    assert wallet["available_usdt"] == "30"


async def test_concurrent_withdrawals_cannot_spend_the_same_balance_twice(cash_db):
    request = cash_request(cash_db)
    await funded(request, ALICE, "10")

    async def withdraw(index):
        try:
            return await WithdrawalService(cash_db).create(
                user_id="alice", tenant_id="tenant", amount_usdt="6",
                destination_address="TAliceWallet", request_key=f"race-{index}",
            )
        # Two rules now stop the second one, and which fires depends on who
        # reaches the wallet row first. Either way exactly one may survive.
        except (InsufficientCash, ActiveWithdrawalExists):
            return None

    results = await asyncio.gather(*(withdraw(index) for index in range(2)))

    assert len([row for row in results if row]) == 1
    wallet = await WalletService(cash_db).get("alice")
    assert wallet["available_usdt"] == "4" and wallet["withdrawal_usdt"] == "6"


async def test_requisites_and_the_partner_token_never_reach_the_logs(cash_db, caplog):
    request = cash_request(cash_db)
    with caplog.at_level(logging.DEBUG):
        order = await create_fiat_order(
            FiatOrderRequest(amount_usdt="20", request_id="quiet"), request, ALICE,
        )
        await mark_fiat_order_paid(order["id"], request, ALICE)
        await simulate_fiat_confirmation(order["id"], request, ALICE)
        logging.getLogger("poker8.security-test").info("cashier flow completed")

    # SQL parameter logging would defeat this, which is why the pilot runbook
    # forbids turning engine echo on.
    written = "\n".join(
        record.getMessage() for record in caplog.records
        if not record.name.startswith("sqlalchemy")
    )
    # Proves the check can see application logs at all, so its silence means
    # nothing was written rather than nothing was captured.
    assert "cashier flow completed" in written
    assert order["requisites"] not in written
    assert "X-Token" not in written


@pytest.mark.parametrize("mode, status", [("off", 404), ("mock", 403)])
async def test_the_kill_switch_closes_cash_for_everyone_it_should(mode, status):
    settings = Settings.from_mapping({
        "POKER8_ENV": "test", "POKER8_CASH_MODE": mode, "POKER8_CASH_ALLOWLIST": "999",
    })
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))

    with pytest.raises(HTTPException) as refused:
        await get_cash_user(request, ALICE)

    assert refused.value.status_code == status


async def test_the_ledger_stays_exact_when_many_credits_land_at_once(cash_db):
    deposits = DepositService(cash_db)
    created = []
    for index in range(24):
        # Two per amount: the mock gives each open deposit a unique cent offset.
        created.append(await deposits.create(
            user_id="alice", tenant_id="tenant", amount_usdt=str(1 + index // 2),
            request_key=f"burst-{index}",
        ))
    events = [
        TransferEvent(
            provider="mock-trc20", external_event_id=f"burst-{index}", tx_hash=f"tx-burst-{index}",
            event_index=0, network=MOCK_NETWORK, token_contract=row["token_contract"],
            destination_address=MOCK_ADDRESS, amount_micros=row["expected_micros"],
            occurred_at=row["created_at"],
        )
        for index, row in enumerate(created)
    ]

    # Every one of these credits the same wallet row and the same clearing row.
    await asyncio.gather(*(DepositService(cash_db).observe(event) for event in events))

    funded = sum(row["expected_micros"] for row in created)
    async with cash_db() as session:
        wallet = await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "available", cash_accounts.c.reference_id == "alice",
        ))
        clearing = await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "clearing", cash_accounts.c.reference_id == "c2c-mock",
        ))
        postings = await session.scalar(select(func.count()).select_from(cash_transactions))
    assert wallet == funded and clearing == -funded and postings == 24
