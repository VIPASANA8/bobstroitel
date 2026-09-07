"""The arithmetic a referrer is paid by, without a database in the way.

Everything here is one function -- `plan_group` -- fed a day at a time, which
is exactly how the settlement job feeds it. The scenarios are the ones that
can lose money if the order of operations is wrong: a group that is down, a
group that is mixed, a rate that changes underneath a carryover.
"""
from cash.settlement import BASE_BPS, BOOST_BPS, plan_group


USDT = 1_000_000


def chain(days, carryover=0):
    """Settle several days in a row, the way the job does. Returns the plans."""
    plans = []
    for contributions in days:
        plan = plan_group(contributions, carryover)
        carryover = plan.carryover_after_micros
        plans.append(plan)
    return plans


def test_a_referral_that_only_loses_pays_its_referrer_a_share_of_the_loss():
    plan = plan_group([("a", BOOST_BPS, 100 * USDT)])

    assert plan.gross_micros == 100 * USDT
    assert plan.base_micros == 100 * USDT
    assert plan.amount_micros == 15 * USDT
    assert plan.carryover_after_micros == 0


def test_a_referral_that_only_wins_pays_nothing_and_leaves_a_debt():
    plan = plan_group([("a", BOOST_BPS, -100 * USDT)])

    assert plan.amount_micros == 0
    assert plan.carryover_after_micros == -100 * USDT


def test_a_losing_day_is_covered_before_the_next_winning_day_pays():
    first, second = chain([
        [("a", BOOST_BPS, -50 * USDT)],
        [("a", BOOST_BPS, 80 * USDT)],
    ])

    assert first.amount_micros == 0 and first.carryover_after_micros == -50 * USDT
    # 80 covers the 50 first; only the 30 left over is anybody's base.
    assert second.base_micros == 30 * USDT
    assert second.amount_micros == 45 * USDT // 10
    assert second.carryover_after_micros == 0


def test_a_winning_day_does_not_pay_twice_when_the_next_day_loses():
    first, second = chain([
        [("a", BOOST_BPS, 80 * USDT)],
        [("a", BOOST_BPS, -50 * USDT)],
    ])

    assert first.amount_micros == 12 * USDT
    # The reward already paid is not clawed back, and the new loss is carried.
    assert second.amount_micros == 0
    assert second.carryover_after_micros == -50 * USDT


def test_months_of_losses_accumulate_and_none_of_them_expires():
    plans = chain([[("a", BASE_BPS, -10 * USDT)] for _ in range(90)])

    assert all(plan.amount_micros == 0 for plan in plans)
    assert plans[-1].carryover_after_micros == -900 * USDT

    recovery = plan_group([("a", BASE_BPS, 1_000 * USDT)], plans[-1].carryover_after_micros)
    assert recovery.base_micros == 100 * USDT
    assert recovery.amount_micros == 5 * USDT


def test_the_carryover_survives_the_drop_from_the_boosted_rate():
    boosted = plan_group([("a", BOOST_BPS, -200 * USDT)])
    later = plan_group([("a", BASE_BPS, 200 * USDT)], boosted.carryover_after_micros)

    # The rate changed; the debt did not move.
    assert later.base_micros == 0
    assert later.amount_micros == 0
    assert later.carryover_after_micros == 0


def test_leaving_the_boosted_period_with_a_profit_behind_does_not_pay_again():
    boosted = plan_group([("a", BOOST_BPS, 200 * USDT)])
    later = plan_group([("a", BASE_BPS, 100 * USDT)], boosted.carryover_after_micros)

    assert boosted.amount_micros == 30 * USDT
    # The old profit is spent: only the new hundred is a base.
    assert later.base_micros == 100 * USDT
    assert later.amount_micros == 5 * USDT


def test_one_referral_winning_what_another_lost_earns_nothing():
    plan = plan_group([("a", BOOST_BPS, 100 * USDT), ("b", BOOST_BPS, -100 * USDT)])

    assert plan.gross_micros == 0
    assert plan.amount_micros == 0
    assert plan.carryover_after_micros == 0


