import random

from online.runtime import _BOT_DIFFICULTY_FACTOR, _BOT_STREET_FACTOR, _BOT_THINK_BAND, bot_think_delay


def test_stays_within_the_widest_possible_band():
    """Even at the extremes (hardest difficulty, slowest street, luckiest
    jitter roll) the delay must not run away -- a hung table is worse than a
    robotic one."""
    rng = random.Random(0)
    lo, hi = _BOT_THINK_BAND
    widest_factor = max(_BOT_DIFFICULTY_FACTOR.values()) * max(_BOT_STREET_FACTOR.values())
    narrowest_factor = min(_BOT_DIFFICULTY_FACTOR.values()) * min(_BOT_STREET_FACTOR.values())
    for _ in range(500):
        delay = bot_think_delay("maximum", "river", rng=rng)
        assert lo * narrowest_factor <= delay <= hi * widest_factor


def test_harder_difficulty_and_later_streets_take_longer_on_average():
    rng = random.Random(1)
    samples = 300

    def average(difficulty, street):
        return sum(bot_think_delay(difficulty, street, rng=rng) for _ in range(samples)) / samples

    assert average("easy", "preflop") < average("maximum", "preflop")
    assert average("normal", "preflop") < average("normal", "river")


def test_an_unknown_difficulty_or_street_falls_back_to_the_neutral_factor():
    rng = random.Random(2)
    delay = bot_think_delay("unknown-difficulty", "unknown-street", rng=rng)
    lo, hi = _BOT_THINK_BAND
    assert lo <= delay <= hi
