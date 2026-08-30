"""Ending a hand is not permission to expose an uncontested winner's cards."""

import pytest

from poker.engine import PokerEngine
from poker.models import ActionType


def _call_or_check(engine, state):
    legal = engine.legal_actions(state, state.acting_player)
    engine.apply_action(state, state.acting_player,
                        ActionType.CHECK if ActionType.CHECK in legal else ActionType.CALL)


@pytest.mark.parametrize("board_length", [0, 3, 4, 5])
def test_a_fold_win_keeps_the_winners_cards_private_on_every_street(board_length):
    engine = PokerEngine()
    state = engine.new_hand()
    while len(state.board) < board_length:
        _call_or_check(engine, state)
    if board_length:
        engine.apply_action(state, state.acting_player, ActionType.BET, 2)
    engine.apply_action(state, state.acting_player, ActionType.FOLD)
    assert state.terminal and len(state.live_ids()) == 1
    for viewer in [None, *state.seat_order]:
        payload = state.to_dict(viewer_player_id=viewer)
        for pid, player in state.players.items():
            expected = player.hole_cards if pid == viewer and not player.folded else ["??", "??"]
            assert payload["players"][pid]["hole_cards"] == expected


@pytest.mark.parametrize("player_count", [2, 3, 6])
@pytest.mark.parametrize("all_in", [False, True])
def test_real_showdowns_reveal_all_remaining_hands(player_count, all_in):
    engine = PokerEngine()
    state = engine.new_hand([
        {"id": str(i), "name": str(i), "seat": i, "stack": 100}
        for i in range(player_count)
    ])
    if all_in:
        engine.apply_action(state, state.acting_player, ActionType.ALL_IN)
    while not state.terminal:
        _call_or_check(engine, state)
    assert len(state.live_ids()) == player_count
    payload = state.to_dict()
    for pid, player in state.players.items():
        assert payload["players"][pid]["hole_cards"] == player.hole_cards


def test_folded_hands_stay_hidden_at_a_real_showdown():
    engine = PokerEngine()
    state = engine.new_hand([
        {"id": str(i), "name": str(i), "seat": i, "stack": 100}
        for i in range(3)
    ])
    folded = state.acting_player
    engine.apply_action(state, folded, ActionType.FOLD)
    while not state.terminal:
        _call_or_check(engine, state)
    assert len(state.live_ids()) == 2
    payload = state.to_dict()
    for pid, player in state.players.items():
        assert payload["players"][pid]["hole_cards"] == (
            ["??", "??"] if pid == folded else player.hole_cards
        )
