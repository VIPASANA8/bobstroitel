from poker.engine import PokerEngine
from poker.models import ActionType


def _seats(stacks):
    return [
        {"id": pid, "name": pid, "seat": index, "stack": stack, "is_bot": False}
        for index, (pid, stack) in enumerate(stacks.items())
    ]


def test_short_all_in_does_not_reopen_the_betting():
    """A raiser who already matched the bet may only call a short all-in."""
    engine = PokerEngine()
    # Seats 0/1/2 -> button/SB/BB is a, b, c. Preflop order starts left of BB.
    state = engine.new_hand(_seats({"a": 100.0, "b": 100.0, "c": 15.0}), button_seat=0)

    engine.apply_action(state, "a", ActionType.RAISE, 10.0)
    engine.apply_action(state, "b", ActionType.CALL)
    # c has 14 BB behind the 1 BB blind: an all-in to 15 is short of the 20 minimum.
    engine.apply_action(state, "c", ActionType.ALL_IN)

    assert state.acting_player == "a"
    assert ActionType.RAISE not in engine.legal_actions(state, "a")
    assert ActionType.ALL_IN not in engine.legal_actions(state, "a")
    assert ActionType.CALL in engine.legal_actions(state, "a")


def test_full_raise_still_reopens_the_betting():
    engine = PokerEngine()
    state = engine.new_hand(_seats({"a": 100.0, "b": 100.0, "c": 100.0}), button_seat=0)

    engine.apply_action(state, "a", ActionType.RAISE, 10.0)
    engine.apply_action(state, "b", ActionType.CALL)
    engine.apply_action(state, "c", ActionType.RAISE, 30.0)

    assert ActionType.RAISE in engine.legal_actions(state, "a")
    assert not state.raise_capped


def test_the_cap_clears_on_the_next_street():
    engine = PokerEngine()
    state = engine.new_hand(_seats({"a": 100.0, "b": 100.0, "c": 15.0}), button_seat=0)

    engine.apply_action(state, "a", ActionType.RAISE, 10.0)
    engine.apply_action(state, "b", ActionType.CALL)
    engine.apply_action(state, "c", ActionType.ALL_IN)
    assert state.raise_capped
    engine.apply_action(state, "a", ActionType.CALL)
    engine.apply_action(state, "b", ActionType.CALL)

    assert not state.raise_capped