def test_only_the_group_profit_is_a_base_when_referrals_disagree():
    plan = plan_group([("a", BOOST_BPS, 200 * USDT), ("b", BOOST_BPS, -100 * USDT)])

    assert plan.base_micros == 100 * USDT
    assert plan.amount_micros == 15 * USDT


def test_a_new_referral_in_profit_cannot_ignore_an_old_one_in_loss():
    plan = plan_group([("new", BOOST_BPS, 100 * USDT), ("old", BASE_BPS, -100 * USDT)])

    # The tempting bug: 15% of the new player's 100, out of a group that made
    # the project nothing at all.
    assert plan.amount_micros == 0


def test_an_old_referral_in_profit_carries_a_new_one_in_loss_at_its_own_rate():
    plan = plan_group([("new", BOOST_BPS, -40 * USDT), ("old", BASE_BPS, 100 * USDT)])

    assert plan.base_micros == 60 * USDT
    # The base is the old player's, so it is paid at the old player's 5%.
    assert plan.amount_micros == 3 * USDT
    awards = {award.user_id: award for award in plan.awards}
    assert awards["new"].base_micros == 0
    assert awards["old"].base_micros == 60 * USDT


def test_the_base_is_shared_between_winners_in_proportion_to_what_they_won():
    plan = plan_group([
        ("boosted", BOOST_BPS, 60 * USDT),
        ("plain", BASE_BPS, 40 * USDT),
        ("loser", BASE_BPS, -50 * USDT),
    ])
    awards = {award.user_id: award for award in plan.awards}

    assert plan.base_micros == 50 * USDT
    assert awards["boosted"].base_micros == 30 * USDT
    assert awards["plain"].base_micros == 20 * USDT
    assert plan.amount_micros == 30 * USDT * BOOST_BPS // 10_000 + 20 * USDT * BASE_BPS // 10_000


def test_a_referral_that_crosses_out_of_the_boost_mid_day_is_two_contributions():
    plan = plan_group([("a", BOOST_BPS, 100 * USDT), ("a", BASE_BPS, 100 * USDT)])

    assert plan.amount_micros == 15 * USDT + 5 * USDT


def test_dozens_of_referrals_share_the_base_to_the_last_micro():
    contributions = [(f"win-{index}", BOOST_BPS, 7 * index + 1) for index in range(40)]
    contributions += [(f"lose-{index}", BASE_BPS, -3 * index - 1) for index in range(40)]
    plan = plan_group(contributions)

    assert sum(award.base_micros for award in plan.awards) == plan.base_micros
    assert plan.base_micros == plan.gross_micros


def test_rounding_never_pays_out_more_than_the_rate_allows():
    # A base of one micro at 15% is nothing anybody can be paid.
    plan = plan_group([("a", BOOST_BPS, 1)])
    assert plan.amount_micros == 0

    plan = plan_group([("a", BOOST_BPS, 7)])
    assert plan.amount_micros == 1


def test_the_largest_stake_stays_inside_a_signed_bigint():
    # 50 USDT staked, the ceiling, lost on a single round, times a busy day.
    plan = plan_group([("a", BOOST_BPS, 50 * USDT * 10_000)])
    assert plan.amount_micros == 75_000 * USDT


def test_a_referrer_is_never_paid_out_of_money_the_project_did_not_make():
    """The one invariant the rest of the file is examples of."""
    days = [
        [("a", BOOST_BPS, 137 * USDT), ("b", BASE_BPS, -211 * USDT)],
        [("a", BOOST_BPS, -19 * USDT), ("c", BASE_BPS, 400 * USDT)],
        [("b", BASE_BPS, 3), ("c", BASE_BPS, -1)],
        [("a", BASE_BPS, 9_999), ("b", BASE_BPS, 1)],
    ]
    carryover = 0
    earned = 0
    paid = 0
    for contributions in days:
        plan = plan_group(contributions, carryover)
        carryover = plan.carryover_after_micros
        earned += plan.gross_micros
        paid += plan.amount_micros
        # Each day: the parts add up and nothing is invented.
        assert sum(award.base_micros for award in plan.awards) == plan.base_micros
        assert plan.amount_micros <= plan.base_micros * BOOST_BPS // 10_000
        assert plan.carryover_after_micros <= 0
    assert paid <= max(earned, 0) * BOOST_BPS // 10_000
