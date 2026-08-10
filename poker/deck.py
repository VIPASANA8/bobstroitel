import random

RANKS = "23456789TJQKA"
SUITS = "shdc"


class Deck:
    def __init__(self):
        self.cards = [rank + suit for rank in RANKS for suit in SUITS]
        random.shuffle(self.cards)

    def draw(self, n: int = 1):
        if n == 1:
            return self.cards.pop()
        return [self.cards.pop() for _ in range(n)]
