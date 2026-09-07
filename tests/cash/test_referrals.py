"""Referral binding, the daily settlement, the hold, and the partner's share.

The arithmetic itself is covered without a database in test_referral_math.py.
What is checked here is everything the arithmetic sits inside: a binding that
cannot be changed, a settlement that cannot be run twice for money, a reward
that cannot be released early, and a partner's share that never touches Poker.
"""
from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from cash.cube import CUBE_ACCOUNT
from cash.holds import take_a_break
from cash.referrals import bind, code_for, summary
from cash.settlement import (
    BASE_BPS, BOOST_BPS, CashSettlements, PARTNER_PAYABLE, REFERRAL_PENDING,
)
from online.schema import (
    cash_accounts, cash_transactions, cube_adjustments, cube_rounds, partner_settlements,
    partner_shares, referral_settlements, referrals, users,
)

pytestmark = [pytest.mark.anyio, pytest.mark.postgres]

USDT = 1_000_000
DAY = date(2026, 3, 2)
NOON = datetime.combine(DAY, time(12), tzinfo=timezone.utc)


async def make_user(factory, user_id, telegram_user_id, *, internal=False):
    async with factory() as session:
        async with session.begin():
            await session.execute(users.insert().values(
                id=user_id, telegram_user_id=telegram_user_id, display_name=user_id,
                acquisition_tenant_id="tenant", internal=internal,
            ))


async def code_of(factory, user_id):
    async with factory() as session:
        async with session.begin():
            return await code_for(session, user_id)


async def link(factory, *, user_id, code):
    async with factory() as session:
        async with session.begin():
            return await bind(session, user_id=user_id, code=code, now=NOON - timedelta(days=1))


async def play(factory, user_id, *, house_micros, at=NOON):
    """A settled Cube round with a given result for the house."""
    stake = abs(house_micros)
    payout = 0 if house_micros > 0 else 2 * stake
    async with factory() as session:
        async with session.begin():
            await session.execute(cube_rounds.insert().values(
                id=uuid4().hex, user_id=user_id, request_id=uuid4().hex,
                stake_micros=stake, selected="1,2", roll=1, payout_micros=payout,
                created_at=at,
            ))


async def balance(factory, reference_id):
    async with factory() as session:
        return int(await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "clearing", cash_accounts.c.reference_id == reference_id,
        )) or 0)


async def wallet(factory, user_id):
    async with factory() as session:
        return int(await session.scalar(select(cash_accounts.c.balance_micros).where(
            cash_accounts.c.kind == "available", cash_accounts.c.reference_id == user_id,
        )) or 0)


async def settlements_of(factory, referrer_id):
    async with factory() as session:
        return (await session.execute(select(referral_settlements).where(
            referral_settlements.c.referrer_id == referrer_id,
        ).order_by(referral_settlements.c.period_start))).mappings().all()


def service(factory, *, now=None, **kwargs):
    return CashSettlements(factory, now=now or (lambda: NOON + timedelta(days=1)), **kwargs)


# --- binding ------------------------------------------------------------------

async def test_a_code_belongs_to_one_person_and_does_not_change(cash_db):
    first = await code_of(cash_db, "alice")
    assert first == await code_of(cash_db, "alice")
    assert first != await code_of(cash_db, "bob")


async def test_a_referral_is_bound_once_and_never_rewritten(cash_db):
    await make_user(cash_db, "carol", 3)
    alice_code = await code_of(cash_db, "alice")
    carol_code = await code_of(cash_db, "carol")

    assert await link(cash_db, user_id="bob", code=alice_code) == "alice"
    # A second link, from anybody, is the first link answering again.
    assert await link(cash_db, user_id="bob", code=carol_code) == "alice"

    async with cash_db() as session:
        bound = (await session.execute(select(referrals))).mappings().all()
    assert [(row["user_id"], row["referrer_id"]) for row in bound] == [("bob", "alice")]


async def test_nobody_refers_themselves(cash_db):
    code = await code_of(cash_db, "alice")
    assert await link(cash_db, user_id="alice", code=code) is None


async def test_two_accounts_cannot_refer_each_other(cash_db):
    alice_code = await code_of(cash_db, "alice")
    bob_code = await code_of(cash_db, "bob")

    assert await link(cash_db, user_id="bob", code=alice_code) == "alice"
    # A ring of two is a self-referral with a step in it.
    assert await link(cash_db, user_id="alice", code=bob_code) is None


async def test_an_owner_is_outside_the_players_programme(cash_db):
    await make_user(cash_db, "owner", 4, internal=True)
    owner_code = await code_of(cash_db, "owner")

    assert await link(cash_db, user_id="bob", code=owner_code) is None

    alice_code = await code_of(cash_db, "alice")
    assert await link(cash_db, user_id="owner", code=alice_code) is None


