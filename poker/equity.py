from __future__ import annotations

import random

from poker.evaluator import HandEvaluator


RANKS = "23456789TJQKA"
SUITS = "shdc"


def estimate_multiway_equity(
    hero_cards: list[str],
    board: list[str],
    opponents: int = 1,
    samples: int = 300,
) -> float:
    """Monte Carlo showdown equity against N random opponent hands."""
    evaluator = HandEvaluator()
    opponents = max(1, int(opponents))
    known = set(hero_cards + board)
    deck = [r + s for r in RANKS for s in SUITS if r + s not in known]
    missing_board = 5 - len(board)
    need = opponents * 2 + missing_board
    if need > len(deck):
        return 0.0

    equity_sum = 0.0
    for _ in range(max(1, samples)):
        drawn = random.sample(deck, need)
        villain_hands = [drawn[i * 2:(i + 1) * 2] for i in range(opponents)]
        runout = list(board) + drawn[opponents * 2:]

        hero_score = evaluator.score(hero_cards, runout)
        scores = [evaluator.score(hand, runout) for hand in villain_hands]
        best = max([hero_score] + scores)
        if hero_score != best:
            continue
        tied = 1 + sum(1 for score in scores if score == best)
        equity_sum += 1.0 / tied

    return equity_sum / max(1, samples)


def estimate_equity(hero_cards: list[str], board: list[str], samples: int = 700) -> float:
    return estimate_multiway_equity(hero_cards, board, opponents=1, samples=samples)
