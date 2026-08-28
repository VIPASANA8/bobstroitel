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
    assert 'content:"ЗАБРОНИРОВАНО"' in reserved
    assert "border-style:solid!important" in reserved, "the open ring closes once the seat is held"


def test_the_css_escapes_survive_the_template_literal():
    """v040 keeps its stylesheet in a JS template literal, where a CSS
    numeric escape is swallowed as a JS escape before the stylesheet ever
    sees it -- the tick came out as the two characters the mangled escape
    happened to spell, and the label rule was dropped entirely."""
    block = V040[V040.index("const style = document.createElement"):]
    for escape in (chr(92) + "27", chr(92) + "04"):
        assert escape not in block, "write the character, not a numeric escape"
