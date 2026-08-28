"""The desktop felt was a square that grew taller with the screen.

Measured before: 928x726 at 1440x900 and 928x906 at 1920x1080 -- an aspect
of 1.02, because the width was pinned at 940px while the height followed the
viewport. A poker table reads as one at roughly 1.6-1.9. On top of that the
seat ring was the phone's percentages, worked out against a tall narrow
felt, so on a wide one they left the top third empty and crowded three boxes
along the bottom.

Measured after: 1.70 at 1920, 1.71 at 1440, 1.73 at 1280 watching, and
1.62-1.63 seated at all three.
"""

import re
from pathlib import Path

V039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")
V040 = Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")

DESKTOP = "body.v014.poker8-v2-sixmax.poker8-desktop-v2"


def _rule(source, selector):
    """The last rule for this selector: several of these are written twice
    over and the later one is what applies."""
    starts = [m.start() for m in re.finditer(re.escape(selector) + r"\{", source)]
    assert starts, selector
    start = starts[-1]
    return source[start:source.index("}", start)]


def _first_rule(source, selector):
    start = source.index(selector + "{")
    return source[start:source.index("}", start)]


def test_the_table_holds_its_shape_at_every_size():
    rule = _rule(V039, f"{DESKTOP} .table-frame")
    assert "aspect-ratio:16 / 10!important" in rule
    # The smallest of the column, a cap, and what the free height allows --
    # so the height derives from the ratio and can never overflow the row.
    assert "width:min(100%,1240px,calc(var(--p8-stage-h) * 1.6))!important" in rule
    assert "width:min(100%,940px)" not in rule, "the fixed width is what made it square"


def test_each_state_gets_its_own_height_allowance():
    """A seated player has the action panel under the felt and a watcher does
    not. One shared number squashed the seated table to 2.21: max-height
    stepped in and the ratio broke."""
    assert "--p8-stage-h:calc(100dvh - 344px)" in V039
    assert f"{DESKTOP}.p8-observer-mode{{--p8-stage-h:calc(100dvh - 150px);}}" in V039


def test_the_chat_no_longer_holds_the_width_the_table_needs():
    layout = _rule(V039, f"{DESKTOP} .layout")
    assert 'grid-template-areas:"table" "actions"!important' in layout
    # Rules only: the comment above names the column it replaced.
    assert "330px" not in re.sub(r"/\*.*?\*/", "", layout, flags=re.S),         "the docked column is what the table was missing"
    assert 'grid-template-areas:"table chat"' not in V039
    chat = _first_rule(V039, f"{DESKTOP} #chatPanel")
    assert "display:none!important" in chat
    assert f"{DESKTOP} #chatPanel.is-open{{display:flex!important;}}" in V039


def test_desktop_has_its_own_seat_ring():
    """Sharing one table of percentages is what tied the two together, so a
    phone fix moved the desktop and back again."""
    for name in ("DESKTOP_LAYOUTS", "DESKTOP_SPECTATOR_LAYOUTS"):
        block = V040[V040.index(f"const {name} = {{"):]
        block = block[:block.index("};")]
        counts = {int(m) for m in re.findall(r"^\s*(\d): \[\[", block, re.M)}
        assert counts == {1, 2, 3, 4, 5, 6}, name
    assert "const ringsFor = viewer => (isDesktop()" in V040
    assert "const table = ringsFor(viewer);" in V040


def test_the_desktop_ring_is_wider_than_it_is_tall():
    """On a 16:10 oval the seats belong along the long sides. The phone's
    ring puts three boxes across the bottom, which is what crowded it."""
    block = V040[V040.index("const DESKTOP_SPECTATOR_LAYOUTS = {"):]
    six = re.search(r"6: \[(.+?)\],\n", block).group(1)
    points = [(int(x), int(y)) for x, y in re.findall(r"\[(\d+), (\d+)\]", six)]
    assert len(points) == 6
    xs = sorted({x for x, _ in points})
    assert xs[0] <= 20 and xs[-1] >= 80, "the ring has to reach the long sides"
    bottom = [p for p in points if p[1] > 60]
    assert len(bottom) == 3, bottom


def test_the_centre_reads_the_same_way_as_the_phone():
    """Chips, then the amount, then the board. Desktop had the board above a
    pot below it -- these three sit in normal flow there, so a top
    percentage only nudges them along instead of placing them."""
    centre = _rule(V039, f"{DESKTOP} .table-center")
    assert "display:flex!important" in centre and "flex-direction:column!important" in centre
    # Matched whole: each of these selectors is written more than once here,
    # and "the last rule wins" is per property, not per rule -- the styling
    # rules for .pot-total come after this one.
    for selector, order in ((".pot-chips", 1), (".pot-total", 2), (".board-cards", 3)):
        assert f"{DESKTOP} {selector}{{order:{order}!important;top:auto!important;}}" in V039, selector


def test_the_phones_two_player_nudges_stay_on_the_phone():
    """Two numbers tuned for the phone's 79x83 two-player box carried an
    extra attribute selector, so they outranked the desktop's own geometry
    on a 146x154 box with an 88px avatar: measured, the name plate ran 45px
    through the middle of the face."""
    for part in (".avatar-wrap", ".seat-identity"):
        rule = f'body.v014.poker8-v2-sixmax:not(.poker8-desktop-v2).p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] {part}'
        assert rule in V040, part
    assert 'body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"]' not in V040


def test_the_dealer_button_sits_beside_the_avatar():
    """It was pinned to the bottom-right of the whole seat box, which on a
    146x154 box reads as floating off the seat. The avatar is 88px centred
    there, so its left edge is at 29px."""
    rule = _rule(V039, f"{DESKTOP} .dealer-button")
    assert "left:-5px!important" in rule and "top:31px!important" in rule
    assert "right:auto!important" in rule and "bottom:auto!important" in rule


def test_the_phones_bet_gesture_furniture_is_not_drawn_on_desktop():
    """Desktop has a slider and a row of quick sizes doing the same job.
    Measured with all of them on screen: the confirm button sat on the quick
    sizes and the rail crossed both the sizes and the slider."""
    for part in (".mobile-sizing-head", "#mobileSizingConfirm", "#mobileSizingCancel", "#mobileBetRail"):
        assert f"{DESKTOP} {part}" in V039, part


def test_the_action_panel_is_centred_under_the_table():
    """The sidebar is a two-column grid; with the other panels hidden the
    action panel landed in the second column while still 940px wide, so it
    started at the sidebar's midpoint and ran past the layout's right edge."""
    sidebar = _rule(V039, f"{DESKTOP} .sidebar")
    assert "grid-template-columns:minmax(0,1fr)!important" in sidebar
    panel = _rule(V039, f"{DESKTOP} .action-panel")
    assert "grid-column:1 / -1!important" in panel
    assert "margin-inline:auto!important" in panel


def test_desktop_buttons_take_the_same_arrangement_as_the_phone():
    """ALL-IN | CHECK over FOLD | RAISE. Desktop builds these with a
    different renderer, so the order is set on the grid rather than in the
    list that makes them."""
    for cls, order in (("all-in", 1), ("fold", 3), ("raise", 4)):
        assert f"#actionButtons .action-slot.{cls}{{order:{order}!important;}}" in V039, cls
    assert f"{DESKTOP} #actionButtons .action-slot.call{{order:2!important;}}" in V039
