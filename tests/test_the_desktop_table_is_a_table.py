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
    assert 'grid-template-areas:"table"!important' in layout
    assert "grid-template-rows:minmax(0,1fr)!important" in layout
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
    assert "left:-5px!important" in rule
    # Half the avatar, less half the button's own height: it follows the head
    # now that the head has a ceiling.
    assert "top:calc(var(--p8-avatar) / 2 - 13px)!important" in rule
    assert "right:auto!important" in rule and "bottom:auto!important" in rule


def test_the_phones_sizing_controls_form_the_desktop_popover():
    """Desktop reuses the phone's explicit amount, cancel and confirmation
    controls in a transient overlay; only the vertical gesture rail stays
    hidden because a pointer already has the slider."""
    for part in (".mobile-sizing-head", "#mobileSizingConfirm", "#mobileSizingCancel", "#mobileBetRail"):
        assert f"{DESKTOP} {part}" in V039, part


def test_the_action_panel_lives_inside_the_table():
    """The controls cannot own a layout row: changing viewer or turn state
    must not change the table's box. The real panel is moved into the frame
    and becomes a transparent interaction layer over it."""
    assert "frame.appendChild(actionPanel)" in V039
    panel = _rule(V039, f"{DESKTOP} .table-frame > .action-panel")
    assert "position:absolute!important" in panel
    assert "inset:0!important" in panel
    assert "pointer-events:none!important" in panel
    sidebar = _rule(V039, f"{DESKTOP} .sidebar")
    assert "display:none!important" in sidebar


def test_desktop_buttons_reuse_the_phones_four_edge_slots():
    """ALL-IN | CHECK/CALL over FOLD | BET/RAISE, rendered by the same
    controller as the phone and anchored to the two lower table corners."""
    assert 'grid.dataset.v038ReferenceActions = "1"' in V038
    assert 'document.body.classList.contains("poker8-desktop-v2")' in V038
    for edge in ("left", "right"):
        assert f'[data-edge="{edge}"]' in V039
    for slot in ("top", "bottom"):
        assert f'[data-slot="{slot}"]' in V039

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
    frame can be half again that now, so the seats and centre cluster take a
    scale factor. The corner controls use clamp() against the frame."""
    assert "--p8-ui-scale:1;" in V039
    assert "scale(var(--p8-ui-scale,1))" in V040, "the seat transform is v040's"
    centre = _first_rule(V039, f"{DESKTOP} .table-center")
    assert "scale(calc(var(--p8-center-scale) * var(--p8-ui-scale)))" in centre
    actions = _rule(V039, f"{DESKTOP} #actionButtons .action-slot")
    assert "width:clamp(128px,18%,176px)!important" in actions
    # No action row is reserved in any state.
    assert f"{DESKTOP}{{--p8-hud-h:0px!important;}}" in V039
    assert "--p8-hud-h:calc(214px * var(--p8-ui-scale))!important" not in V039
    # Read off .layout, not the frame, to avoid a scale feedback loop.
    assert "function uiScale(layout)" in V039
    # It shrinks as well as grows. The factor only ever grew, so a window
    # smaller than the size these pixel values were drawn at got the
    # full-size furniture on a smaller table: measured at 1067x632, 88px
    # heads on a 964x458 felt and the top plates lying across the pot.
    floor = float(re.search(r"const FLOOR = ([\d.]+);", V039).group(1))
    cap = float(re.search(r"const CAP = ([\d.]+);", V039).group(1))
    assert 0.75 <= floor < 1 < cap <= 1.5, (floor, cap)
    assert "Math.max(FLOOR, grown)" in V039


def test_the_felt_draws_nothing_that_stayed_behind():
    """A sweep of .felt's own children on the live table: the seats and the
    centre cluster take the factor where they are defined, and these are
    everything else it draws. The wager layer's bet markers are display:none
    on this table -- the stake is inside the avatar, which is inside the
    seat -- so there is nothing there to scale."""
    for selector, transform in (
        (".street-splash", "translate(-50%,-50%) scale(calc(.86 * var(--p8-ui-scale)))"),
    ):
        assert f"transform:{transform}!important" in _rule(V039, f"{DESKTOP} {selector}"), selector
    # .v038-ready-countdown was on this list while it could still land on the
    # felt. It now only hangs on the hero's avatar-wrap, inside a seat that
    # already carries the factor, so scaling it here applied it twice.
    assert f"{DESKTOP} .v038-ready-countdown" not in V039
    # Both sit on the felt's bottom edge and have to grow away from it.
    bottom = _rule(V039, f"{DESKTOP} .v038-turn-context")
    assert "transform:translateX(-50%) scale(var(--p8-ui-scale))!important" in bottom
    assert "transform-origin:bottom center!important" in bottom


def test_the_old_action_bar_has_no_layout_job():
    """The sidebar stays in the DOM as the mobile home for the panel, but on
    desktop it contributes no width or height at all."""
    rule = _rule(V039, f"{DESKTOP} .sidebar")
    assert "display:none!important" in rule
    assert 'grid-template-areas:"table" "actions"!important' not in V039
    assert "actionHome.insertBefore(actionPanel" in V039, "mobile restores the original DOM home"


def test_the_controls_go_when_the_seat_is_not_in_the_hand():
    """Folded, or seated after the cards were out: the buttons have nothing
    to do with this hand. The panel keeps its box -- collapsing it mid-hand
    would jump the table."""
    online = Path("static/online-table.js").read_text(encoding="utf-8")
    assert '"p8-not-in-hand",' in online
    assert "!observerMode && Boolean(state?.hand_id) && !viewerInHand" in online
    for control in ("#actionButtons", "#sizingWrap", "#mobileAutoActionBar"):
        assert f"body.v014.poker8-desktop-v2.p8-not-in-hand {control}" in V039, control


def test_everyone_elses_ready_check_shows_on_desktop():
    """v038 gates the tick on p8-can-ready, which is about this viewer's own
    ready button -- so watching a table showed nobody's confirmation."""
    rule = _rule(V039, f"{DESKTOP} .avatar-wrap.v038-viewer-ready .v038-ready-mark")
    assert "display:grid!important" in rule
    v038 = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    # The mark only exists between hands, and never on the hero's own seat --
    # which is what keeps this out of a running hand.
    assert 'data-visual-seat="0"]\')) return;' in v038
    assert "if (game) {" in v038


