"""One colour per state, and glow spent where it means something."""

import re
from pathlib import Path

STATIC = Path("static")
ROOT = (STATIC / "style.css").read_text(encoding="utf-8")
TABLE = (STATIC / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
TURN = (STATIC / "v041-poker8-v2-turn-clarity.js").read_text(encoding="utf-8")

#: The measured starting point: 1478 distinct colours over 2050 uses, so the
#: average colour on this project was used 1.4 times. These five are the ones
#: that carry a state, and each is defined once.
STATE_TOKENS = ("--turn", "--act-fold", "--act-check", "--act-raise", "--act-allin")


def test_each_state_colour_is_defined_once():
    for token in STATE_TOKENS:
        assert len(re.findall(rf"^\s*{token}:", ROOT, re.M)) == 1, token


def test_the_action_buttons_take_their_colour_from_the_tokens():
    """Six literals sat here, two of them cyans nobody could tell apart."""
    for action in ("fold", "check", "call", "raise", "all-in"):
        rule = re.search(rf"\.action-slot\.{re.escape(action)}\{{--v038-action:([^;]+);", TABLE)
        assert rule, action
        assert rule.group(1).startswith("var(--act-"), (action, rule.group(1))


def test_check_and_call_are_the_same_colour():
    """They were #55cfff and #39c8ff -- a distinction no eye makes."""
    pair = {re.search(rf"\.action-slot\.{a}\{{--v038-action:([^;]+);", TABLE).group(1)
            for a in ("check", "call")}
    assert len(pair) == 1


def test_a_queued_action_keeps_its_own_colour():
    """Every queued button turned magenta, so queued-fold and queued-raise
    looked alike -- and it spent the turn colour on something that is not
    the turn."""
    rule = TABLE[TABLE.index(".action-slot.queued{"):]
    rule = rule[:rule.index("}")]
    assert "border-color:var(--v038-action)" in rule
    assert "255,59,213" not in rule


def test_the_turn_is_one_colour_on_every_seat():
    """It was hsla(var(--seat-accent), ...) -- cyan on seat 0, violet on seat 5.

    A signal that never looks the same twice cannot be learned.
    """
    highlight = TURN[TURN.index(".p8-turn-gradient .player-avatar{"):]
    highlight = highlight[:highlight.index("@keyframes")]
    assert "--seat-accent" not in highlight
    assert "var(--turn)" in highlight


def test_the_timer_and_the_seat_ring_agree():
    """The two places the turn appears must be the same colour."""
    timer = TABLE[TABLE.index(".v038-turn-timer{"):]
    assert "var(--turn)" in timer[:timer.index("}")]
    assert "var(--turn)" in TURN


def test_magenta_belongs_to_the_turn_alone():
    """Nothing else may reach for it, or it stops meaning anything."""
    for name, source in (("v038", TABLE), ("v041", TURN)):
        for literal in re.findall(r"#(?:ff3[0-9a-f]{2}[a-f0-9]{2}|ff38c7|ff3bd[0-9a-f]|ff39cf)", source, re.I):
            assert False, f"{name} still writes {literal} instead of var(--turn)"


def test_glow_is_off_at_rest():
    """66 elements glowed with nobody to act, so the turn glow was the 67th."""
    assert "body.v014.poker8-v2-sixmax .poker-chip," in TURN
    diet = TURN[TURN.index("body.v014.poker8-v2-sixmax .poker-chip,"):]
    diet = diet[:diet.index("@media (prefers-reduced-motion")]
    assert "filter:none!important" in diet
    #: The acting seat is the exception -- it is what the glow is now for.
    assert ".seat-card:not(.p8-turn-gradient) .player-avatar" in diet


def test_the_cards_keep_depth_and_lose_the_haze():
    """Their glow was cyan at alpha .28 -- what makes a card look like a card
    is the shadow underneath it, not a halo around it."""
    rule = TURN[TURN.index("body.v014.poker8-v2-sixmax .card{"):]
    rule = rule[:rule.index("}")]
    assert "0 6px 14px" in rule and "0 0 " not in rule
