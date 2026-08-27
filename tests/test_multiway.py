from poker.engine import PokerEngine
from poker.models import ActionType, Street
from bots.multiway import MultiwayBot


def seats(n=6, stack=1000.0):
    rows = [{"id": "hero", "name": "Вы", "seat": 0, "stack": stack, "is_bot": False, "difficulty": "normal"}]
    for i in range(1, n):
        rows.append({"id": f"bot_{i}", "name": f"Бот {i}", "seat": i, "stack": stack, "is_bot": True, "difficulty": "normal"})
    return rows


def test_6max_positions_and_blinds():
    engine = PokerEngine()
    state = engine.new_hand(seats(6), button_seat=0)

    assert state.players["hero"].position == "BTN"
    assert state.players["bot_1"].position == "SB"
    assert state.players["bot_2"].position == "BB"
    assert state.players["bot_3"].position == "UTG"
    assert state.players["bot_4"].position == "HJ"
    assert state.players["bot_5"].position == "CO"
    assert state.acting_player == "bot_3"
    assert state.pot == 1.5


def test_multiway_limp_round_reaches_flop():
    engine = PokerEngine()
    state = engine.new_hand(seats(4), button_seat=0)

    # Order: bot_3 (CO), hero (BTN), bot_1 (SB), bot_2 (BB)
    engine.apply_action(state, "bot_3", ActionType.CALL)
    engine.apply_action(state, "hero", ActionType.CALL)
    engine.apply_action(state, "bot_1", ActionType.CALL)
    engine.apply_action(state, "bot_2", ActionType.CHECK)

    assert state.street == Street.FLOP
    assert len(state.board) == 3
    # Postflop left of button -> SB seat.
    assert state.acting_player == "bot_1"
    assert state.pot == 4.0


def test_multiway_raise_reopens_action():
    engine = PokerEngine()
    state = engine.new_hand(seats(4), button_seat=0)

    engine.apply_action(state, "bot_3", ActionType.RAISE, 3.0)
    assert state.pending_actions == {"hero", "bot_1", "bot_2"}
    engine.apply_action(state, "hero", ActionType.CALL)
    engine.apply_action(state, "bot_1", ActionType.FOLD)
    engine.apply_action(state, "bot_2", ActionType.RAISE, 8.0)

    assert state.pending_actions == {"hero", "bot_3"}
    assert state.acting_player == "bot_3"


def test_side_pot_distribution_conserves_chips():
    engine = PokerEngine()
    custom = seats(3)
    custom[0]["stack"] = 20.0
    custom[1]["stack"] = 50.0
    custom[2]["stack"] = 100.0
    state = engine.new_hand(custom, button_seat=0)

    # Force all players all-in with unequal stacks through legal actions.
    engine.apply_action(state, state.acting_player, ActionType.ALL_IN)
    while not state.terminal:
        pid = state.acting_player
        legal = engine.legal_actions(state, pid)
        if ActionType.CALL in legal:
            engine.apply_action(state, pid, ActionType.CALL)
        elif ActionType.ALL_IN in legal:
            engine.apply_action(state, pid, ActionType.ALL_IN)
        elif ActionType.CHECK in legal:
            engine.apply_action(state, pid, ActionType.CHECK)
        else:
            engine.apply_action(state, pid, legal[0])

    total = sum(p.stack for p in state.players.values())
    assert abs(total - 170.0) < 1e-6
    assert len(state.board) == 5
    assert state.result_details


def test_multiway_bot_returns_legal_action():
    engine = PokerEngine()
    bot = MultiwayBot(engine)
    state = engine.new_hand(seats(6), button_seat=0)
    pid = state.acting_player
    assert state.players[pid].is_bot
    decision = bot.decide(state, pid)
    assert decision.action in engine.legal_actions(state, pid)


def test_showdown_pays_out_every_chip_of_every_side_pot():
    """The guard in _showdown must hold on an ordinary layered showdown: three
    unequal stacks make three pots, and each one has to reach a player."""
    engine = PokerEngine()
    custom = seats(4)
    for row, stack in zip(custom, (10.0, 40.0, 100.0, 100.0)):
        row["stack"] = stack
    state = engine.new_hand(custom, button_seat=0)

    while not state.terminal:
        pid = state.acting_player
        legal = engine.legal_actions(state, pid)
        if ActionType.ALL_IN in legal:
            engine.apply_action(state, pid, ActionType.ALL_IN)
        elif ActionType.CALL in legal:
            engine.apply_action(state, pid, ActionType.CALL)
        else:
            engine.apply_action(state, pid, legal[0])

    assert abs(sum(p.stack for p in state.players.values()) - 250.0) < 1e-6
    assert state.pot == 0.0
    # Layered, not a single pot: the short stacks cap what they can win.
    assert len(state.result_details) >= 2


def test_showdown_refuses_to_zero_a_pot_it_did_not_pay_out():
    """A side pot with no eligible winner is skipped while the pot is cleared
    unconditionally, so those chips would vanish. Force that shape and confirm
    the guard fires instead of silently losing the money."""
    import pytest

    engine = PokerEngine()
    state = engine.new_hand(seats(3), button_seat=0)
    while not state.terminal:
        pid = state.acting_player
        legal = engine.legal_actions(state, pid)
        engine.apply_action(state, pid, ActionType.ALL_IN if ActionType.ALL_IN in legal else legal[0])

    # Rebuild the finished hand as an unpayable one: chips are in the pot, but
    # every contributor has folded, so build_side_pots yields no eligible list.
    state.terminal = False
    state.street = Street.RIVER
    state.pot = 30.0
    for player in state.players.values():
        player.folded = True
        player.total_invested = 10.0

    with pytest.raises(AssertionError, match="no eligible winner"):
        engine._showdown(state)
