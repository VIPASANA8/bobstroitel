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
V038 = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")

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


def test_both_drags_move_the_table():
    """Each side takes what it can up to the shape the other allows: the
    width may stretch the felt to its widest, the height may square it back.
    A hard width cap (1240px) meant dragging the window wider changed
    nothing; one fixed ratio would have the same fault, with the width
    following the height alone."""
    rule = _rule(V039, f"{DESKTOP} .table-frame")
    assert ("width:min(100%,var(--p8-stage-w),"
            "calc((var(--p8-stage-h) - 50px) * var(--p8-felt-widest)))!important") in rule
    assert ("height:min(100%,var(--p8-stage-h),"
            "calc(var(--p8-stage-w) / var(--p8-felt-squarest) + 50px))!important") in rule
    assert "width:min(100%,940px)" not in rule, "the fixed width is what made it square"
    assert "1240px" not in rule, "the cap is what left 230px of black either side"
    # A poker table reads as one at roughly 1.6-1.9.
    band = [float(re.search(rf"--p8-felt-{name}:([\d.]+);", V039).group(1))
            for name in ("squarest", "widest")]
    assert band[0] < band[1], band
    assert 1.6 <= band[0] and band[1] <= 1.9, band


def test_the_table_is_measured_rather_than_remembered():
    """The row already contains the topbar, the gap and the action panel --
    and whatever replaces them later. The CSS numbers are only what the
    first paint uses before the measurement lands."""
    assert "--p8-stage-h:calc(100dvh - 344px)" in V039
    assert f"{DESKTOP}.p8-observer-mode{{--p8-stage-h:calc(100dvh - 150px);}}" in V039
    assert 'document.body.style.setProperty("--p8-stage-h"' in V039
    assert 'document.body.style.setProperty("--p8-stage-w"' in V039
    assert "new ResizeObserver(syncStage)" in V039
    assert '[".left-column", ".layout"]' in V039


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

def test_the_table_photo_is_fitted_to_the_frame_not_the_window():
    """v038 paints it at 100vw, which is the frame's width on a phone and
    wider than the frame on a desktop -- so the frame clipped both ends of
    the table off, more of them the wider the window got."""
    rule = _rule(V039, f"{DESKTOP} .table-frame")
    assert "background-size:100% 100%!important" in rule
    assert "background-position:center!important" in rule
    # v038's rule carries two classes; this one has to outrank it.
    assert "100vw" in V038, "the phone rule this is written against"


def test_what_the_table_draws_grows_with_the_table():
    """Every size on this table is a fixed pixel value tuned at 1240x775. The
    frame can be half again that now, so the seats, the centre cluster and
    the action panel take a scale factor."""
    assert "--p8-ui-scale:1;" in V039
    assert "scale(var(--p8-ui-scale,1))" in V040, "the seat transform is v040's"
    centre = _first_rule(V039, f"{DESKTOP} .table-center")
    assert "scale(calc(.94 * var(--p8-ui-scale)))" in centre
    panel = _rule(V039, f"{DESKTOP} .action-panel")
    assert "transform:scale(var(--p8-ui-scale))!important" in panel
    assert "transform-origin:top center!important" in panel
    # The row has to be as tall as the panel it holds, and an observer's is
    # pinned at 0 elsewhere.
    assert f"{DESKTOP}:not(.p8-observer-mode){{" in V039
    assert "--p8-hud-h:calc(214px * var(--p8-ui-scale))!important" in V039
    # Read off .layout, not the frame: the panel's height is an input to the
    # frame's size, so the frame cannot be the input to the panel's.
    assert "function uiScale(layout)" in V039


def test_the_felt_draws_nothing_that_stayed_behind():
    """A sweep of .felt's own children on the live table: the seats and the
    centre cluster take the factor where they are defined, and these are
    everything else it draws. The wager layer's bet markers are display:none
    on this table -- the stake is inside the avatar, which is inside the
    seat -- so there is nothing there to scale."""
    for selector, transform in (
        (".street-splash", "translate(-50%,-50%) scale(calc(.86 * var(--p8-ui-scale)))"),
        (".v038-ready-countdown", "translate(-50%,-50%) scale(var(--p8-ui-scale))"),
    ):
        assert f"transform:{transform}!important" in _rule(V039, f"{DESKTOP} {selector}"), selector
    # Both sit on the felt's bottom edge and have to grow away from it.
    bottom = _rule(V039, f"{DESKTOP} .v038-turn-context")
    assert "transform:translateX(-50%) scale(var(--p8-ui-scale))!important" in bottom
    assert "transform-origin:bottom center!important" in bottom
