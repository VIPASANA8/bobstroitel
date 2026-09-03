"""The house takes 10% of what the winners took off the other players.

Never of a winner's own money, never past three big blinds in one hand, never
before a flop, and never rounded against the player. `state.rake` has to
account for every chip that leaves a pot without reaching a stack, because the
settlement invariant in cash/game.py balances the seats against exactly that.
"""
import pytest

from poker.engine import PokerEngine
from poker.models import ActionType, GameState

RAKE_BPS = 1_000
SB, BB = 5, 10


def seats(*stacks):
    return [
        {"id": f"u{i}", "name": f"P{i}", "seat": i, "stack": stack, "is_bot": False}
        for i, stack in enumerate(stacks)
    ]


def engine(rake_bps=RAKE_BPS):
    return PokerEngine(exact_chips=True, small_blind=SB, big_blind=BB, rake_bps=rake_bps)


def flopped(rake=0):
    """The cheapest state the rake rule reads: a board, and what it took so far."""
    return GameState(board=["4h", "Ah", "6h"], rake=rake)


def run_to_showdown(eng, state):
    """Everyone calls preflop, then checks the hand down."""
    while not state.terminal:
        actor = state.acting_player
        to_call = eng.to_call(state, actor)
        eng.apply_action(state, actor, ActionType.CALL if to_call else ActionType.CHECK, 0)
    return state


def test_rake_is_ten_percent_of_what_the_winners_took_off_others():
    eng = engine()
    assert eng._rake(150, flopped()) == 15
    # The winner's own stake is out of `taxable` before it ever gets here, so a
    # pot they alone funded is free.
    assert eng._rake(0, flopped()) == 0


def test_rounding_lands_with_the_player():
    eng = engine()
    assert eng._rake(19, flopped()) == 1   # not 1.9, and not 2
    assert eng._rake(9, flopped()) == 0


def test_the_cap_is_three_big_blinds_for_the_whole_hand():
    eng = engine()
    assert eng.RAKE_CAP_BB == 3
    assert eng._rake(10_000, flopped()) == 3 * BB
    # The ceiling is per hand, not per pot: a side pot meets what is left of it.
    assert eng._rake(10_000, flopped(rake=3 * BB - 2)) == 2
    assert eng._rake(10_000, flopped(rake=3 * BB)) == 0


def test_no_flop_no_drop():
    eng = engine()
    assert eng._rake(500, GameState(board=[])) == 0
    assert eng._rake(500, flopped()) == 3 * BB


def test_a_hand_that_ends_before_the_flop_is_free():
    eng = engine()
    state = eng.new_hand(seats(200, 200, 200), button_seat=0)
    eng.apply_action(state, state.acting_player, ActionType.RAISE, 60)
    eng.apply_action(state, state.acting_player, ActionType.FOLD, 0)
    eng.apply_action(state, state.acting_player, ActionType.FOLD, 0)

    assert state.terminal and state.board == []
    assert state.rake == 0
    assert state.players["u0"].stack == 200 - 60 + 75


def test_rake_is_off_by_default_and_forbidden_without_exact_chips():
    plain = PokerEngine()
    assert plain.rake_bps == 0
    state = plain.new_hand(seats(200, 200), button_seat=0)
    plain.apply_action(state, state.acting_player, ActionType.FOLD, 0)
    assert state.rake == 0

    with pytest.raises(ValueError, match="exact-chip"):
        PokerEngine(rake_bps=RAKE_BPS)
    with pytest.raises(ValueError, match="rake_bps"):
        PokerEngine(exact_chips=True, small_blind=SB, big_blind=BB, rake_bps=5_000)


def test_every_chip_leaves_the_pot_at_showdown():
    """Stacks plus rake equal what went in -- the invariant cash/game.py checks."""
    eng = engine()
    state = eng.new_hand(seats(200, 200, 200), button_seat=0)
    before = sum(player.stack for player in state.players.values()) + state.pot
    run_to_showdown(eng, state)

    after = sum(player.stack for player in state.players.values())
    assert state.board != [] and state.rake >= 0
    assert state.rake <= eng.RAKE_CAP_BB * BB
    assert after + state.rake == before


def test_a_split_pot_is_taxed_once_and_shared_evenly():
    """Two winners split a pot they each put 20 into: 60 in, 40 of it theirs,
    so 10% of the remaining 20 is two chips -- taken once, not once each."""
    eng = engine()
    pot = {"amount": 60, "contributors": ["u0", "u1", "u2"], "eligible": ["u0", "u1"]}
    own = pot["amount"] // len(pot["contributors"])
    taxable = pot["amount"] - own * len(pot["eligible"])
    assert own == 20 and taxable == 20
    assert eng._rake(taxable, flopped()) == 2
    assert divmod(pot["amount"] - 2, len(pot["eligible"])) == (29, 0)


def test_an_uncapped_rate_would_have_taken_far_more():
    """Why the cap exists: a stack-sized pot is where a flat percentage bites."""
    eng = engine()
    assert 2_000 * RAKE_BPS // 10_000 == 200
    assert eng._rake(2_000, flopped()) == 30
