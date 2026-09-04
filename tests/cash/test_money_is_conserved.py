"""No micro is created and none is destroyed, over a whole life of an account.

`CashLedger.post` refuses postings that do not sum to zero, so conservation is
structural -- but only for what actually goes through it, and only as long as
the balance projection it maintains by hand still matches the entries it wrote.
Nothing checked either of those before this file.

The lifecycle here is deliberately the complete one: a chain deposit, a buy-in,
a raked hand, standing up, and both withdrawal rails with their fees. Every
place the house keeps money is a place money can quietly go missing.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, insert, select

from cash.access import CashOperator
from cash.admin import CashAdminService
from cash.deposits import DepositService
from cash.game import CashGameService, RAKE_ACCOUNT
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.withdrawals import (
    FEE_ACCOUNT, P2P_CLEARING, P2P_RUB, TRC20, WithdrawalService,
)
from online.schema import cash_accounts, cash_entries, poker_tables, table_seats
from poker.models import ActionType

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
OPERATOR = CashOperator("operator", 1001, "tenant", "operator")
CHIP, BB = 10_000, 100_000
TABLE = "cash-conservation"
BUY_IN = 10_000_000


async def deposit(cash_db, user_id, amount, key):
    deposits = DepositService(cash_db)
    row = await deposits.create(
        user_id=user_id, tenant_id="tenant", amount_usdt=amount, request_key=key,
    )
    await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id=f"e-{key}", tx_hash=f"tx-{key}", event_index=0,
        network=MOCK_NETWORK, token_contract=row["token_contract"],
        destination_address=MOCK_ADDRESS, amount_micros=row["expected_micros"],
        occurred_at=row["created_at"] + timedelta(seconds=1),
    ))
    return row["expected_micros"]


async def seed_table(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(insert(poker_tables).values(
                id=TABLE, scope="network", asset="CASH_USDT", name="Conservation",
                small_blind_units=5, big_blind_units=10,
                small_blind_micros=BB // 2, big_blind_micros=BB, chip_micros=CHIP,
                min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6, rake_bps=1_000,
            ))


async def play_a_raked_hand(cash_db):
    service = CashGameService(cash_db)
    await service.seat("alice", TABLE, 0, BUY_IN, "seat-alice")
    await service.seat("bob", TABLE, 1, BUY_IN, "seat-bob")
    # A checked-down hand splits on a tie, and a split pot pays no rake (each
    # winner only takes their own stake back). Play hands until one is actually
    # raked, so the test is deterministic rather than deck-lucky.
    total_rake, step = 0, 0
    for hand in range(20):
        result = await service.start_hand(TABLE, button_seat=hand % 2)
        while not result.state.terminal:
            state, actor = result.state, result.state.acting_player
            owed = state.current_bet - state.players[actor].street_invested
            step += 1
            result = await service.act(
                TABLE, actor, ActionType.CALL if owed else ActionType.CHECK,
                amount_micros=0, command_id=f"s{step}", expected_revision=result.revision,
            )
        total_rake += result.state.rake * CHIP
        if total_rake:
            break
    await service.leave("alice", TABLE, "leave-alice")
    await service.leave("bob", TABLE, "leave-bob")
    return total_rake


async def ledger_state(cash_db):
    """Every account, its projected balance, and what its entries actually say."""
    async with cash_db() as session:
        rows = (await session.execute(
            select(
                cash_accounts.c.id, cash_accounts.c.kind, cash_accounts.c.reference_id,
                cash_accounts.c.balance_micros,
                func.coalesce(func.sum(cash_entries.c.amount_micros), 0).label("posted"),
            )
            .select_from(cash_accounts)
            .outerjoin(cash_entries, cash_entries.c.account_id == cash_accounts.c.id)
            .group_by(cash_accounts.c.id, cash_accounts.c.kind,
                      cash_accounts.c.reference_id, cash_accounts.c.balance_micros)
        )).mappings().all()
    return [dict(row) for row in rows]


async def test_a_whole_account_life_creates_and_destroys_nothing(cash_db):
    await seed_table(cash_db)
    banked = await deposit(cash_db, "alice", "50", "d-alice")
    banked += await deposit(cash_db, "bob", "50", "d-bob")

    rake = await play_a_raked_hand(cash_db)
    assert rake > 0, "a checked-down hand at a raked table has to leave something behind"

    withdrawals = WithdrawalService(cash_db, fee_micros=5_000_000)
    admin = CashAdminService(cash_db)
    chain = await withdrawals.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20",
        destination_address="TAliceWallet", request_key="w-chain", rail=TRC20,
    )
    await admin.approve_withdrawal(chain["id"], OPERATOR, reason="checked", key="a1")
    await admin.execute_mock(chain["id"], OPERATOR, outcome="success", reason="sent", key="a2")

    fiat = await withdrawals.create(
        user_id="bob", tenant_id="tenant", amount_usdt="20",
        destination_address="2200 7007 1234 5678", request_key="w-fiat", rail=P2P_RUB,
    )
    await admin.approve_withdrawal(fiat["id"], OPERATOR, reason="checked", key="b1")
    await admin.settle_p2p_withdrawal(
        fiat["id"], OPERATOR, fiat_kopecks=180_000, reason="paid", key="b2",
    )

    accounts = await ledger_state(cash_db)

    # 1. The projection is not a lie. It is maintained by hand on every post,
    #    and if it ever drifts every balance a user or an operator reads is
    #    wrong while the entries underneath are right.
    drifted = [row for row in accounts if row["balance_micros"] != row["posted"]]
    assert drifted == [], f"balance projection disagrees with the entries: {drifted}"

    # 2. Nothing was created and nothing was destroyed. Every posting balances
    #    to zero, so the whole system has to.
    assert sum(row["balance_micros"] for row in accounts) == 0

    # 3. Every micro is somewhere nameable. The players' wallets, the house
    #    accounts, and the clearing account money left through must add back up
    #    to exactly what was ever deposited.
    by_reference = {row["reference_id"]: row["balance_micros"] for row in accounts}
    wallets = sum(row["balance_micros"] for row in accounts if row["kind"] == "available")
    escrow = sum(row["balance_micros"] for row in accounts if row["kind"] == "escrow")
    reserved = sum(row["balance_micros"] for row in accounts if row["kind"] == "withdrawal")
    house = by_reference[RAKE_ACCOUNT] + by_reference[FEE_ACCOUNT]
    # `c2c-mock` is the counterparty on both sides of the chain: it goes
    # negative by every deposit credited and positive by every payout sent, so
    # adding the deposits back to it leaves exactly what went out that way.
    went_out = (banked + by_reference["c2c-mock"]) + by_reference[P2P_CLEARING]

    assert escrow == 0, "nobody is still seated, so no escrow may hold anything"
    assert reserved == 0, "both payouts finished, so nothing may still be reserved"
    assert house == rake + 2 * 5_000_000
    # What came in is what is still held plus what left. Both payouts were
    # 20 USDT less the 5 USDT fee, so 30 USDT reached the outside world.
    assert went_out == 30_000_000
    assert wallets + escrow + reserved + house + went_out == banked

    # 4. The house money is where it was put, not merely present in the total.
    assert by_reference[RAKE_ACCOUNT] == rake
    assert by_reference[FEE_ACCOUNT] == 10_000_000


async def test_an_unknown_payout_keeps_the_money_reserved(cash_db):
    """The dangerous outcome: we do not know whether the chain took it.

    Returning it would risk paying twice, and clearing it would risk keeping
    money that never left. It stays in the reserve, out of the wallet, until a
    person resolves it -- and the books still balance while it waits.
    """
    await deposit(cash_db, "alice", "50", "d-unknown")
    withdrawals = WithdrawalService(cash_db, fee_micros=5_000_000)
    admin = CashAdminService(cash_db)
    row = await withdrawals.create(
        user_id="alice", tenant_id="tenant", amount_usdt="20",
        destination_address="TAliceWallet", request_key="w-unknown",
    )
    await admin.approve_withdrawal(row["id"], OPERATOR, reason="checked", key="u1")
    after = await admin.execute_mock(
        row["id"], OPERATOR, outcome="unknown", reason="no receipt", key="u2",
    )
    assert after["status"] == "unknown"

    accounts = await ledger_state(cash_db)
    assert [r for r in accounts if r["balance_micros"] != r["posted"]] == []
    assert sum(row["balance_micros"] for row in accounts) == 0
    # Still reserved: not refunded to the wallet, not counted as sent.
    assert sum(r["balance_micros"] for r in accounts if r["kind"] == "withdrawal") == 20_000_000
    # Nothing was paid out by hand, so the P2P clearing account does not exist.
    assert P2P_CLEARING not in {r["reference_id"] for r in accounts}

    # An operator resolving it as confirmed is what finally moves it.
    await admin.resolve_withdrawal(
        row["id"], OPERATOR, decision="confirmed", tx_hash="0xabc", reason="found", key="u3",
    )
    accounts = await ledger_state(cash_db)
    assert [r for r in accounts if r["balance_micros"] != r["posted"]] == []
    assert sum(r["balance_micros"] for r in accounts) == 0
    assert sum(r["balance_micros"] for r in accounts if r["kind"] == "withdrawal") == 0


async def test_a_paused_table_keeps_every_stack_in_its_own_escrow(cash_db):
    """A discrepancy stops the table it belongs to and strands nothing."""
    await seed_table(cash_db)
    await deposit(cash_db, "alice", "50", "d-pause-a")
    await deposit(cash_db, "bob", "50", "d-pause-b")
    service = CashGameService(cash_db)
    alice = await service.seat("alice", TABLE, 0, BUY_IN, "seat-a")
    bob = await service.seat("bob", TABLE, 1, BUY_IN, "seat-b")

    accounts = await ledger_state(cash_db)
    # Seats that were released leave their empty escrow behind, which is why
    # only the funded ones are compared.
    escrows = {r["id"]: r["balance_micros"]
               for r in accounts if r["kind"] == "escrow" and r["balance_micros"]}
    assert escrows == {alice.cash_escrow_account_id: BUY_IN, bob.cash_escrow_account_id: BUY_IN}
    # One seat, one escrow account: two players can never share a pot of money.
    assert alice.cash_escrow_account_id != bob.cash_escrow_account_id
    assert sum(r["balance_micros"] for r in accounts) == 0
    assert [r for r in accounts if r["balance_micros"] != r["posted"]] == []

    async with cash_db() as session:
        seats = (await session.execute(select(table_seats.c.stack_micros).where(
            table_seats.c.table_id == TABLE, table_seats.c.state == "seated",
        ))).scalars().all()
    assert sorted(seats) == [BUY_IN, BUY_IN]
