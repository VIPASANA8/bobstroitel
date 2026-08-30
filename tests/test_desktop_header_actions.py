"""Desktop had no take-seat/observe pair, no combos hint, and therefore no
buy-in slider at all -- `showBuyInDialog()`'s only caller is the header's
take-seat click, and the whole `#mobileGameHeader` is `display:none` above
780px (v039). Desktop seating fell through to `#readyPanel`, which calls
`ready()` with no buy-in and lands on a flat 40 BB.

The nodes were always built and state-synced at every width; they were just
parked in a hidden parent. `placeHeaderActions()` moves those same nodes
into the topbar's `.top-actions` on desktop -- no second copy, so no
handler, state sync or glow can drift between the two layouts.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/online-table.js").read_text(encoding="utf-8")
V039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")

#: Start of the *first* phone-only block. Appearance rules must sit after
#: the block closes; phone-layout rules must sit inside it.
FIRST_PHONE_BLOCK = SOURCE.index("@media(max-width:780px){")


def _extract(marker, end_marker):
    start = SOURCE.index(marker)
    return SOURCE[start:SOURCE.index(end_marker, start) + len(end_marker)]


def _run_place(is_phone):
    block = _extract("function placeHeaderActions() {", "\n  }\n")
    harness = """
    const state = {phone: %s, parents: {}, bodyClasses: new Set()};
    const mk = id => ({
      id,
      get parentElement() { return state.parents[id] || null; },
    });
    const seatActions = mk("seatActions");
    const utility = mk("utility");
    const header = {id: "header", append(node) { state.parents[node.id] = header; }};
    const topActions = {id: "topActions", append(node) { state.parents[node.id] = topActions; }};
    state.parents.seatActions = header;
    state.parents.utility = header;
    const mobileQuery = {matches: state.phone};
    const document = {
      getElementById: id => (id === "mobileGameHeader" ? header : null),
      querySelector: sel => (sel === ".topbar .top-actions" ? topActions : null),
      body: {classList: {toggle(name, on) { on ? state.bodyClasses.add(name) : state.bodyClasses.delete(name); }}},
    };
    const $ = id => ({mobileHeaderSeatActions: seatActions, mobileHeaderUtility: utility}[id] || null);
    // Sizing the seat pair is measured against a real rendered font, which
    // this DOM does not have; placing the groups is what is under test here.
    const sizeHeaderSeatButtons = () => {};
    %s
    placeHeaderActions();
    console.log(JSON.stringify({
      seatActionsHost: state.parents.seatActions.id,
      utilityHost: state.parents.utility.id,
      desktopClass: state.bodyClasses.has("p8-desktop-header-actions"),
    }));
    """ % (json.dumps(is_phone), block)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_desktop_moves_both_groups_into_the_topbar():
    out = _run_place(is_phone=False)
    assert out["seatActionsHost"] == "topActions"
    assert out["utilityHost"] == "topActions"


def test_the_desktop_marker_is_only_claimed_once_the_move_happened():
    # #readyPanel is hidden off this class, so claiming it without the
    # buttons actually landing would strand desktop with no way to sit.
    assert _run_place(is_phone=False)["desktopClass"] is True
    assert _run_place(is_phone=True)["desktopClass"] is False


def test_the_phone_keeps_its_buttons_in_the_mobile_header():
    out = _run_place(is_phone=True)
    assert out["seatActionsHost"] == "header"
    assert out["utilityHost"] == "header"


def test_the_readypanel_fallback_is_gated_on_that_same_marker():
    assert ".poker8-online.p8-desktop-header-actions #readyPanel{display:none!important}" in SOURCE


def test_the_reserved_strip_does_not_repeat_the_header_button():
    """It spent a version in the desktop topbar, reporting that a seat request
    had landed -- beside the header's own "В очереди" button, which says the
    same thing in the place the request was made from. Two sources for one fact,
    and it cost the bar the 300px that pushed its controls onto a second row."""
    v039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")
    assert ".topbar > #readyPanel" not in v039
    # The offer card stays hidden on desktop too: the header carries that button.
    assert "body.v014.poker8-desktop-v2:not(.p8-desktop-header-actions) .felt > #readyPanel{" in v039
    # Which leaves the panel with one home, the felt, for the phone.
    assert "if (panel.parentElement !== felt) felt.append(panel);" in SOURCE
    assert "layout.prepend(panel)" not in SOURCE, "the desktop panel used to land outside the felt"


def test_button_appearance_is_no_longer_width_gated():
    """These rules used to sit inside the phone block, which is why desktop
    would have rendered the relocated buttons unstyled."""
    for rule in (
        ".poker8-online .mobile-header-seat-actions button{",
        ".poker8-online .mobile-header-seat-actions button.mode-active{",
        ".poker8-online .mobile-chat-button,",
    ):
        assert SOURCE.index(rule) > FIRST_PHONE_BLOCK, rule
        # After the first phone block *closes* -- i.e. not inside it.
        assert SOURCE.index(rule) > SOURCE.index("\n    }\n", FIRST_PHONE_BLOCK), rule


def test_phone_only_layout_stays_inside_the_phone_block():
    close = SOURCE.index("\n    }\n", FIRST_PHONE_BLOCK)
    for rule in (
        ".poker8-online .mobile-header-seat-actions{order:1;margin:0 4px}",
        ".poker8-online .mobile-header-seat-actions.ready-up-only{",
        ".poker8-online .mobile-header-utility{order:2}",
    ):
        assert FIRST_PHONE_BLOCK < SOURCE.index(rule) < close, rule


def test_the_seat_count_comes_from_the_table_not_a_hardcoded_seven():
    """index.html shipped a literal "/ 7 игроков" from the seven-seat era;
    every table is six-max and carries its own max_seats."""
    block = _extract("function syncTableIdentity(state) {", "\n  }\n")
    assert "table.max_seats" in block
    assert "из ${seats} мест" in block
    assert "7" not in re.sub(r"//.*", "", block)


def test_the_desktop_header_gives_the_relocated_buttons_a_layout():
    for rule in (
        "body.v014.poker8-desktop-v2 .top-actions{",
        "body.v014.poker8-desktop-v2 .mobile-header-seat-actions button{",
        "body.v014.poker8-desktop-v2 .p8-table-identity b{",
    ):
        assert rule in V039, rule
