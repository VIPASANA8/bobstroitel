"""Hole cards flew off the desktop table -- reported as "КАРТЫ УЛЕТАЮТ",
with card backs floating in bare felt and the top seat's pair clipped away
at the table edge.

Two causes, both switched on by the specificity fix in
test_desktop_sizing_outranks_the_phone_layer:

1. v039 carried `.player-cards{top:-80px}` -- a value that had never once
   applied, because until then v038's `top:-13px` won the tie. With a 55px
   card that put the whole pair ~100px above its seat, entirely off it.

2. Even at a sane overhang the top row did not fit. The desktop seat box is
   a fixed height, so its centre needs half the box plus the overhang of
   clear felt above it. The top pole sits at 9% -- 70px on a 780px felt --
   so the box already began 4px above the felt and `overflow:hidden` on
   .table-frame ate the cards. A percentage cannot express a pixel
   shortfall, so the seat top takes a pixel floor via max().
"""

import re
from pathlib import Path

V039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")
V040 = Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")


def _card_overhang():
    match = re.search(
        r"body\.v014\.poker8-v2-sixmax\.poker8-desktop-v2 \.player-cards\{[^}]*?top:(-?\d+)px",
        V039,
    )
    assert match, "desktop .player-cards rule missing"
    return -int(match.group(1))


def _seat_top_floor():
    match = re.search(r"top:max\(var\(--v040-seat-y\),(\d+)px\)", V040)
    assert match, "the desktop seat top no longer has a pixel floor"
    return int(match.group(1))


def _tallest_desktop_seat_box():
    block = V040[V040.index("@media (min-width:781px){"):]
    heights = [int(h) for h in re.findall(r"\.seat\.v040-dynamic-seat\{width:\d+px!important;height:(\d+)px", block)]
    assert heights, "desktop seat box heights missing"
    return max(heights)


def test_the_cards_only_peek_above_the_seat():
    overhang = _card_overhang()
    # -80 put the pair completely clear of its own seat; a card is ~55px, so
    # anything at or past that hides them behind the felt edge instead.
    assert 0 < overhang <= 40, f"top:-{overhang}px lifts the cards off the seat"


def test_the_top_row_is_floored_so_the_box_and_its_cards_clear_the_felt():
    floor = _seat_top_floor()
    needed = _tallest_desktop_seat_box() / 2 + _card_overhang()
    assert floor >= needed, (
        f"floor {floor}px is under the {needed}px the tallest seat box plus its "
        "card overhang needs -- the top row clips again"
    )


def test_the_floor_does_not_flatten_the_hexagon_on_a_tall_felt():
    """It must bind only where the percentage falls short. The upper wings
    sit at 14% -- on the ~780px felt this table actually renders that is
    109px, so the floor has to stay below it or pole and wings collapse
    onto one line."""
    block = V040[V040.index("const SPECTATOR_LAYOUTS = {"):V040.index("const style = document.createElement")]
    line = next(l for l in block.splitlines() if re.match(r"\s*6:", l))
    points = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+),\s*(\d+)\]", line)]
    upper_wing_pct = min(points[1][1], points[5][1])
    assert _seat_top_floor() < upper_wing_pct / 100 * 780
