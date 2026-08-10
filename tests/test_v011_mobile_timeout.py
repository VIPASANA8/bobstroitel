
from poker.engine import PokerEngine


def test_timeout_fold_can_fold_when_check_was_available():
    engine = PokerEngine()
    seats = [
        {"id": "hero", "name": "Hero", "seat": 0, "balance": 100.0, "is_bot": False},
        {"id": "bot", "name": "Bot", "seat": 1, "balance": 100.0, "is_bot": True},
    ]
    state = engine.new_hand(seats, button_seat=0)
    # Complete preflop until a postflop actor can check.
    safety = 0
    while not state.terminal and state.street.value == "preflop":
        safety += 1
        assert safety < 10
        pid = state.acting_player
        legal = [a.value for a in engine.legal_actions(state, pid)]
        if "call" in legal:
            from poker.models import ActionType
            engine.apply_action(state, pid, ActionType.CALL)
        elif "check" in legal:
            from poker.models import ActionType
            engine.apply_action(state, pid, ActionType.CHECK)
        else:
            raise AssertionError(legal)
    assert not state.terminal
    pid = state.acting_player
    assert engine.to_call(state, pid) == 0
    engine.timeout_fold(state, pid)
    assert state.players[pid].folded is True
