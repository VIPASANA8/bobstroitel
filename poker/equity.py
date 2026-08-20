from __future__ import annotations

import random

from poker.evaluator import HandEvaluator


RANKS = "23456789TJQKA"
SUITS = "shdc"


#: Preflop equity is asked for constantly and depends on almost nothing: two
#: cards and a number of opponents. Suits only matter as "same or not", so AhKh
#: and AsKs are the same question -- normalising collapses 1326 starting hands
#: to 169. The result is a Monte Carlo estimate either way; reusing one is no
#: less honest than drawing a second sample of the same distribution, and the
#: caller adds its own noise on top before deciding anything.
_PREFLOP_EQUITY_CACHE: dict[tuple[str, int, int], float] = {}
_PREFLOP_CACHE_LIMIT = 4096


def _preflop_key(hero_cards: list[str]) -> str | None:
    if len(hero_cards) != 2:
        return None
    (rank_a, suit_a), (rank_b, suit_b) = hero_cards[0], hero_cards[1]
    high, low = sorted((rank_a, rank_b), key=RANKS.index, reverse=True)
    return f"{high}{low}{'s' if suit_a == suit_b else 'o'}"


def estimate_multiway_equity(
    hero_cards: list[str],
    board: list[str],
    opponents: int = 1,
    samples: int = 300,
) -> float:
    """Monte Carlo showdown equity against N random opponent hands."""
    cache_key = None
    if not board:
        shape = _preflop_key(list(hero_cards))
        if shape is not None:
            cache_key = (shape, max(1, int(opponents)), max(1, int(samples)))
            cached = _PREFLOP_EQUITY_CACHE.get(cache_key)
            if cached is not None:
                return cached

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

    result = equity_sum / max(1, samples)
    if cache_key is not None:
        if len(_PREFLOP_EQUITY_CACHE) >= _PREFLOP_CACHE_LIMIT:
            _PREFLOP_EQUITY_CACHE.clear()
        _PREFLOP_EQUITY_CACHE[cache_key] = result
    return result


def estimate_equity(hero_cards: list[str], board: list[str], samples: int = 700) -> float:
    return estimate_multiway_equity(hero_cards, board, opponents=1, samples=samples)
