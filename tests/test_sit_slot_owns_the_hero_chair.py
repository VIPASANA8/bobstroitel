"""While nobody is watching from a seat, the hero's chair is the invitation.

A spectator saw the table with every empty seat hidden -- v040 hides them
so six unused chairs do not become furniture -- which left no visible way
to sit down, and on a one-player table the single bot was placed *in* the
hero chair at 50%/80%, taking the spot the invitation belongs in.

So: one empty seat stays on the felt as the sit control, at the hero's own
position, and no spectator layout may put a player there. The exception is
a full room, where there is no seat to offer and the sixth player uses it.
"""

import re
from pathlib import Path

V040 = Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")

#: The hero's chair. Anything centred here is "where the viewer would sit".
HERO_X, HERO_Y = 50, 80


def _spectator_layouts():
    block = V040[V040.index("const SPECTATOR_LAYOUTS = {"):V040.index("const style = document.createElement")]
    out = {}
    for line in block.splitlines():
        match = re.match(r"\s*(\d):\s*(\[\[.*\]\]),", line)
        if match:
            out[int(match.group(1))] = [
                (int(x), int(y)) for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", match.group(2))
            ]
    return out


def test_a_lone_player_sits_at_the_top_not_in_the_hero_chair():
    layouts = _spectator_layouts()
    assert 1 in layouts, "one player fell through to LAYOUTS, which puts them at 50/80"
    (x, y), = layouts[1]
    assert y < 22, "the top, clear of the pot and board band"


def test_no_layout_but_a_full_room_uses_the_hero_chair():
    for count, points in _spectator_layouts().items():
        near_hero = [p for p in points if abs(p[0] - HERO_X) < 12 and abs(p[1] - HERO_Y) > -1 and p[1] >= 70]
        if count == 6:
            continue  # nothing to offer, so the chair is just a seat
        assert not near_hero, f"{count}-player layout puts somebody at {near_hero}"


def test_every_layout_still_has_a_point_per_player():
    for count, points in _spectator_layouts().items():
        assert len(points) == count, count


def test_one_empty_seat_is_kept_as_the_invitation():
    body = V040[V040.index("const activeSet = new Set(active);"):]
    body = body[:body.index(chr(10) + "  }" + chr(10))]
    assert "sitSeat" in body
    assert "!viewer && count < 6" in body, "not offered to someone already seated, nor in a full room"
    # app.js's renderSeats renders the "Сесть" button into exactly one empty
    # seat and nothing into the rest, so picking our own would place a blank
    # box and hide the real offer.
    assert 'seat.querySelector("[data-add-seat]")' in body, "follow app.js's offered seat"
    assert 'classList.toggle("v040-sit-slot"' in body
    # It has to be shown and positioned like a real seat, or hiding empties
    # would swallow it again.
    assert "activeSet.has(seat) || seat === sitSeat" in body


def test_the_invitation_is_placed_in_the_hero_chair():
    assert f"moveSeatTo(sitSeat, {HERO_X}, {HERO_Y})" in V040
    # And it must not also be swept up by the leftover-seat placement below.
    assert "!activeSet.has(seat) && seat !== sitSeat" in V040


def test_seats_are_placed_before_they_are_revealed():
    """Revealing first meant any failure in between -- a layout short of
    points, a class pair matching neither half of the stylesheet -- left a
    seat on screen with nothing positioning it, so it fell back to
    style.css's seven-seat ring. That is how the Сесть button kept landing
    in the top-left corner. A seat that cannot be placed stays hidden."""
    body = V040[V040.index("function applyDynamicLayoutInner"):]
    body = body[:body.index("\n  }\n")]
    assert body.index("moveSeatTo(sitSeat") < body.index('classList.toggle("v040-dynamic-seat"')
    assert body.index("moveSeatTo(seat, x, y)") < body.index('classList.toggle("v040-empty-seat"')


def test_a_seat_that_is_no_longer_active_loses_its_visual_seat():
    """`data-visual-seat` is how half a dozen layers pin a seat -- at the same
    specificity as v040's own rule, so a stale one is not a tie v040 wins:
    load order decides it, and v040 loses. Measured live: a leftover "1" on
    the seat holding the Сесть button held it at the first chair's arc
    position in the corner (7%/24%) no matter what coordinates it was given.
    Clearing it put the button back in the hero chair (50%/80%)."""
    body = V040[V040.index("function applyDynamicLayoutInner"):]
    body = body[:body.index(chr(10) + "  }" + chr(10))]
    assert "delete seat.dataset.visualSeat" in body
    # Before the placement below, or the rules it frees are still in force
    # while the seat is being measured for its move.
    assert body.index("delete seat.dataset.visualSeat") < body.index("moveSeatTo(sitSeat")


def test_two_spectated_players_sit_side_by_side_on_the_top_band():
    """Facing each other across the middle of the felt (x:12/88, y:50) put
    them level with the pot and board and left the whole top empty. Both go
    up instead, on the same y:14 band 5 and 6 use for their upper wings --
    the band already measured to clear the pot label."""
    (left, right) = sorted(_spectator_layouts()[2])
    assert left[1] == right[1] == 14, "same band, or they do not read as a pair"
    assert left[0] + right[0] == 100, "mirrored about the centre line"
    assert right[0] - left[0] >= 50, "far enough apart to be two sides of a table"
