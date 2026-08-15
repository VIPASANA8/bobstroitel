import random

RANKS = "23456789TJQKA"
SUITS = "shdc"


class Deck:
    def __init__(self):
        self.cards = [rank + suit for rank in RANKS for suit in SUITS]
        random.SystemRandom().shuffle(self.cards)

    @classmethod
    def from_remaining(cls, cards: list[str]) -> "Deck":
        deck = cls.__new__(cls)
        deck.cards = list(cards)
        return deck

    def draw(self, n: int = 1):
        if n == 1:
            return self.cards.pop()
        return [self.cards.pop() for _ in range(n)]
