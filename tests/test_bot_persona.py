"""A table of bots must not look like one brain wearing six name tags."""

import random
from collections import Counter

import pytest

from bots.multiway import MultiwayBot
from bots.persona import persona_for


def test_a_bot_plays_the_same_way_every_time_you_meet_it():
    """Style is derived from the id and nothing else, so it survives restarts,
    reseatings and a move to another table -- the way a regular does."""
    for bot_id in ("system-01", "system-17", "system-36"):
        assert persona_for(bot_id) == persona_for(bot_id)


def test_no_two_bots_at_a_table_share_a_style():
    table = [persona_for(f"system-{n:02d}") for n in range(1, 7)]
    assert len({(p.tightness, p.aggression) for p in table}) == 6


def test_styles_actually_spread_rather_than_clustering_on_the_average():
    """A spread that all lands near neutral would be the same bot again."""
    everyone = [persona_for(f"system-{n:02d}") for n in range(1, 37)]
    labels = Counter(p.label for p in everyone)
    assert len(labels) >= 5, f"only {len(labels)} kinds of player: {labels}"
    assert max(labels.values()) < len(everyone) * 0.5, "one style dominates the room"


def test_bet_sizing_stops_being_the_same_number_every_hand():
    """A fixed 0.48-pot raise coming back hand after hand is the loudest tell
    at the table."""
    persona = persona_for("system-04")
    rng = random.Random(11)
    sizes = {round(MultiwayBot._human_sizing(0.48, persona, rng), 4) for _ in range(200)}
    assert len(sizes) > 100, "the same fraction is still being reused"
    assert all(0.15 <= size <= 1.25 for size in sizes), "but never a nonsense size"


def test_two_bots_do_not_pick_the_same_size_for_the_same_spot():
    rng_a, rng_b = random.Random(3), random.Random(3)
    a = MultiwayBot._human_sizing(0.55, persona_for("system-02"), rng_a)
    b = MultiwayBot._human_sizing(0.55, persona_for("system-05"), rng_b)
    assert a != b, "identical dice, identical spot -- only the person differs"


@pytest.mark.parametrize("amount,big_blind,expected", [
    (3.27, 1.0, 3.5),   # under 10bb: snaps to the nearest half blind
    (17.4, 1.0, 18.0),  # above it: to a whole one
    (0.9, 1.0, 1.0),
])
def test_bets_land_on_numbers_a_person_would_pick(amount, big_blind, expected):
    assert MultiwayBot._round_bet(amount, big_blind) == expected


def test_rounding_never_shrinks_a_bet_below_what_was_asked():
    """A raise rounded under the minimum is rejected by the engine, and a
    rejected action pauses the table for good."""
    rng = random.Random(5)
    for _ in range(2000):
        amount = rng.uniform(0.4, 60.0)
        rounded = MultiwayBot._round_bet(amount, 1.0)
        assert rounded >= amount
        # At most one step: half a blind up close, a whole one further up.
        assert rounded - amount <= 1.0, "and never wanders far from the intended size"
