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


def test_the_countdown_runs_out_instead_of_starting_over():
    """The result phase counted to result_clear_at -- three seconds before the
    next hand -- while promising the next hand, so the number ran down to one
    and then jumped back up when the phase changed."""
    body = TABLE_JS[TABLE_JS.index("function countdownText"):]
    body = body[:body.index("\n  }")]
    assert "state.next_hand_at ||" in body
    assert len(set(re.findall(r"`([^`]*\$\{seconds\}[^`]*)`", body))) == 1, \
        "one sentence for both phases, or the wording changes mid-count"
