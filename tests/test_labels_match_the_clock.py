"""Copy that quotes a duration has to quote the one the code actually uses.

These are the labels that drift silently: somebody changes a constant, the
sentence in the interface keeps promising the old number, and nothing fails.
"""

import re
from pathlib import Path

from online.coordinator import ROOM_IDLE_TTL
from online.seating import HOLD_WINDOW

LOBBY_HTML = Path("static/lobby.html").read_text(encoding="utf-8")
LOBBY_JS = Path("static/lobby.js").read_text(encoding="utf-8")
TABLE_JS = Path("static/online-table.js").read_text(encoding="utf-8")


def _russian_minutes(delta):
    """90s -> "1,5 минуты" -- the form the copy is written in."""
    minutes = delta.total_seconds() / 60
    return f"{minutes:g}".replace(".", ",")


def test_the_room_form_quotes_the_lifetime_the_coordinator_enforces():
    assert f"{_russian_minutes(ROOM_IDLE_TTL)} минуты" in LOBBY_HTML


def test_leaving_your_own_room_quotes_the_same_lifetime():
    handler = TABLE_JS[TABLE_JS.index('$("mobileDrawerLeave")'):]
    handler = handler[:handler.index("});")]
    assert f"{_russian_minutes(ROOM_IDLE_TTL)} минуты" in handler


def test_a_held_seat_does_not_promise_more_than_the_hold_window():
    """HOLD_WINDOW is half a minute; "Место сохранено" on its own read as a
    promise that it would be waiting whenever they got back."""
    assert HOLD_WINDOW.total_seconds() == 30
    line = next(l for l in LOBBY_JS.splitlines() if 'seat_state === "held"' in l)
    assert "полминуты" in line, line


def test_every_phase_pill_reads_in_the_same_language():
    """"COUNTDOWN" was the one word of English among ОЖИДАНИЕ, РАЗДАЧА,
    ВСКРЫТИЕ and ПАУЗА."""
    line = next(l for l in TABLE_JS.splitlines() if "ОЖИДАНИЕ" in l and "РАЗДАЧА" in l)
    labels = re.findall(r'"([A-ZА-ЯЁ]+)"', line)
    assert labels and not any(re.fullmatch(r"[A-Z]+", label) for label in labels), labels


def test_stacks_are_measured_in_one_unit_everywhere():
    """The felt writes "40.00 ББ"; one prompt still said "40 BB" in Latin."""
    assert " BB" not in TABLE_JS
    assert "40 ББ" in TABLE_JS
