from decimal import Decimal

import pytest
from sqlalchemy import func, insert, select

from cash.deposits import DepositService
from cash.fiat_orders import FiatOrderService
from cash.fiat_p2p import MockCase8Partner, PartnerEvent
from cash.game import CashGameService
from cash.ledger import CashLedger
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.wallet import WalletService
from online.schema import (
    cash_accounts, cash_fiat_events, cash_partner_cursors, cash_transactions,
    poker_tables, table_seats,
)
from poker.models import ActionType


pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
TABLE_ID = "cash-fault-table"


class CrashAfterPosting(CashLedger):
    """The process dies with the credit posted but the transaction not committed."""

    async def post(self, session, **kwargs):
        receipt = await super().post(session, **kwargs)
        raise RuntimeError("process died between the partner event and its commit")


async def paid_order(factory):
    service = FiatOrderService(factory, partner=MockCase8Partner())
    order = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20", request_key="rub-fault",
    )
    await service.mark_paid(order["id"], "alice")
    return service, order


async def counts(factory):
    async with factory() as session:
        return {
            "transactions": await session.scalar(select(func.count()).select_from(cash_transactions)),
            "events": await session.scalar(select(func.count()).select_from(cash_fiat_events)),
            "cursor": await session.scalar(select(cash_partner_cursors.c.offset)) or 0,
        }


async def test_a_crash_between_the_event_and_the_credit_leaves_nothing_behind(cash_db):
    service, order = await paid_order(cash_db)
    crashing = FiatOrderService(
        cash_db, partner=MockCase8Partner(), ledger=CrashAfterPosting(),
    )
    crashing.partner = service.partner

    with pytest.raises(RuntimeError, match="process died"):
        await crashing.poll_once()

    # The event row, the ledger posting and the cursor were all in that one
    # transaction, so the partner will simply deliver the event again.
    assert await counts(cash_db) == {"transactions": 0, "events": 0, "cursor": 0}
    assert (await service.get(order["id"], "alice"))["status"] == "waiting_trader"
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == "0"

    assert await service.poll_once() == 1
    assert (await service.get(order["id"], "alice"))["status"] == "credited"
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == "20"
    assert (await counts(cash_db))["transactions"] == 1

    # And a partner redelivering after the recovery still credits once.
    stored = await counts(cash_db)

    class Resending:
        async def poll_events(self, offset):
            return [PartnerEvent(1, order["partner_order_id"], "completed")], max(offset, 1)

    await FiatOrderService(cash_db, partner=Resending()).poll_once()
    assert (await WalletService(cash_db).get("alice"))["available_usdt"] == "20"
    assert await counts(cash_db) == stored


async def seat_two(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(insert(poker_tables).values(
                id=TABLE_ID, scope="network", asset="CASH_USDT", name="Fault Heads-Up",
                small_blind_units=0, big_blind_units=0, small_blind_micros=10_000,
                big_blind_micros=20_000, chip_micros=10_000, min_buy_in_bb=40,
                max_buy_in_bb=100, max_seats=6,
            ))
    deposits = DepositService(cash_db)
    funded = 0
    for user_id in ("alice", "bob"):
        deposit = await deposits.create(
            user_id=user_id, tenant_id="tenant", amount_usdt="10", request_key=f"fund-{user_id}",
        )
        # The mock C2C flow credits the unique expected amount, not the round one.
        funded += deposit["expected_micros"]
        await deposits.observe(TransferEvent(
            provider="mock-trc20", external_event_id=f"chain-{user_id}", tx_hash=f"tx-{user_id}",
            event_index=0, network=MOCK_NETWORK, token_contract=deposit["token_contract"],
            destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
            occurred_at=deposit["created_at"],
        ))
    game = CashGameService(cash_db)
    await game.seat("alice", TABLE_ID, 0, 800_000, "seat-alice")
    await game.seat("bob", TABLE_ID, 1, 800_000, "seat-bob")
    return game, funded


async def test_leaving_twice_returns_the_escrow_once(cash_db):
    game, _ = await seat_two(cash_db)

    await game.leave("alice", TABLE_ID, "leave-alice")
    await game.leave("alice", TABLE_ID, "leave-alice")
    await CashGameService(cash_db).leave("alice", TABLE_ID, "leave-alice-again")

    wallet = await WalletService(cash_db).get("alice")
    assert wallet["available_usdt"] == "10" and wallet["escrow_usdt"] == "0"
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(table_seats).where(
            table_seats.c.user_id == "alice", table_seats.c.state.in_(("seated", "held", "leaving")),
        )) == 0
        escrow = await session.scalar(select(func.sum(cash_accounts.c.balance_micros)).where(
            cash_accounts.c.kind == "escrow", cash_accounts.c.user_id == "alice",
        ))
    assert escrow == 0


async def test_a_settled_hand_needs_no_connection_to_be_exact(cash_db):
    game, funded = await seat_two(cash_db)
    started = await game.start_hand(TABLE_ID, button_seat=0)

    # Nobody is listening: no WebSocket is attached to this runtime at all.
    finished = await game.act(
        TABLE_ID, started.state.acting_player, ActionType.FOLD,
        amount_micros=0, command_id="fold-1", expected_revision=started.revision,
    )

    assert finished.state.terminal
    await game.leave("alice", TABLE_ID, "leave-alice")
    await game.leave("bob", TABLE_ID, "leave-bob")
    wallets = [await WalletService(cash_db).get(user) for user in ("alice", "bob")]
    async with cash_db() as session:
        available = await session.scalar(select(func.sum(cash_accounts.c.balance_micros)).where(
            cash_accounts.c.kind == "available",
        ))
    assert available == funded
    assert {Decimal(wallet["available_units"]) for wallet in wallets} == {Decimal("99.9"), Decimal("100.2")}
    assert all(wallet["escrow_usdt"] == "0" for wallet in wallets)
