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


def test_two_bots_never_click_ready_in_the_same_moment():
    """Independent draws from the band collide. Measured on the live site at
    300ms resolution, the last two checkmarks landed in the same frame on
    every single cycle -- a slot each is what separates them."""
    from datetime import datetime, timezone

    from online.runtime import MAX_READY_SLOTS, TableRuntimeManager

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manager = TableRuntimeManager.__new__(TableRuntimeManager)
    manager._bot_ready_at = {}

    smallest = 99.0
    for trial in range(400):
        table = f"t{trial}"
        manager.schedule_bot_ready(table, set(range(1, MAX_READY_SLOTS + 1)), now)
        moments = sorted((when - now).total_seconds() for when in manager._bot_ready_at[table].values())
        smallest = min(smallest, min(b - a for a, b in zip(moments, moments[1:])))

    assert smallest > 0.4, f"two checkmarks landed {smallest:.2f}s apart"


def test_a_bot_keeps_the_slot_it_was_given():
    """Its beat has to stay put across ticks, or it never becomes due."""
    from datetime import datetime, timedelta, timezone

    from online.runtime import TableRuntimeManager

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    manager = TableRuntimeManager.__new__(TableRuntimeManager)
    manager._bot_ready_at = {}

    manager.schedule_bot_ready("t1", {1, 2}, now)
    first = dict(manager._bot_ready_at["t1"])
    manager.schedule_bot_ready("t1", {1, 2}, now + timedelta(seconds=1))
    assert manager._bot_ready_at["t1"] == first

    # A bot that sits down late queues behind the ones already waiting.
    manager.schedule_bot_ready("t1", {1, 2, 3}, now + timedelta(seconds=1))
    late = manager._bot_ready_at["t1"][3]
    assert late > max(first.values()), "the latecomer went first"


def test_who_is_acting_is_louder_than_which_move_it_is():
    """A bot's own tempo has to beat the per-move jitter, or every bot reads
    the same however much each individual pause wobbles."""
    import statistics

    from bots.persona import persona_for

    medians = {}
    for bot in (f"system-{n:02d}" for n in range(1, 13)):
        patience = persona_for(bot).patience
        medians[bot] = statistics.median(
            bot_think_delay("normal", "flop", patience=patience) for _ in range(300)
        )

    slowest, fastest = max(medians.values()), min(medians.values())
    # The old patience span was 0.7-1.45, so 2.07x was the most it could ever
    # reach even at the extremes; anything above that is the wider span.
    assert slowest / fastest > 2.2, f"bots only differ by {slowest / fastest:.1f}x"
