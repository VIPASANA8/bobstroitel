import pytest

from online.serialization import deserialize_state, serialize_state
from poker.engine import InvalidAction, PokerEngine
from poker.models import Street


def exact_seats():
    return [
        {"id": "u0", "name": "Zero", "seat": 0, "stack": 100, "is_bot": False},
        {"id": "u1", "name": "One", "seat": 1, "stack": 100, "is_bot": False},
        {"id": "u2", "name": "Two", "seat": 2, "stack": 100, "is_bot": False},
    ]


def test_exact_engine_keeps_integer_chips_through_serialization():
    engine = PokerEngine(exact_chips=True, small_blind=1, big_blind=2)
    state = engine.new_hand(exact_seats(), button_seat=0)
    restored = deserialize_state(serialize_state(state))

    assert state.pot == 3
    assert all(type(value) is int for value in (
        state.pot, state.current_bet, state.min_raise_size,
        *(player.stack for player in state.players.values()),
        *(player.total_invested for player in state.players.values()),
        restored.pot, restored.current_bet,
        *(player.stack for player in restored.players.values()),
    ))


@pytest.mark.parametrize("bad", [100.0, 100.5, True, "100"])
def test_exact_engine_rejects_non_integer_stack_or_action_amount(bad):
    engine = PokerEngine(exact_chips=True, small_blind=1, big_blind=2)
    seats = exact_seats()
    seats[0]["stack"] = bad
    with pytest.raises((InvalidAction, ValueError), match="integer"):
        engine.new_hand(seats, button_seat=0)

    state = engine.new_hand(exact_seats(), button_seat=0)
    with pytest.raises(InvalidAction, match="integer"):
        engine.apply_action(state, state.acting_player, engine.legal_actions(state, state.acting_player)[-1], bad)


def test_exact_showdown_gives_odd_chip_clockwise_after_button():
    engine = PokerEngine(exact_chips=True, small_blind=1, big_blind=2)
    state = engine.new_hand(exact_seats(), button_seat=0)
    state.street = Street.RIVER
    state.pot = 3
    for player in state.players.values():
        player.stack = 99
        player.street_invested = 1
        player.total_invested = 1
        player.folded = player.id == "u1"
    engine.evaluator.score = lambda _hole, _board: (1,)
    engine.evaluator.describe = lambda _hole, _board: "tie"

    engine._showdown(state)

    # From button seat 0 the first eligible winner clockwise is seat 2 because
    # seat 1 folded. It receives the indivisible remainder.
    assert state.players["u0"].stack == 100
    assert state.players["u2"].stack == 101
    assert sum(player.stack for player in state.players.values()) == 300
    assert state.result_details[0]["payouts"] == {"u0": 1, "u2": 2}


def test_exact_side_pots_conserve_every_chip():
    engine = PokerEngine(exact_chips=True, small_blind=1, big_blind=2)
    state = engine.new_hand(exact_seats(), button_seat=0)
    contributions = {"u0": 3, "u1": 5, "u2": 5}
    state.pot = sum(contributions.values())
    for participant_id, contribution in contributions.items():
        player = state.players[participant_id]
        player.stack = 100 - contribution
        player.total_invested = contribution
        player.street_invested = contribution
        player.folded = False
    state.street = Street.RIVER
    scores = {"u0": (9,), "u1": (8,), "u2": (8,)}
    engine.evaluator.score = lambda hole, _board: scores[next(
        pid for pid, player in state.players.items() if player.hole_cards == hole
    )]
    engine.evaluator.describe = lambda _hole, _board: "exact"

    engine._showdown(state)

    assert len(state.result_details) == 2
    assert all(type(player.stack) is int for player in state.players.values())
    assert sum(player.stack for player in state.players.values()) == 300
    assert state.pot == 0
