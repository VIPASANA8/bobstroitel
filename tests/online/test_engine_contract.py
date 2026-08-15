import pytest

from poker.deck import Deck
from poker.engine import InvalidAction, PokerEngine


def _seats(count):
    return [
        {"id": f"p{seat}", "name": f"P{seat}", "seat": seat, "stack": 100.0, "is_bot": False}
        for seat in range(count)
    ]


def test_engine_rejects_a_seventh_player():
    with pytest.raises(InvalidAction, match="2 to 6"):
        PokerEngine().new_hand(_seats(7), button_seat=0)


def test_deck_can_restore_an_exact_remaining_order():
    deck = Deck.from_remaining(["As", "Kh", "2c"])
    assert deck.draw(2) == ["2c", "Kh"]
    assert deck.cards == ["As"]
