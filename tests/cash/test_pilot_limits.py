"""Limits that protect the player, and the pilot, from a bad day.

Three separate rules, all with the same shape: they stop the *next* commitment
and never claw back money already at risk. A limit that ejects a seated player
or seizes a pending payout would do more harm than the thing it prevents.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select, update

from cash.antifraud import LossLimitReached, screen_cash_buy_in
from cash.deposits import DepositService
from cash.game import CashGameService
from cash.holds import (
    CashUserFrozen, MAX_BREAK, MIN_BREAK, assert_not_frozen, clear_expired_breaks, take_a_break,
)
from cash.trc20 import MOCK_ADDRESS, MOCK_NETWORK, TransferEvent
from cash.withdrawals import ActiveWithdrawalExists, WithdrawalService
from online.schema import cash_user_holds, hand_players, hands, poker_tables

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]
NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


async def fund(cash_db, key="fund", amount="50"):
    deposits = DepositService(cash_db)
    deposit = await deposits.create(
        user_id="alice", tenant_id="tenant", amount_usdt=amount, request_key=key,
    )
    await deposits.observe(TransferEvent(
        provider="mock-trc20", external_event_id=f"e-{key}", tx_hash=f"tx-{key}", event_index=0,
        network=MOCK_NETWORK, token_contract=deposit["token_contract"],
        destination_address=MOCK_ADDRESS, amount_micros=deposit["expected_micros"],
        occurred_at=deposit["created_at"] + timedelta(seconds=1),
    ))


async def test_only_one_withdrawal_is_live_at_a_time(cash_db):
    await fund(cash_db)
    service = WithdrawalService(cash_db)
    first = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address="TUserWallet", request_key="w1",
    )
    with pytest.raises(ActiveWithdrawalExists, match="open withdrawal"):
        await service.create(
            user_id="alice", tenant_id="tenant", amount_usdt="10",
            destination_address="TUserWallet", request_key="w2",
        )
    # Replaying the first key is still a replay, not a second withdrawal.
    assert (await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address="TUserWallet", request_key="w1",
    ))["id"] == first["id"]

    # Once it is out of the way the next one goes through.
    await service.cancel(first["id"], "alice")
    second = await service.create(
        user_id="alice", tenant_id="tenant", amount_usdt="10",
        destination_address="TUserWallet", request_key="w3",
    )
    assert second["id"] != first["id"]


async def test_the_break_blocks_money_and_runs_out_on_its_own(cash_db):
    async with cash_db() as session:
        async with session.begin():
            until = await take_a_break(
                session, user_id="alice", tenant_id="tenant", hours=24, now=NOW,
            )
    assert until == NOW + timedelta(hours=24)
    async with cash_db() as session:
        with pytest.raises(CashUserFrozen, match="asked for a break"):
            await assert_not_frozen(session, "alice")

    # Expired, and the account is its own again.
    async with cash_db() as session:
        async with session.begin():
            await session.execute(update(cash_user_holds).where(
                cash_user_holds.c.user_id == "alice"
            ).values(until=datetime.now(timezone.utc) - timedelta(minutes=1)))
    async with cash_db() as session:
        await assert_not_frozen(session, "alice")
    async with cash_db() as session:
        async with session.begin():
            assert await clear_expired_breaks(session) == 1


async def test_a_break_extends_but_never_shortens(cash_db):
    async with cash_db() as session:
        async with session.begin():
            short = await take_a_break(
                session, user_id="alice", tenant_id="tenant", hours=2, now=NOW,
            )
            long = await take_a_break(
                session, user_id="alice", tenant_id="tenant", hours=48, now=NOW,
            )
            # Asking for less than what is already running changes nothing:
            # a break you can call off is not a break.
            again = await take_a_break(
                session, user_id="alice", tenant_id="tenant", hours=1, now=NOW,
            )
    assert short == NOW + timedelta(hours=2)
    assert long == NOW + timedelta(hours=48)
    assert again == long


@pytest.mark.parametrize("hours", [0, -1, 366 * 24, 1.5, "24"])
async def test_a_break_has_to_be_a_real_length(cash_db, hours):
    async with cash_db() as session:
        async with session.begin():
            with pytest.raises(ValueError, match="a break lasts"):
                await take_a_break(session, user_id="alice", tenant_id="tenant", hours=hours)
    assert MIN_BREAK == timedelta(hours=1) and MAX_BREAK == timedelta(days=365)


async def test_a_player_cannot_overwrite_an_operator_hold_with_their_own_break(cash_db):
    async with cash_db() as session:
        async with session.begin():
            await session.execute(insert(cash_user_holds).values(
                user_id="alice", tenant_id="tenant", reason="under review",
                operator_id="operator", until=None,
            ))
    async with cash_db() as session:
        async with session.begin():
            with pytest.raises(CashUserFrozen, match="on hold"):
                await take_a_break(session, user_id="alice", tenant_id="tenant", hours=1)
    # And an operator hold has no expiry to wait out.
    async with cash_db() as session:
        async with session.begin():
            assert await clear_expired_breaks(session) == 0
        with pytest.raises(CashUserFrozen, match="on hold"):
            await assert_not_frozen(session, "alice")


async def seed_loss(cash_db, *, micros, completed_at, table="cash-loss"):
    async with cash_db() as session:
        async with session.begin():
            existing = await session.scalar(
                select(poker_tables.c.id).where(poker_tables.c.id == table)
            )
            if existing is None:
                await session.execute(insert(poker_tables).values(
                    id=table, scope="network", asset="CASH_USDT", name="Loss",
                    small_blind_units=5, big_blind_units=10,
                    small_blind_micros=50_000, big_blind_micros=100_000, chip_micros=10_000,
                    min_buy_in_bb=40, max_buy_in_bb=100, max_seats=6, rake_bps=0,
                ))
            hand_id = f"h-{completed_at.timestamp()}-{micros}"
            await session.execute(insert(hands).values(
                id=hand_id, table_id=table, revision_started=1, button_seat=0,
                board_json=[], terminal=True, completed_at=completed_at,
            ))
            await session.execute(insert(hand_players).values(
                hand_id=hand_id, participant_id="alice", user_id="alice", seat_no=0,
                position="BTN", net_micros=micros,
            ))


async def test_the_daily_loss_limit_counts_a_rolling_day_of_losses(cash_db):
    now = datetime.now(timezone.utc)
    await seed_loss(cash_db, micros=-6_000_000, completed_at=now - timedelta(hours=2))
    async with cash_db() as session:
        # Under the limit, the table keeps selling.
        await screen_cash_buy_in(session, user_id="alice", limit_micros=10_000_000, now=now)

    await seed_loss(cash_db, micros=-5_000_000, completed_at=now - timedelta(hours=1))
    async with cash_db() as session:
        with pytest.raises(LossLimitReached, match="daily loss limit of 10"):
            await screen_cash_buy_in(session, user_id="alice", limit_micros=10_000_000, now=now)
        # Zero is off, and yesterday's losses have rolled out of the window.
        await screen_cash_buy_in(session, user_id="alice", limit_micros=0, now=now)
        await screen_cash_buy_in(
            session, user_id="alice", limit_micros=10_000_000, now=now + timedelta(days=1, hours=1),
        )


async def test_the_limit_is_on_the_net_and_not_on_the_losing_hands(cash_db):
    """Poker loses more pots than it wins; counting those would be a win cap.

    A player up on the day has not lost anything, whatever the individual
    hands did, so the limit follows the wallet rather than the hand history.
    """
    now = datetime.now(timezone.utc)
    await seed_loss(cash_db, micros=+50_000_000, completed_at=now - timedelta(hours=3))
    await seed_loss(cash_db, micros=-11_000_000, completed_at=now - timedelta(hours=1))
    async with cash_db() as session:
        # Down 11 on one hand but up 39 overall: nothing has been lost.
        await screen_cash_buy_in(session, user_id="alice", limit_micros=10_000_000, now=now)

    # Give back the winnings and then some, and the net crosses the line.
    await seed_loss(cash_db, micros=-50_000_000, completed_at=now - timedelta(minutes=30))
    async with cash_db() as session:
        with pytest.raises(LossLimitReached, match="daily loss limit of 10"):
            await screen_cash_buy_in(session, user_id="alice", limit_micros=10_000_000, now=now)


async def test_the_limit_stops_the_next_buy_in_and_never_a_seated_player(cash_db):
    await fund(cash_db, key="fund-seat")
    now = datetime.now(timezone.utc)
    await seed_loss(cash_db, micros=-20_000_000, completed_at=now - timedelta(hours=1),
                    table="cash-seat-limit")
    service = CashGameService(cash_db, daily_loss_micros=10_000_000)
    with pytest.raises(LossLimitReached):
        await service.seat("alice", "cash-seat-limit", 0, 10_000_000, "seat-blocked")
    # Nothing was taken: the refusal happens before any money moves.
    async with cash_db() as session:
        seated = await session.scalar(select(hand_players.c.user_id).where(
            hand_players.c.user_id == "alice", hand_players.c.net_micros > 0,
        ))
    assert seated is None
    # With the limit off, the same buy-in is ordinary.
    assert (await CashGameService(cash_db).seat(
        "alice", "cash-seat-limit", 0, 10_000_000, "seat-ok",
    )).stack_micros == 10_000_000
