"""Nothing on the felt should announce which opponents are software.

They already play like people -- bot_think_delay gives each one its own
tempo, longer on a big decision, with the occasional tank -- but everything
around that gave them away: the avatar read "AI", it was painted from its
own base hue, the seat plate had its own border rule, and only a bot showed
a "ДУМАЕТ" badge with animated dots while on the clock.

The server keeps knowing (is_bot drives seating, stack caps and the bot
move itself); this is about what a player at the table can see.
"""

import re
from pathlib import Path

RUNTIME = Path("online/runtime.py").read_text(encoding="utf-8")


def _code(source):
    """Without the comments: these assertions are about what runs, and the
    comments deliberately name the old values they replaced."""
    return re.sub(r"//.*", "", source)


APP = _code(Path("static/app.js").read_text(encoding="utf-8"))


def _function(source, name):
    start = source.index(f"function {name}(")
    return source[start:source.index("\n}", start)]


def test_an_avatar_never_reads_ai():
    body = _function(APP, "avatarInitials")
    assert '"AI"' not in body
    assert "isBot" not in body


def test_one_palette_for_everyone_at_the_table():
    body = _function(APP, "avatarHue")
    assert "isBot" not in body and "188" not in body


def test_the_seat_plate_is_drawn_from_one_rule():
    assert 'const typeClass = "seat-human";' in APP
    assert 'isHuman ? "seat-human" : "seat-bot"' not in APP


def test_only_folding_puts_a_badge_over_an_avatar():
    """A human on the clock shows nothing there -- the seat's own glow says
    it -- so a badge that appeared only for bots was a tell."""
    status = re.search(r'const status = folded \? "ПАС"[^;]*;', APP)
    assert status, "the status line moved"
    assert "ДУМАЕТ" not in status.group(0)
    assert "thinking-dots" not in APP


def test_the_panel_says_whose_turn_not_what_they_are():
    assert "БОТ ДУМАЕТ" not in APP
    assert "ХОД СОПЕРНИКА" in APP


def test_the_plate_labels_do_not_grade_the_opponent():
    assert 'DIFFICULTY_LABELS[source.difficulty' not in APP
    assert '(isHuman ? "ИГРОК" : "БОТ")' not in APP


def test_a_bot_is_on_the_same_clock_as_a_person():
    """action_deadline was set only for a non-bot actor, so the ring around a
    bot's avatar had nothing to count and its turn looked unlike anyone
    else's. Nothing times a bot out in practice: the coordinator hands them
    their move before the deadline branch, and bot_think_delay is capped
    well inside the window."""
    for hit in re.findall(r"action_deadline = \(\n(?:.*\n){0,6}?\s*\)", RUNTIME):
        assert "is_bot" not in hit, hit
    assert "timedelta(seconds=30) if state.acting_player else None" in RUNTIME
