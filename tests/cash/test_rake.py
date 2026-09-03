"""The house takes 10% of what a winner took off the other players.

Never of the winner's own money, never rounded against the player, and never
without the chips leaving the pot -- the settlement invariant in cash/game.py
depends on `state.rake` accounting for every chip that does not reach a stack.
"""
import pytest

from poker.engine import PokerEngine
from poker.models import ActionType

RAKE_BPS = 1_000


def seats(*stacks):
    return [
        {"id": f"u{i}", "name": f"P{i}", "seat": i, "stack": stack, "is_bot": False}
        for i, stack in enumerate(stacks)
    ]


def engine(rake_bps=RAKE_BPS):
    return PokerEngine(exact_chips=True, small_blind=5, big_blind=10, rake_bps=rake_bps)


def test_rake_only_touches_money_taken_off_other_players():
    # Heads up, 5 + 10 blinds, small blind folds: the winner drags 15 chips of
    # which 10 were already theirs, so only the 5 they took is taxed.
    state = engine().new_hand(seats(200, 200), button_seat=0)
    engine().apply_action(state, state.acting_player, ActionType.FOLD, 0)

    assert state.terminal and state.rake == 0  # 10% of 5 floors to nothing
    assert state.players["u1"].stack == 200 - 10 + 15


def test_rake_is_ten_percent_of_the_net_win():
    state = engine().new_hand(seats(200, 200, 200), button_seat=0)
    # u0 opens to 60, both blinds fold: pot 75, u0 put in 60, net win 15.
    engine().apply_action(state, "u0", ActionType.RAISE, 60)
    engine().apply_action(state, "u1", ActionType.FOLD, 0)
    engine().apply_action(state, "u2", ActionType.FOLD, 0)

    assert state.terminal
    assert state.rake == 1  # floor(15 * 0.10)
    assert state.players["u0"].stack == 200 - 60 + 75 - 1


def test_a_big_pot_the_winner_funded_is_taxed_only_on_the_other_stack():
    """The winner has 200 in a 400 pot. Ten percent of the pot would be 40; ten
    percent of what they actually took is 20, and that is the number."""
    eng = engine()
    assert eng._rake(400, 200) == 20
    # And a pot nobody contested beyond the winner is free.
    assert eng._rake(200, 200) == 0


def test_rake_is_off_by_default_and_forbidden_without_exact_chips():
    plain = PokerEngine()
    assert plain.rake_bps == 0
    state = plain.new_hand(seats(200, 200), button_seat=0)
    plain.apply_action(state, state.acting_player, ActionType.FOLD, 0)
    assert state.rake == 0

    with pytest.raises(ValueError, match="exact-chip"):
        PokerEngine(rake_bps=RAKE_BPS)
    with pytest.raises(ValueError, match="rake_bps"):
        PokerEngine(exact_chips=True, small_blind=5, big_blind=10, rake_bps=5_000)


def test_every_chip_leaves_the_pot_at_showdown():
    """Whatever the rake is, stacks plus rake must equal what was put in."""
    eng = engine()
    state = eng.new_hand(seats(200, 200, 200), button_seat=0)
    # The blinds are already off the stacks and inside the pot by now.
    before = sum(player.stack for player in state.players.values()) + state.pot
    eng.apply_action(state, "u0", ActionType.CALL, 0)
    eng.apply_action(state, "u1", ActionType.CALL, 0)
    eng.apply_action(state, "u2", ActionType.CHECK, 0)
    while not state.terminal:
        eng.apply_action(state, state.acting_player, ActionType.CHECK, 0)

    after = sum(player.stack for player in state.players.values())
    assert state.rake >= 0
    assert after + state.rake == before


def test_split_pot_taxes_each_winner_on_their_own_share():
    """Two winners split a 60-chip pot they each put 20 into: each nets 10, and
    10% of 10 is one chip each, so the house takes two and not four."""
    eng = engine()
    pot = {"amount": 60, "contributors": ["u0", "u1", "u2"], "eligible": ["u0", "u1"]}
    own = pot["amount"] // len(pot["contributors"])
    share = pot["amount"] // len(pot["eligible"])
    assert own == 20 and share == 30
    assert eng._rake(share, own) == 1
    assert sum(eng._rake(share, own) for _ in pot["eligible"]) == 2
