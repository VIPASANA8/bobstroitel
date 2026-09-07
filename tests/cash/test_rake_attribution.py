"""Whose money the rake was taken out of.

A referral share of Poker income is a share of rake the house actually kept,
and "actually kept off this player" has to be a number, not an estimate. It is
one: the rake of a pot is charged on what the winners took off everybody else,
so the losers of that pot paid it, in the proportion they put it in. This file
holds the engine to that -- including that the parts always add back up to
`state.rake`, which is what the cash settlement posts to the house.
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
    return GameState(board=["4h", "Ah", "6h"], rake=rake)


def hand(eng, *stacks, rake=0):
    """A real hand, wound forward to a flop with the rake already taken so far."""
    state = eng.new_hand(seats(*stacks), button_seat=0)
    state.board = ["4h", "Ah", "6h"]
    state.rake = rake
    return state


def invested(state, **amounts):
    """Put the players in a finished pot: what each one has in it, and the pot."""
    for pid, player in state.players.items():
        player.total_invested = amounts.get(pid, 0)
        player.street_invested = amounts.get(pid, 0)
    state.pot = sum(amounts.values())


def test_the_loser_of_a_folded_pot_pays_all_of_its_rake():
    eng = engine()
    state = hand(eng, 100, 100)
    invested(state, u0=40, u1=40)
    state.players["u1"].folded = True

    eng._award_last_player(state)

    # 10% of the 40 the winner took off u1.
    assert state.rake == 4
    assert state.rake_by_player == {"u1": 4}


def test_two_losers_pay_a_folded_pot_in_proportion_to_what_they_put_in():
    eng = engine()
    state = hand(eng, 200, 200, 200)
    invested(state, u0=60, u1=40, u2=20)
    state.players["u1"].folded = True
    state.players["u2"].folded = True

    eng._award_last_player(state)

    assert state.rake == 6
    assert state.rake_by_player == {"u1": 4, "u2": 2}
    assert sum(state.rake_by_player.values()) == state.rake


def test_the_winner_of_a_folded_pot_never_pays_rake_on_their_own_money():
    eng = engine()
    state = hand(eng, 100, 100)
    invested(state, u0=90, u1=10)
    state.players["u1"].folded = True

    eng._award_last_player(state)

    assert state.rake == 1
    assert "u0" not in state.rake_by_player


def test_an_uncontested_pot_is_free_and_charges_nobody():
    eng = engine()
    state = hand(eng, 100, 100)
    invested(state, u0=40)
    state.players["u1"].folded = True

    eng._award_last_player(state)

    assert state.rake == 0
    assert state.rake_by_player == {}


def test_a_hand_that_never_saw_a_flop_charges_nobody():
    eng = engine()
    state = eng.new_hand(seats(100, 100), button_seat=0)  # no board: no drop
    invested(state, u0=40, u1=40)
    state.players["u1"].folded = True

    eng._award_last_player(state)

    assert (state.rake, state.rake_by_player) == (0, {})


def test_a_showdown_splits_the_rake_between_the_players_who_lost_the_pot():
    eng = engine()
    state = hand(eng, 200, 200, 200)
    for pid in ("u0", "u1", "u2"):
        state.players[pid].hole_cards = []
    invested(state, u0=50, u1=50, u2=50)
    # One winner takes 100 off the other two; the rake is 10 of it.
    eng._charge_rake(state, 10, {"u1": 50, "u2": 50})

    assert state.rake_by_player == {"u1": 5, "u2": 5}


def test_an_odd_rake_is_shared_out_to_the_last_chip_and_never_invented():
    eng = engine()
    state = hand(eng, 200, 200, 200, 200)

    eng._charge_rake(state, 7, {"u1": 10, "u2": 10, "u3": 10})

    assert sum(state.rake_by_player.values()) == 7
    # Deterministic: the remainder goes by player id, not by dictionary order.
    assert state.rake_by_player == {"u1": 3, "u2": 2, "u3": 2}


def test_the_cap_is_shared_out_too_and_still_adds_up():
    """Three big blinds is the ceiling; the split is of what was really taken."""
    eng = engine()
    state = hand(eng, 1_000, 1_000, rake=eng.RAKE_CAP_BB * BB - 1)
    invested(state, u0=500, u1=500)
    state.players["u1"].folded = True

    eng._award_last_player(state)

    assert state.rake == 1
    assert state.rake_by_player == {"u1": 1}


def test_a_full_hand_played_out_attributes_every_chip_of_its_rake():
    eng = engine()
    state = eng.new_hand(seats(300, 300, 300), button_seat=0)
    while not state.terminal:
        actor = state.acting_player
        to_call = eng.to_call(state, actor)
        eng.apply_action(state, actor, ActionType.CALL if to_call else ActionType.CHECK, 0)

    assert state.rake > 0
    assert sum(state.rake_by_player.values()) == state.rake
    # Everybody charged was in the hand, and one pot means its winners paid
    # nothing: the rake came off the players who lost it.
    assert set(state.rake_by_player) <= set(state.seat_order)
    if len(eng.build_side_pots(state)) == 1:
        assert not set(state.rake_by_player) & set(state.winners)


@pytest.mark.parametrize("stacks", [(100, 60, 25), (500, 500, 40), (80, 80, 80, 80)])
def test_side_pots_conserve_the_attribution_whatever_the_stacks(stacks):
    """All-ins build layers, and each layer is raked separately. The sum still
    has to be the number the settlement posts to the house account."""
    eng = engine()
    state = eng.new_hand(seats(*stacks), button_seat=0)
    while not state.terminal:
        actor = state.acting_player
        legal = eng.legal_actions(state, actor)
        move = next(action for action in
                    (ActionType.ALL_IN, ActionType.CALL, ActionType.CHECK) if action in legal)
        eng.apply_action(state, actor, move, 0)

    assert sum(state.rake_by_player.values()) == state.rake
    assert all(share > 0 for share in state.rake_by_player.values())