def test_watching_a_table_never_promotes_somebody_else_to_hero():
    """The trainer finds the hero by profile, and with no active profile to
    match, by "the first player who has one at all". Online that reads the
    first human at the table as you: they took the hero's chair -- the one
    the Сесть invitation belongs in -- and the invitation was dropped with
    it, because it is only offered while your own seat is empty."""
    assert "if (!viewer && !online) {" in V040
    # null === null was the first half: between hands the derived player has
    # no id, and neither does a viewer who is not seated.
    assert "const viewerId = gameState?.viewer_player_id || tableState?.viewer_player_id || null;" in V040
    # And the seat number, which is the answer that exists between hands: sit
    # down and you hold a seat no roster has heard of yet, so the id is null
    # while the server says seated. Without this the watching ring was drawn
    # over your own chair and offered it to you as an empty one, while the
    # header hid the seat buttons because you were -- correctly -- seated.
    assert "tableState?.viewer_seat_no ?? gameState?.viewer_seat_no" in V040
    app = Path("static/app.js").read_text(encoding="utf-8")
    assert "viewer_seat_no: state?.viewer_seat_no ?? null," in app, "tableData has to carry it"
    assert "let viewer = viewerId" in V040
    # And the marker that fed it back: v023 stamps .viewer-seat on chair 0.
    v023 = Path("static/v023-brand-balance-fix.js").read_text(encoding="utf-8")
    assert "if (window.Poker8OnlineTable) return;" in v023
    # The seated ring starts at the hero's chair; the watching one does not
    # use that point until the table is full enough to need it.
    seated = re.search(r"const DESKTOP_LAYOUTS = \{\s*1: \[\[(\d+), (\d+)\]\]", V040)
    watching = re.search(r"const DESKTOP_SPECTATOR_LAYOUTS = \{\s*1: \[\[(\d+), (\d+)\]\]", V040)
    assert seated and watching
    assert int(seated.group(2)) > 60, "the hero sits at the bottom"
    assert int(watching.group(2)) < 40, "watching, the lone player is not in your chair"