async def test_a_code_nobody_owns_binds_nothing(cash_db):
    assert await link(cash_db, user_id="bob", code="ZZZZZZZZ") is None
    assert await link(cash_db, user_id="bob", code=None) is None


# --- the daily settlement -----------------------------------------------------

async def test_a_day_of_losses_pays_the_referrer_the_boosted_share(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)

    written = await service(cash_db).settle_cube_day(DAY)

    assert len(written) == 1
    row = (await settlements_of(cash_db, "alice"))[0]
    assert row["gross_micros"] == 100 * USDT
    assert row["amount_micros"] == 15 * USDT
    assert row["status"] == "pending"
    assert row["breakdown_json"][0]["rate_bps"] == BOOST_BPS
    # The money left the house and is waiting, not spendable yet.
    assert await balance(cash_db, CUBE_ACCOUNT) == -15 * USDT
    assert await balance(cash_db, REFERRAL_PENDING) == 15 * USDT
    assert await wallet(cash_db, "alice") == 0


async def test_running_the_same_day_again_pays_nothing_more(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db)

    await settlements.settle_cube_day(DAY)
    await settlements.settle_cube_day(DAY)
    await settlements.settle_cube_day(DAY)

    assert len(await settlements_of(cash_db, "alice")) == 1
    assert await balance(cash_db, REFERRAL_PENDING) == 15 * USDT


async def test_a_group_that_won_pays_nothing_and_carries_the_loss(cash_db):
    await make_user(cash_db, "carol", 3)
    code = await code_of(cash_db, "alice")
    await link(cash_db, user_id="bob", code=code)
    await link(cash_db, user_id="carol", code=code)
    await play(cash_db, "bob", house_micros=100 * USDT)
    await play(cash_db, "carol", house_micros=-140 * USDT)

    await service(cash_db).settle_cube_day(DAY)

    row = (await settlements_of(cash_db, "alice"))[0]
    assert row["gross_micros"] == -40 * USDT
    assert row["amount_micros"] == 0
    assert row["carryover_after_micros"] == -40 * USDT
    assert await balance(cash_db, REFERRAL_PENDING) == 0


async def test_yesterdays_loss_is_covered_before_today_pays(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=-50 * USDT, at=NOON)
    await play(cash_db, "bob", house_micros=80 * USDT, at=NOON + timedelta(days=1))

    settlements = service(cash_db, now=lambda: NOON + timedelta(days=2))
    await settlements.settle_cube_day(DAY)
    await settlements.settle_cube_day(DAY + timedelta(days=1))

    first, second = await settlements_of(cash_db, "alice")
    assert first["amount_micros"] == 0
    assert second["carryover_before_micros"] == -50 * USDT
    assert second["base_micros"] == 30 * USDT
    assert second["amount_micros"] == 45 * USDT // 10


async def test_the_rate_drops_to_five_percent_after_thirty_days_of_play(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=10 * USDT, at=NOON)
    later = NOON + timedelta(days=40)
    await play(cash_db, "bob", house_micros=100 * USDT, at=later)

    settlements = service(cash_db, now=lambda: later + timedelta(days=1))
    await settlements.settle_cube_day(DAY)
    await settlements.settle_cube_day(later.date())

    first, second = await settlements_of(cash_db, "alice")
    assert first["amount_micros"] == 15 * USDT // 10
    assert second["breakdown_json"][0]["rate_bps"] == BASE_BPS
    assert second["amount_micros"] == 5 * USDT
    # The boost started at the first round played, not at signing up.
    async with cash_db() as session:
        activated = await session.scalar(select(referrals.c.activated_at).where(
            referrals.c.user_id == "bob",
        ))
    assert activated.replace(tzinfo=timezone.utc) == NOON


async def test_a_player_with_no_referrer_earns_nobody_anything(cash_db):
    await play(cash_db, "bob", house_micros=100 * USDT)

    assert await service(cash_db).settle_cube_day(DAY) == []
    assert await balance(cash_db, CUBE_ACCOUNT) == 0


async def test_an_internal_referrer_is_skipped_by_the_settlement(cash_db):
    await make_user(cash_db, "owner", 4)
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "owner"))
    # Marked internal after the fact, the way a new owner would be.
    async with cash_db() as session:
        async with session.begin():
            await session.execute(users.update().where(users.c.id == "owner").values(internal=True))
    await play(cash_db, "bob", house_micros=100 * USDT)

    assert await service(cash_db).settle_cube_day(DAY) == []


async def test_poker_hands_are_not_cube_and_do_not_move_the_carryover(cash_db):
    """Nothing but `cube_rounds` feeds the Cube side. A rake-funded reward is a
    second source with its own settlements, and it does not exist yet."""
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))

    assert await service(cash_db).settle_cube_day(DAY) == []
    async with cash_db() as session:
        poker = await session.scalar(select(func.count()).select_from(
            referral_settlements
        ).where(referral_settlements.c.source == "poker"))
    assert poker == 0


