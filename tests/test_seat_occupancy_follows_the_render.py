"""v040 read `gameState.players` to decide which seats are taken, and that is
the wrong source: it is the last *dealt* hand's roster, and it outlives the
people in it. On a table that can no longer deal -- one player left, so no
hand ever starts -- it never updates again.

Reproduced live: a table with one bot and a four-player roster laid the felt
out for four. The one real player was pushed from the top pole into a
four-player corner, three empty boxes stood on the ring where the departed
had been, and when the offered seat was one of those four, the Сесть button
was carried off to a player's position instead of the hero chair.

app.js already solved this once -- `playerAtSeat` filters the roster by
`current_seats`. The seat-card it renders is that answer, so it is the only
thing v040 should be reading.
"""

import json
import subprocess
import tempfile
from pathlib import Path

V040 = Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")


def _player_for_seat(has_card, roster, viewer_card=False):
    """Runs the real function against one seat."""
    start = V040.index("  function playerForSeat(gameState, seat) {")
    block = V040[start:V040.index("\n  }\n", start) + 4]
    harness = """
    %s
    const seat = {
      dataset: {seat: "2"},
      querySelector: sel => (%s && sel === ".seat-card"
        ? {classList: {contains: name => name === "viewer-seat" && %s}} : null),
    };
    console.log(JSON.stringify(playerForSeat({players: %s}, seat)));
    """ % (block, json.dumps(has_card), json.dumps(viewer_card), json.dumps(roster))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    try:
        out = subprocess.run(["node", path], capture_output=True, text=True, check=True)
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(out.stdout)


def test_a_roster_entry_alone_does_not_seat_anybody():
    """The bug: the hand's roster still names seat 2, nobody is drawn there."""
    assert _player_for_seat(has_card=False, roster={"ghost": {"id": "ghost", "seat": 2}}) is None


def test_a_drawn_seat_is_taken_even_with_no_roster_entry():
    """Somebody seated during a hand they were not dealt into. app.js draws
    them from current_seats; there is no roster row to find."""
    seated = _player_for_seat(has_card=True, roster={}, viewer_card=True)
    assert seated["seat"] == 2 and seated["isViewerCard"] is True


def test_the_roster_still_names_a_drawn_player():
    """It stays the better source for *who* -- just not for *whether*."""
    seated = _player_for_seat(has_card=True, roster={"p": {"id": "p", "seat": 2}})
    assert seated["id"] == "p"


def test_the_card_is_checked_before_the_roster():
    """Order matters: reading the roster first is what let it win."""
    body = V040[V040.index("function playerForSeat"):V040.index("function orderedActiveSeats")]
    assert body.index('querySelector(".seat-card")') < body.index("gameState?.players")
