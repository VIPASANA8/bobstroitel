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
    sit = _sit_vars("body.v014.poker8-v2-sixmax .seat.v040-sit-slot{")
    avatar = "body.v014.poker8-v2-sixmax .avatar-wrap"
    assert sit["size"] == _declared(V038, avatar, "width")
    assert sit["top"] == _declared(V038, avatar, "top")


def test_the_phone_label_sits_where_the_name_plate_sits():
    sit = _sit_vars("body.v014.poker8-v2-sixmax .seat.v040-sit-slot{")
    plate = "body.v014.poker8-v2-sixmax .seat-identity"
    assert sit["label-top"] == _declared(V038, plate, "top")
    assert sit["label-w"] == _declared(V038, plate, "width")


def test_the_desktop_invitation_matches_the_desktop_avatar_and_plate():
    sit = _sit_vars("body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat.v040-sit-slot{")
    avatar = "body.v014.poker8-v2-sixmax.poker8-desktop-v2 .avatar-wrap"
    plate = "body.v014.poker8-v2-sixmax.poker8-desktop-v2 .seat-identity"
    assert sit["size"] == _declared(V039, avatar, "width")
    assert sit["top"] == _declared(V039, avatar, "top")
    assert sit["label-top"] == _declared(V039, plate, "top")
    assert sit["label-w"] == _declared(V039, plate, "width")


def test_a_claimed_seat_stops_offering_itself():
    """Claiming a seat mid-hand always worked -- the queue seats you at the
    boundary -- but the chair carried on reading "Сесть", so the only sign
    anything had happened was in the header."""
    online = (STATIC / "online-table.js").read_text(encoding="utf-8")
    assert 'classList.toggle("p8-seat-reserved", viewerState === "waiting")' in online

    reserved = V040[V040.index(".p8-seat-reserved .seat.v040-sit-slot"):]
    reserved = reserved[:reserved.index("`")]
    assert "pointer-events:none!important" in reserved, "a held seat must not take another click"
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
    block = V040[V040.index("const style = document.createElement"):]
    for escape in (chr(92) + "27", chr(92) + "04"):
        assert escape not in block, "write the character, not a numeric escape"


def test_the_label_sits_on_a_plate_like_a_name_does():
    """Bare text under the circle was the half of this that still did not
    look like a seat. It takes .seat-identity's own box: same padding,
    radius and ground, with the empty seat's mint edge in place of the
    accent hue a taken seat carries."""
    block = V040[V040.index(".v040-sit-slot .seat-empty strong{"):]
    block = block[:block.index("}")]
    plate = _last_rule_text(V038, "body.v014.poker8-v2-sixmax .seat-identity", "border-radius")
    for prop in ("padding", "border-radius", "background"):
        assert prop in block, f"the label has no {prop}, so it is not a plate"
    # Read off the plate rather than repeated, so a restyled name plate takes
    # the label with it instead of leaving the two subtly different.
    for prop in ("border-radius", "padding"):
        value = re.search(prop + r":([^;!]+)", plate).group(1).strip()
        assert prop + ":" + value in block, f"label {prop} is {block!r}, plate wants {value}"


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
    assert "viewerSeatNo(latestState) == null" in body


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