# --- the hold, the release and the reversal -----------------------------------

async def test_a_reward_is_not_spendable_before_the_hold_runs_out(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db)
    await settlements.settle_cube_day(DAY)

    assert await settlements.release_due() == 0
    assert await wallet(cash_db, "alice") == 0

    settlements.now = lambda: NOON + timedelta(days=8)
    assert await settlements.release_due() == 1
    assert await wallet(cash_db, "alice") == 15 * USDT
    assert await balance(cash_db, REFERRAL_PENDING) == 0
    assert (await settlements_of(cash_db, "alice"))[0]["status"] == "available"

    # And never a second time.
    assert await settlements.release_due() == 0
    assert await wallet(cash_db, "alice") == 15 * USDT


async def test_a_frozen_referrer_keeps_waiting(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db)
    await settlements.settle_cube_day(DAY)
    async with cash_db() as session:
        async with session.begin():
            await take_a_break(session, user_id="alice", tenant_id="tenant", hours=48)

    # The hold has run out, so only the freeze is holding the money back.
    settlements.now = lambda: NOON + timedelta(days=8)
    assert await settlements.release_due() == 0
    assert (await settlements_of(cash_db, "alice"))[0]["status"] == "pending"


async def test_a_reward_inside_its_hold_can_be_taken_back(cash_db):
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db)
    settlement_id = (await settlements.settle_cube_day(DAY))[0]

    assert await settlements.reverse(settlement_id, actor="operator:test") is True

    assert await balance(cash_db, REFERRAL_PENDING) == 0
    assert await balance(cash_db, CUBE_ACCOUNT) == 0
    assert (await settlements_of(cash_db, "alice"))[0]["status"] == "reversed"
    # Reversing twice, or reversing what has already been paid, does nothing.
    assert await settlements.reverse(settlement_id, actor="operator:test") is False

    settlements.now = lambda: NOON + timedelta(days=8)
    assert await settlements.release_due() == 0
    assert await wallet(cash_db, "alice") == 0


# --- the partner --------------------------------------------------------------

async def set_share(factory, *, effective_from, share_bps):
    async with factory() as session:
        async with session.begin():
            await session.execute(partner_shares.insert().values(
                id=uuid4().hex, effective_from=effective_from, share_bps=share_bps,
            ))


async def partner_rows(factory, kind):
    async with factory() as session:
        return (await session.execute(select(partner_settlements).where(
            partner_settlements.c.period_kind == kind,
        ).order_by(partner_settlements.c.period_start))).mappings().all()


async def test_the_partner_shares_what_is_left_after_the_referral_cost(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db, now=lambda: datetime(2026, 4, 5, tzinfo=timezone.utc))
    await settlements.settle_cube_day(DAY)

    await settlements.settle_partner_periods(date(2026, 4, 4))

    month = [row for row in await partner_rows(cash_db, "month")
             if row["period_start"] == date(2026, 3, 1)][0]
    assert month["gross_micros"] == 100 * USDT
    assert month["referral_cost_micros"] == 15 * USDT
    assert month["net_micros"] == 85 * USDT
    assert month["amount_micros"] == 42_500_000
    assert month["posted"] is True
    assert await balance(cash_db, PARTNER_PAYABLE) == 42_500_000


async def test_only_one_cadence_moves_money_and_the_other_is_a_report(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db, now=lambda: datetime(2026, 4, 5, tzinfo=timezone.utc))

    await settlements.settle_partner_periods(date(2026, 4, 4))

    weeks = await partner_rows(cash_db, "week")
    assert weeks and all(row["posted"] is False for row in weeks)
    assert sum(row["gross_micros"] for row in weeks) == 100 * USDT
    # The month paid; the weeks only counted.
    assert await balance(cash_db, PARTNER_PAYABLE) == 50 * USDT


