from poker.engine import PokerEngine
from poker.models import ActionType
from online.serialization import deserialize_state, serialize_state


def test_private_snapshot_round_trip_continues_the_same_hand():
    engine = PokerEngine()
    seats = [
        {"id": "u1", "name": "One", "seat": 0, "stack": 100.0, "is_bot": False},
        {"id": "u2", "name": "Two", "seat": 1, "stack": 100.0, "is_bot": False},
    ]
    original = engine.new_hand(seats, button_seat=0)
    actor = original.acting_player
    restored = deserialize_state(serialize_state(original))

    assert restored.deck.cards == original.deck.cards
    assert restored.players["u1"].hole_cards == original.players["u1"].hole_cards
    assert restored.pending_actions == original.pending_actions

    engine.apply_action(original, actor, ActionType.CALL)
    engine.apply_action(restored, actor, ActionType.CALL)
    assert serialize_state(restored) == serialize_state(original)
