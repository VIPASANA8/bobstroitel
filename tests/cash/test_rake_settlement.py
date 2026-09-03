"""The rake has to reach the ledger, not just leave the pot.

`_settle` no longer balances the seats against zero, so the chips the house
keeps must land on a real account inside the same transaction. If they do not,
escrow and the daily reconciliation disagree by exactly the rake.
"""
import pytest
from sqlalchemy import insert, select

from cash.game import CashGameService, RAKE_ACCOUNT
from cash.ledger import CashLedger
from online.schema import cash_accounts, poker_tables, table_seats
from poker.models import ActionType

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]

CHIP = 10_000
BB = 100_000
TABLE = "cash-rake"
BUY_IN = 10_000_000
FUNDED = 20_000_000


async def seed(factory):
    async with factory() as session:
        async with session.begin():
            await session.execute(insert(poker_tables).values(
                id=TABLE, scope="network", asset="CASH_USDT", name="Cash Rake",
                small_blind_units=5, big_blind_units=10,
                small_blind_micros=BB // 2, big_blind_micros=BB, chip_micros=CHIP,
                min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6, rake_bps=1_000,
            ))


async def fund(factory, wallet, amount, key):
    async with factory() as session:
        async with session.begin():
            await CashLedger().post(
                session, scope="cash-rake-test", key=key, kind="deposit",
                reference_id=key, actor="test:fund",
                postings={"external": -amount, wallet: amount},
            )


async def balance(factory, account_id):
    async with factory() as session:
        return await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.id == account_id
        )) or 0


async def rake_balance(factory):
    async with factory() as session:
        account_id = await session.scalar(select(cash_accounts.c.id).where(
            cash_accounts.c.kind == "clearing",
            cash_accounts.c.reference_id == RAKE_ACCOUNT,
        ))
    return await balance(factory, account_id) if account_id else 0


async def check_down(service, table_id, result):
    """Call what is owed, otherwise check, until the hand is over."""
    step = 0
    while not result.state.terminal:
        state, actor = result.state, result.state.acting_player
        owed = state.current_bet - state.players[actor].street_invested
        step += 1
        result = await service.act(
            table_id, actor, ActionType.CALL if owed else ActionType.CHECK,
            amount_micros=0, command_id=f"step-{step}", expected_revision=result.revision,
        )
    return result


async def test_the_rake_lands_on_its_own_account_and_the_chips_still_add_up(cash_db):
    await seed(cash_db)
    await fund(cash_db, "alice-wallet", FUNDED, "fund-alice")
    await fund(cash_db, "bob-wallet", FUNDED, "fund-bob")
    service = CashGameService(cash_db)
    await service.seat("alice", TABLE, 0, BUY_IN, "seat-alice")
    await service.seat("bob", TABLE, 1, BUY_IN, "seat-bob")

    finished = await check_down(service, TABLE, await service.start_hand(TABLE, button_seat=0))
    rake_micros = finished.state.rake * CHIP

    # A hand checked down reaches a flop, so the rake rule is live here. Both
    # players put in 10 chips, so the winner nets 10 and the house takes 1 --
    # or the board splits it, both winners get their own stake back, and the
    # house takes nothing. Anything else means the arithmetic moved.
    assert finished.state.board != []
    split = len(finished.state.winners) > 1
    assert finished.state.rake == (0 if split else 1)
    assert rake_micros <= 3 * BB
    assert await rake_balance(cash_db) == rake_micros

    async with cash_db() as session:
        seats = (await session.execute(select(table_seats).where(
            table_seats.c.table_id == TABLE,
            table_seats.c.state.in_(("seated", "held", "leaving")),
        ))).mappings().all()
    for seat in seats:
        assert await balance(cash_db, seat["cash_escrow_account_id"]) == seat["stack_micros"]
    # What the seats hold plus what the house took is what was bought in.
    assert sum(seat["stack_micros"] for seat in seats) + rake_micros == 2 * BUY_IN

    await service.leave("alice", TABLE, "leave-alice")
    await service.leave("bob", TABLE, "leave-bob")
    wallets = await balance(cash_db, "alice-wallet") + await balance(cash_db, "bob-wallet")
    assert wallets + rake_micros == 2 * FUNDED


async def test_a_table_without_a_rake_still_settles_to_zero(cash_db):
    await seed(cash_db)
    async with cash_db() as session:
        async with session.begin():
            await session.execute(poker_tables.update().where(
                poker_tables.c.id == TABLE
            ).values(rake_bps=0))
    await fund(cash_db, "alice-wallet", FUNDED, "fund-alice")
    await fund(cash_db, "bob-wallet", FUNDED, "fund-bob")
    service = CashGameService(cash_db)
    await service.seat("alice", TABLE, 0, BUY_IN, "seat-alice")
    await service.seat("bob", TABLE, 1, BUY_IN, "seat-bob")

    finished = await check_down(service, TABLE, await service.start_hand(TABLE, button_seat=0))
    assert finished.state.rake == 0
    assert await rake_balance(cash_db) == 0
