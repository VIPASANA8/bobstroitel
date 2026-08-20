import random

from online.runtime import (
    _BOT_DIFFICULTY_FACTOR,
    _BOT_STREET_FACTOR,
    _BOT_THINK_BAND,
    _BOT_THINK_CAP,
    bot_think_delay,
)


def test_never_runs_away_however_the_dice_fall():
    """A hung table is worse than a robotic one. Every knob at its extreme --
    hardest bot, slowest street, all-in to call, slowest tempo, and a tank on
    top -- still has to come back inside the cap."""
    rng = random.Random(0)
    for _ in range(2000):
        delay = bot_think_delay("maximum", "river", pressure=9.0, patience=99.0, rng=rng)
        assert 0 < delay <= _BOT_THINK_CAP
    for _ in range(2000):
        delay = bot_think_delay("easy", "preflop", pressure=0.0, patience=0.0, rng=rng)
        assert delay > 0, "and never collapses to an instant move"


def test_a_free_check_is_waved_through_and_a_big_bet_is_stared_at():
    """The pause is the tell: a person does not spend the same time on nothing
    to call as on a bet worth the pot."""
    rng = random.Random(7)
    samples = 400

    def average(pressure):
        return sum(bot_think_delay("normal", "flop", pressure=pressure, rng=rng)
                   for _ in range(samples)) / samples

    assert average(0.0) < average(0.5) < average(1.2)


def test_a_bots_tempo_is_its_own_and_stays_that_way():
    """Persona patience is stable per bot, so a fast player is fast on every
    street rather than randomly quick from one hand to the next."""
    from bots.persona import persona_for

    assert persona_for("system-01") == persona_for("system-01")
    assert persona_for("system-01") != persona_for("system-02")

    rng = random.Random(8)
    samples = 400

    def average(patience):
        return sum(bot_think_delay("normal", "flop", patience=patience, rng=rng)
                   for _ in range(samples)) / samples

    assert average(0.7) < average(1.4)


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


def test_bot_ready_delay_stays_inside_the_afk_deadline():
    """Bots gate the hand now, so a slot past the 30s AFK deadline would let a
    bot sit a human out for being slower than the bot itself."""
    from online.runtime import _BOT_READY_BAND, bot_ready_delay

    rng = random.Random(3)
    lo, hi = _BOT_READY_BAND
    for _ in range(500):
        delay = bot_ready_delay(rng=rng)
        assert lo <= delay <= hi
        assert delay < 30


def test_bot_ready_slots_are_spread_out_not_simultaneous():
    """The whole point: six checkmarks must not land on the same frame."""
    from online.runtime import bot_ready_delay

    rng = random.Random(4)
    slots = [round(bot_ready_delay(rng=rng), 3) for _ in range(6)]
    assert len(set(slots)) == len(slots)
    assert max(slots) - min(slots) > 0.5
