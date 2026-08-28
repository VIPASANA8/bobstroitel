"""An idle table went on showing the last hand's players.

`state.players` is the roster of the hand that was dealt, not of who is
sitting there now. That is usually harmless -- the next hand refreshes it.
But a table that cannot deal again keeps it for good: micro-a holds a
single bot, one bot has nobody to play, so the table sat in `waiting`
presenting four players who had left long before. Reported as "MICRO A --
there should be one bot".

The seating itself is the only truthful answer while nothing is running,
so `current_seats` now goes to everyone watching an idle table rather than
only to a viewer caught between hands. The client treats it as deciding
who is present (see app.js's playerAtSeat).
"""

from pathlib import Path

RUNTIME = Path("online/runtime.py").read_text(encoding="utf-8")
APP = Path("static/app.js").read_text(encoding="utf-8")


def _snapshot_condition():
    start = RUNTIME.index("current_seats = (")
    return RUNTIME[start:RUNTIME.index(")", RUNTIME.index("else None", start))]


def test_an_idle_table_sends_its_seating_to_everyone():
    """Not just to a seated viewer who missed the hand -- a spectator
    watching a table that cannot deal has no other source of truth."""
    condition = _snapshot_condition()
    assert 'loaded.phase == "waiting"' in condition


def test_it_is_still_sent_for_the_case_it_was_written_for():
    """A viewer seated mid-hand is not in state.players and would otherwise
    have no avatar to render or click ready on."""
    condition = _snapshot_condition()
    assert "participant_id not in loaded.state.players" in condition


def test_the_client_lets_the_seating_decide_who_is_present():
    """Merging it on top of players only ever *added* seats, so the stale
    ones stayed on screen."""
    start = APP.index("const playerAtSeat = seatNo =>")
    block = APP[start:start + 400]
    assert "liveSeating" in block
    assert "if (liveSeating && !liveSeating[seatNo]) return null;" in block


def test_players_still_supplies_the_detail():
    """The seating carries who and how much; the hand carries hole cards and
    the rest, so a confirmed seat still reads from players first."""
    start = APP.index("const playerAtSeat = seatNo =>")
    block = APP[start:start + 400]
    assert "players.find(row => Number(row.seat) === seatNo)" in block
    assert "currentSeatFor(seatNo)" in block
