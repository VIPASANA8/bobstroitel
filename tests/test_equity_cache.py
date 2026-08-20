"""Preflop equity is asked for constantly and depends on almost nothing."""

import time

from poker.equity import _PREFLOP_EQUITY_CACHE, _preflop_key, estimate_multiway_equity


def test_suits_only_matter_as_same_or_not():
    """1326 starting hands collapse to 169 shapes, which is why the cache hits."""
    assert _preflop_key(["Ah", "Kh"]) == _preflop_key(["As", "Ks"]) == "AKs"
    assert _preflop_key(["Ah", "Ks"]) == _preflop_key(["Ad", "Kc"]) == "AKo"
    assert _preflop_key(["Kh", "Ah"]) == "AKs", "order does not matter"
    assert _preflop_key(["Ah", "As"]) == "AAo"


def test_different_hands_never_share_a_key():
    keys = {_preflop_key(pair) for pair in (
        ["Ah", "Kh"], ["Ah", "Ks"], ["Ah", "Qh"], ["Kh", "Qh"], ["2h", "7s"], ["Ah", "As"])}
    assert len(keys) == 6


def test_the_second_ask_is_the_cheap_one():
    _PREFLOP_EQUITY_CACHE.clear()
    t0 = time.perf_counter()
    first = estimate_multiway_equity(["Ah", "Kh"], [], opponents=3, samples=700)
    cold_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    second = estimate_multiway_equity(["As", "Ks"], [], opponents=3, samples=700)
    warm_ms = (time.perf_counter() - t0) * 1000

    assert second == first, "the same shape is the same question"
    assert warm_ms < cold_ms / 10, f"cold {cold_ms:.0f}ms, warm {warm_ms:.0f}ms"


def test_a_board_is_never_served_from_the_cache():
    """Only the preflop question is small enough to repeat. Once there is a
    board the spot is its own, and reusing an answer would be wrong."""
    _PREFLOP_EQUITY_CACHE.clear()
    estimate_multiway_equity(["Ah", "Kh"], ["2c", "7d", "9s"], opponents=2, samples=60)
    assert _PREFLOP_EQUITY_CACHE == {}


def test_opponent_count_is_part_of_the_question():
    _PREFLOP_EQUITY_CACHE.clear()
    heads_up = estimate_multiway_equity(["Ah", "Kh"], [], opponents=1, samples=400)
    five_way = estimate_multiway_equity(["Ah", "Kh"], [], opponents=5, samples=400)
    assert heads_up > five_way, "one opponent is easier to beat than five"


def test_the_cache_cannot_grow_without_limit():
    from poker.equity import _PREFLOP_CACHE_LIMIT

    assert _PREFLOP_CACHE_LIMIT >= 169, "smaller than the shape count would thrash"
    assert _PREFLOP_CACHE_LIMIT <= 20000
