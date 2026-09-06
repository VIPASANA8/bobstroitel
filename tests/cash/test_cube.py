"""CUBE settles on the server, against the same USDT wallet the tables pay from."""
import pytest
from sqlalchemy import func, select

from cash.antifraud import LossLimitReached
from cash.cube import (
    CUBE_ACCOUNT, CashCubeService, CubeError, MAX_STAKE_MICROS,
    MULTIPLIER_TENTHS, STAKE_STEP_MICROS, TARGET_RTP, potential_payout, validate,
)
from cash.holds import CashUserFrozen, take_a_break
from cash.ledger import CashLedger, InsufficientCash
from online.schema import cash_accounts, cube_rounds

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]

STAKE = 1_000_000  # 1 USDT
FUNDED = 20_000_000


async def fund(factory, amount=FUNDED, key="fund-alice"):
    async with factory() as session:
        async with session.begin():
            await CashLedger().post(
                session, scope="cube-test", key=key, kind="deposit",
                reference_id=key, actor="test:fund",
                postings={"external": -amount, "alice-wallet": amount},
            )


async def balance(factory, account_id="alice-wallet"):
    async with factory() as session:
        return int(await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.id == account_id,
        )))


async def test_a_round_moves_the_wallet_by_exactly_what_it_paid(cash_db):
    await fund(cash_db)
    service = CashCubeService(cash_db)
    result = await service.settle("alice", "round-1", STAKE, [2, 5])

    assert result["roll"] in range(1, 7)
    assert result["won"] == (result["roll"] in result["selected"])
    assert result["payout_micros"] == (potential_payout(STAKE, 2) if result["won"] else 0)
    assert result["available_micros"] == FUNDED - STAKE + result["payout_micros"]
    assert await balance(cash_db) == result["available_micros"]


async def test_the_house_account_is_the_other_side_of_every_round(cash_db):
    """Wins are paid out of it and losses fund it, so the two sides of the game
    always add to zero -- which is what the cash reconciliation checks."""
    await fund(cash_db)
    service = CashCubeService(cash_db)
    result = await service.settle("alice", "round-1", STAKE, [1, 2, 3])

    async with cash_db() as session:
        house = int(await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "clearing",
            cash_accounts.c.reference_id == CUBE_ACCOUNT,
        )))
    assert house == STAKE - result["payout_micros"]
    assert house + (await balance(cash_db)) == FUNDED


async def test_the_same_request_id_is_the_same_round_not_a_second_one(cash_db):
    """A retried post must be answered with the face that settled. Redrawing it
    would show the player a result their balance never saw."""
    await fund(cash_db)
    service = CashCubeService(cash_db)
    first = await service.settle("alice", "round-1", STAKE, [2, 5])
    after = await balance(cash_db)
    second = await service.settle("alice", "round-1", STAKE, [2, 5])

    assert second == first
    assert await balance(cash_db) == after
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(cube_rounds)) == 1


async def test_a_stake_past_the_balance_never_posts(cash_db):
    await fund(cash_db, STAKE)
    service = CashCubeService(cash_db)
    with pytest.raises(InsufficientCash):
        await service.settle("alice", "round-1", STAKE * 2, [2, 5])

    assert await balance(cash_db) == STAKE
    async with cash_db() as session:
        assert await session.scalar(select(func.count()).select_from(cube_rounds)) == 0


async def test_a_frozen_account_cannot_play(cash_db):
    await fund(cash_db)
    async with cash_db() as session:
        async with session.begin():
            await take_a_break(session, user_id="alice", tenant_id="tenant", hours=24)

    with pytest.raises(CashUserFrozen):
        await CashCubeService(cash_db).settle("alice", "round-1", STAKE, [2, 5])
    assert await balance(cash_db) == FUNDED


async def test_the_daily_loss_limit_counts_cube_rounds_too(cash_db):
    """A limit a whole game walks around is not a limit: the cube posts no
    hands, so before it was counted here the poker limit never saw its losses."""
    await fund(cash_db)
    service = CashCubeService(cash_db, daily_loss_micros=2_000_000)
    # One face of six pays x6 but comes up rarely; keep rolling until the net
    # is past the limit, which is what the screen is supposed to notice.
    for index in range(200):
        try:
            await service.settle("alice", f"round-{index}", STAKE, [1])
        except LossLimitReached:
            assert FUNDED - (await balance(cash_db)) >= 2_000_000
            return
    pytest.fail("the loss limit never fired over 200 losing-odds rounds")


@pytest.mark.parametrize("stake_micros,selected", [
    (STAKE, [2, 2]),                            # the same face twice is not two faces
    (STAKE, [1, 2, 3, 4]),                      # four of six would pay less than it costs
    (STAKE, [7]),                               # off the die
    (STAKE + 50_000, [2]),                      # off the 0.10 grid
    (MAX_STAKE_MICROS + STAKE_STEP_MICROS, [2]),
    (STAKE_STEP_MICROS - 10_000, [2]),
])
async def test_the_rules_are_enforced_before_any_money_moves(cash_db, stake_micros, selected):
    await fund(cash_db)
    with pytest.raises(CubeError):
        await CashCubeService(cash_db).settle("alice", "bad", stake_micros, selected)
    assert await balance(cash_db) == FUNDED


def test_the_house_edge_lives_in_the_chance_not_in_the_payout():
    """x6 on one face of six is an honest payout; the 20% is taken by dealing
    that face 80% as often. Both together are the 80% RTP CASE8 designed for."""
    for count in (1, 2, 3):
        honest = MULTIPLIER_TENTHS[count] / 10
        assert abs(honest * count / 6 - 1) < 1e-9
        assert abs(honest * (count / 6 * TARGET_RTP) - TARGET_RTP) < 1e-9


def test_the_stake_grid_is_the_one_the_page_offers():
    assert validate(STAKE_STEP_MICROS, [1]) == (1,)
    assert validate(MAX_STAKE_MICROS, [1, 2, 3]) == (1, 2, 3)
    assert potential_payout(MAX_STAKE_MICROS, 1) == 300_000_000
