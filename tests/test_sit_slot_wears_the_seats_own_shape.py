"""The invitation to sit is a chair, so it takes the chair's shape.

It used to be a 29px dashed dot floating inside a 44px button with the word
tucked underneath: next to a real seat it read as a stray control rather
than a place at the table. It now takes the avatar's own circle, in the
avatar's own position, with the label where the name plate goes.

Those numbers belong to v038 (phone) and v039 (desktop), so they are read
back out of those layers here: if the avatar is ever resized, this fails
rather than leaving the empty chair a different size from the taken ones.
"""

import re
from pathlib import Path

STATIC = Path("static")
V038 = (STATIC / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
V039 = (STATIC / "v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")
V040 = (STATIC / "v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")


def _sit_vars(selector):
    """The custom properties v040 hands the sit slot for one mode."""
    block = V040[V040.index(selector):]
    block = block[:block.index("}")]
    return {name: float(value)
            for name, value in re.findall(r"--p8-sit-([a-z-]+):(-?[\d.]+)px", block)}


def _last_rule_text(source, selector, prop):
    """The whole body of the last rule for this selector that declares prop."""
    found = None
    for match in re.finditer(re.escape(selector) + r"\{", source):
        rule = source[match.end():source.index("}", match.end())]
        if prop + ":" in rule:
            found = rule
    assert found is not None, f"{selector} never declares {prop}"
    return found


def _declared(source, selector, prop):
    """The value that actually applies: later rules win at equal specificity,
    and a selector is written several times over, so the live value is the
    last rule that declares this property -- not the last rule overall (the
    final `.seat-identity` block in v039 only sets a backdrop filter).

    A zero is written `top:0`, not `top:0px`, so the unit is optional.
    """
    pattern = re.compile(r"(?:^|[;{\s])" + prop + r":(-?[\d.]+)(?:px)?")
    found = None
    for match in re.finditer(re.escape(selector) + r"\{", source):
        rule = source[match.end():source.index("}", match.end())]
        hit = pattern.search(rule)
        if hit:
            found = float(hit.group(1))
    assert found is not None, f"{selector} never declares {prop}"
    return found


def test_the_phone_invitation_is_the_size_of_a_phone_avatar():
    sit = _last_rule_text(V040, "body.v014.poker8-v2-sixmax .seat.v040-sit-slot", "--p8-sit-size")
    hero = _last_rule_text(V038, 'body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]', "--p8-hero-avatar-size")
    avatar = _last_rule_text(V038, 'body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .avatar-wrap', "width")
    assert "--p8-sit-size:var(--p8-hero-avatar-size,44px)" in sit
    assert "--p8-sit-top:var(--p8-hero-avatar-top,0px)" in sit
    assert "--p8-hero-avatar-size:48px" in hero and "--p8-hero-avatar-top:9px" in hero
    assert "width:var(--p8-hero-avatar-size)" in avatar
    assert "top:var(--p8-hero-avatar-top)" in avatar


def test_the_phone_label_sits_where_the_name_plate_sits():
    sit = _last_rule_text(V040, "body.v014.poker8-v2-sixmax .seat.v040-sit-slot", "--p8-sit-label-top")
    hero = _last_rule_text(V038, 'body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]', "--p8-hero-label-top")
    plate = _last_rule_text(V038, 'body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-identity', "top")
    # The label used to take the name plate's own offset. A plate may overlap
    # the avatar's bottom edge -- it is a solid box and the name sits inside it
    # -- but the invitation lost its box, so that number put the bare word on
    # the ring. It is worked out from the circle now, and keeps the width.
    assert "--p8-sit-label-top:calc(var(--p8-sit-top) + var(--p8-sit-size) + 6px)" in sit
    assert "--p8-sit-label-w:var(--p8-hero-label-w,90px)" in sit
    assert "--p8-hero-label-top:54px" in hero and "--p8-hero-label-w:108px" in hero
    assert "top:var(--p8-hero-label-top)" in plate
    assert "width:var(--p8-hero-label-w)" in plate


def test_the_desktop_invitation_matches_the_desktop_avatar_and_plate():
    """Desktop sizes the head off --p8-avatar, which has a ceiling of its own,
    so the chair takes the variable rather than a copy of today's number --
    that is what keeps an empty chair the size of a taken one at every scale.
    """
    block = V040[V040.index("body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat.v040-sit-slot{"):]
    block = block[:block.index("}")]
    assert "--p8-sit-size:var(--p8-avatar,88px)" in block
    # Desktop no longer restates the offset at all: the shared rule derives it
    # from --p8-sit-size, which desktop already points at --p8-avatar.
    assert "--p8-sit-label-top" not in block
    avatar = "body.v014.poker8-v2-sixmax.poker8-desktop-v2 .avatar-wrap"
    plate = "body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-identity"
    assert "var(--p8-avatar)" in _last_rule_text(V039, avatar, "width")
    assert "calc(var(--p8-avatar) - 6px)" in _last_rule_text(V039, plate, "top")
    assert _sit_vars("body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat.v040-sit-slot{")["top"] ==         _declared(V039, avatar, "top")
    assert _declared(V039, plate, "width") == 116


def test_a_claimed_seat_stops_offering_itself():
    """Claiming a seat mid-hand always worked -- the queue seats you at the
    boundary -- but the chair carried on reading "Сесть", so the only sign
    anything had happened was in the header."""
    online = (STATIC / "online-table.js").read_text(encoding="utf-8")
    assert 'classList.toggle("p8-seat-reserved", viewerState === "waiting")' in online

    reserved = V040[V040.index(".p8-seat-reserved .seat.v040-sit-slot"):]
    reserved = reserved[:reserved.index("`")]
    # Measured in the browser at the 10px/0.6px the plate is set in:
    # ЗАБРОНИРОВАНО renders 96px wide inside a 90px plate and spills out of
    # it. Whatever the word is, it has to fit the plate it sits on.
    word = re.search(r'content:"([^"]+)"', reserved[reserved.index("strong::after"):]).group(1)
    assert len(word) <= 10, f"{word} is wider than the name plate it replaces"
    assert "border-style:solid!important" in reserved, "the open ring closes once the seat is held"


def test_the_css_escapes_survive_the_template_literal():
    """v040 keeps its stylesheet in a JS template literal, where a CSS
    numeric escape is swallowed as a JS escape before the stylesheet ever
    sees it -- the tick came out as the two characters the mangled escape
    happened to spell, and the label rule was dropped entirely."""
    block = V040[V040.index("const DESKTOP_LAYOUTS"):]
    for escape in (chr(92) + "27", chr(92) + "04"):
        assert escape not in block, "write the character, not a numeric escape"


def test_the_label_keeps_the_plates_place_but_not_its_plate():
    """It wore .seat-identity's whole box for a while -- mint edge, black
    ground -- and an empty chair carrying that read as a seventh occupied seat
    from any distance, which is the one thing it must not look like. It keeps
    where the name goes and how wide the name is; the dashed ring above it is
    what says "a place at the table"."""
    block = V040[V040.index(".v040-sit-slot .seat-empty strong{"):]
    block = block[:block.index("}")]
    assert "border:0!important" in block
    assert "background:none!important" in block
    # Still where a name would be, and as wide.
    assert "top:var(--p8-sit-label-top)!important" in block
    assert "width:var(--p8-sit-label-w)!important" in block


def test_a_held_seat_is_not_read_as_a_seated_one():
    """current_seats carries seats that are only held for the next boundary,
    and seats on their way out. The server counts neither as seated, so
    reading a held one as the viewer's own seat put a "mark ready" button in
    front of somebody with no seat to be ready in -- the server answered
    "take a seat before marking ready"."""
    online = (STATIC / "online-table.js").read_text(encoding="utf-8")
    lookup = online[online.index("function viewerSeatNo(state) {"):]
    lookup = lookup[:lookup.index(chr(10) + "  }")]
    assert 'row.state === "seated"' in lookup

    runtime = Path("online/runtime.py").read_text(encoding="utf-8")
    seating = runtime[runtime.index("async def _current_seating"):]
    seating = seating[:seating.index("@staticmethod")]
    assert '"state": seat["state"]' in seating, "the client cannot filter what it is not told"


def test_marking_ready_needs_the_seat_the_server_counts():
    """The server reports viewer_state "seated" for a seat that is only held
    for the next boundary (app/routers/tables.py), while the ready-up
    endpoint behind the button counts only state == "seated" and refuses the
    rest with "take a seat before marking ready". Gating readyUp on
    viewerSeatNo -- which applies the server's own rule -- means the button
    is offered exactly when the call behind it can succeed. Reported live
    from both the header button and the avatar, which share this path."""
    online = (STATIC / "online-table.js").read_text(encoding="utf-8")
    body = online[online.index("async function readyUp() {"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "viewer_seat_no" in body, "the seat has to come from the server"


def test_the_invitation_ring_cannot_be_squashed_into_an_ellipse():
    """Sized as a percentage of the button, the ring depended on the button
    resolving a height; where it did not, the ring collapsed to the glyph's
    line box and drew as a flat ellipse -- reported from a phone. Its own
    pixels, plus aspect-ratio as a floor, keep it round."""
    block = V040[V040.index(".v040-sit-slot .empty-avatar{"):]
    block = block[:block.index("}")]
    assert "width:var(--p8-sit-size)" in block and "height:var(--p8-sit-size)" in block
    assert "aspect-ratio:1" in block
    assert "height:100%" not in block, "a percentage height is what collapsed"


def test_the_turn_ring_only_runs_while_the_server_keeps_a_clock():
    """action_deadline is set for a human and left null for a bot, which is
    not an omission -- a bot is never timed out. The ring was drawn for any
    actor, so it invented a 30s countdown for bots and restarted it at 30 on
    every bot action as the turn moved round the table. Reported as the
    timer jumping back to 30."""
    table = (STATIC / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    body = table[table.index("function syncTableTurnHud() {"):]
    body = body[:body.index(chr(10) + "  }")]
    # The ring still marks whose turn it is, so an untimed actor keeps it --
    # it just stops carrying a number, and stops restarting a countdown that
    # nothing was counting.
    assert "const timed = !Number.isNaN(deadline);" in body
    assert 'setText(timer.querySelector("b"), "");' in body
    assert "TURN_VISUAL_MS - (Date.now() - turnVisualStartedAt)" not in body


def test_pressing_your_own_held_seat_gives_it_back():
    """The chair was pointer-events:none once held, so the only way out of the
    queue was a button in the header -- not where anyone looks. It is the same
    call the header's "Отменить" makes, and like it, it does not ask twice."""
    reserved = V040[V040.index(".p8-seat-reserved .seat.v040-sit-slot"):]
    reserved = reserved[:reserved.index("`")]
    assert "pointer-events:none" not in reserved

    online = (STATIC / "online-table.js").read_text(encoding="utf-8")
    handler = online[online.index('const button = event.target?.closest?.("[data-add-seat]");'):]
    handler = handler[:handler.index("showBuyInDialog(Number(button.dataset.addSeat));")]
    assert 'if (viewerState === "waiting") {' in handler
    assert "cancelQueue()" in handler
