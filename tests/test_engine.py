from poker.engine import PokerEngine
from poker.models import ActionType, Street


def test_new_hand_blinds():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")

    assert state.pot == 1.5
    assert state.players["hero"].street_invested == 0.5
    assert state.players["bot"].street_invested == 1.0
    assert state.acting_player == "hero"


def test_limp_check_goes_to_flop():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")

    engine.apply_action(state, "hero", ActionType.CALL)
    assert state.acting_player == "bot"

    engine.apply_action(state, "bot", ActionType.CHECK)

    assert state.street == Street.FLOP
    assert len(state.board) == 3
    assert state.acting_player == "bot"


def test_raise_call_goes_to_flop():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")

    engine.apply_action(state, "hero", ActionType.RAISE, 3.0)
    engine.apply_action(state, "bot", ActionType.CALL)

    assert state.street == Street.FLOP
    assert len(state.board) == 3
    assert state.pot == 6.0


def test_fold_ends_hand():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")

    engine.apply_action(state, "hero", ActionType.FOLD)

    assert state.terminal is True
    assert state.winner == "bot"
    assert state.pot == 0.0


def test_check_check_flop_advances_turn():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")
    engine.apply_action(state, "hero", ActionType.CALL)
    engine.apply_action(state, "bot", ActionType.CHECK)

    assert state.street == Street.FLOP
    assert state.acting_player == "bot"

    engine.apply_action(state, "bot", ActionType.CHECK)
    engine.apply_action(state, "hero", ActionType.CHECK)

    assert state.street == Street.TURN
    assert len(state.board) == 4


def test_all_in_call_runs_to_showdown():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")

    engine.apply_action(state, "hero", ActionType.ALL_IN)
    assert state.acting_player == "bot"

    engine.apply_action(state, "bot", ActionType.CALL)

    assert state.terminal is True
    assert len(state.board) == 5
    assert state.winner in {"hero", "bot", "tie"}


def test_bb_option_after_limp_is_raise_not_bet():
    engine = PokerEngine()
    state = engine.new_hand(button="hero")
    engine.apply_action(state, "hero", ActionType.CALL)

    legal = engine.legal_actions(state, "bot")
    assert ActionType.CHECK in legal
    assert ActionType.RAISE in legal
    assert ActionType.BET not in legal


def test_custom_persistent_stacks_are_used():
    engine = PokerEngine()
    state = engine.new_hand(button="hero", hero_stack=875.5, bot_stack=1124.5)

    assert state.starting_stacks == {"hero": 875.5, "bot": 1124.5}
    assert state.players["hero"].stack == 875.0
    assert state.players["bot"].stack == 1123.5