async def test_a_losing_month_is_carried_into_the_next_one(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await play(cash_db, "bob", house_micros=-2_000 * USDT, at=NOON)
    await play(cash_db, "bob", house_micros=5_000 * USDT, at=datetime(2026, 4, 10, tzinfo=timezone.utc))
    settlements = service(cash_db, now=lambda: datetime(2026, 5, 2, tzinfo=timezone.utc))

    await settlements.settle_partner_periods(date(2026, 5, 1))

    march, april = [row for row in await partner_rows(cash_db, "month")
                    if row["period_start"] in (date(2026, 3, 1), date(2026, 4, 1))]
    assert march["amount_micros"] == 0
    assert march["carryover_after_micros"] == -2_000 * USDT
    assert april["carryover_before_micros"] == -2_000 * USDT
    # 5000 - 2000 carried = 3000 to share, half of it the partner's.
    assert april["amount_micros"] == 1_500 * USDT


async def test_an_agreed_cube_expense_comes_off_before_the_share(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=4_000)
    await play(cash_db, "bob", house_micros=1_000 * USDT)
    async with cash_db() as session:
        async with session.begin():
            await session.execute(cube_adjustments.insert().values(
                id=uuid4().hex, occurred_on=DAY, amount_micros=-200 * USDT,
                reason="chargeback", actor="operator:test",
            ))
    settlements = service(cash_db, now=lambda: datetime(2026, 4, 5, tzinfo=timezone.utc))

    await settlements.settle_partner_periods(date(2026, 4, 4))

    month = [row for row in await partner_rows(cash_db, "month")
             if row["period_start"] == date(2026, 3, 1)][0]
    assert month["net_micros"] == 800 * USDT
    assert month["amount_micros"] == 320 * USDT


async def test_changing_the_share_leaves_settled_periods_alone(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await play(cash_db, "bob", house_micros=100 * USDT, at=NOON)
    await play(cash_db, "bob", house_micros=100 * USDT,
               at=datetime(2026, 4, 10, tzinfo=timezone.utc))
    settlements = service(cash_db, now=lambda: datetime(2026, 5, 2, tzinfo=timezone.utc))
    await settlements.settle_partner_periods(date(2026, 3, 31))

    await set_share(cash_db, effective_from=date(2026, 4, 1), share_bps=3_000)
    await settlements.settle_partner_periods(date(2026, 5, 1))

    march, april = [row for row in await partner_rows(cash_db, "month")
                    if row["period_start"] in (date(2026, 3, 1), date(2026, 4, 1))]
    assert (march["share_bps"], march["amount_micros"]) == (5_000, 50 * USDT)
    assert (april["share_bps"], april["amount_micros"]) == (3_000, 30 * USDT)


async def test_settling_the_partner_twice_pays_once(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db, now=lambda: datetime(2026, 4, 5, tzinfo=timezone.utc))

    await settlements.settle_partner_periods(date(2026, 4, 4))
    await settlements.settle_partner_periods(date(2026, 4, 4))

    assert await balance(cash_db, PARTNER_PAYABLE) == 50 * USDT
    async with cash_db() as session:
        posted = await session.scalar(select(func.count()).select_from(cash_transactions).where(
            cash_transactions.c.kind == "cube_profit_share",
        ))
    assert posted == 1


# --- the whole pass -----------------------------------------------------------

async def test_one_pass_settles_the_days_releases_what_is_due_and_pays_the_partner(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await link(cash_db, user_id="bob", code=await code_of(cash_db, "alice"))
    await play(cash_db, "bob", house_micros=100 * USDT)
    settlements = service(cash_db, now=lambda: datetime(2026, 4, 5, tzinfo=timezone.utc))

    first = await settlements.run()
    second = await settlements.run()

    assert first["referral_settlements"] == 1
    assert first["partner_settlements"] > 0
    # The hold runs from when the reward was worked out, so a day settled late
    # still gets its seven days of review rather than landing spendable.
    assert first["released"] == 0
    # A second pass on the same data is a no-op, which is what lets an hourly
    # loop run it.
    assert second == {"referral_settlements": 0, "released": 0, "partner_settlements": 0}
    assert await balance(cash_db, PARTNER_PAYABLE) == 42_500_000

    settlements.now = lambda: datetime(2026, 4, 13, tzinfo=timezone.utc)
    assert (await settlements.run())["released"] == 1
    assert await wallet(cash_db, "alice") == 15 * USDT

    data = None
    async with cash_db() as session:
        async with session.begin():
            data = await summary(session, "alice")
    assert data["invited"] == 1
    assert data["paid_micros"] == 15 * USDT
    assert data["carryover_micros"] == 0


async def test_the_books_balance_to_the_micro_after_a_full_pass(cash_db):
    await set_share(cash_db, effective_from=date(2026, 1, 1), share_bps=5_000)
    await make_user(cash_db, "carol", 3)
    code = await code_of(cash_db, "alice")
    await link(cash_db, user_id="bob", code=code)
    await link(cash_db, user_id="carol", code=code)
    await play(cash_db, "bob", house_micros=333 * USDT + 7)
    await play(cash_db, "carol", house_micros=-111 * USDT - 3)

    await service(cash_db, now=lambda: datetime(2026, 4, 5, tzinfo=timezone.utc)).run()

    async with cash_db() as session:
        total = int(await session.scalar(select(func.coalesce(func.sum(
            cash_accounts.c.balance_micros
        ), 0))))
    # Every posting has two sides: the house funds what the referrer and the
    # partner are owed, and nothing was created on the way.
    assert total == 0
