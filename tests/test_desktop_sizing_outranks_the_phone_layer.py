"""Desktop rendered the phone's sizes: a 49px avatar and 45x63 board cards
on a 928px felt, where v039 had asked for 88px and larger cards all along.

Nothing was missing -- v039's desktop rules were simply losing the cascade.
Both layers write `!important`, both selectors carry the same specificity
(`body.v014.poker8-desktop-v2 X` vs v038's `body.v014.poker8-v2-sixmax X`,
each 0,0,3,1), and v038 is appended *later*: it is loaded off v037, while
v039 is a plain <script> in index.html. Later wins a specificity tie, so
every desktop size v039 set was silently discarded.

The fix is a specificity bump, not new values: adding `.poker8-v2-sixmax`
to v039's selectors makes them 0,0,4,1 and independent of load order. This
guards the invariant rather than the pixel values, because the failure mode
is invisible -- the rule is right there in the file, it just never applies.
"""

import re
from pathlib import Path

V038 = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
V039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")

#: Elements v038 sizes for every width, so any desktop rule for them is in a
#: tie v038 would otherwise win.
CONTESTED = [".avatar-wrap", ".player-avatar", ".board-cards .card", ".seat-identity"]


def test_v038_really_does_contest_these():
    """If v038 ever stops sizing them the guard below is moot -- and if it
    still does, the tie is real."""
    for target in CONTESTED:
        assert f"body.v014.poker8-v2-sixmax {target}{{" in V038, target


def test_every_desktop_rule_for_them_outranks_the_phone_layer():
    for target in CONTESTED:
        pattern = re.compile(r"(body\.v014[\w.\-]*)\s" + re.escape(target) + r"\{")
        found = pattern.findall(V039)
        assert found, f"v039 no longer styles {target}"
        for prefix in found:
            assert "poker8-v2-sixmax" in prefix and "poker8-desktop-v2" in prefix, (
                f"{target}: {prefix} ties with v038 and loses on load order"
            )


def test_the_avatar_is_desktop_sized_not_phone_sized():
    """49px was chosen for a 375px screen; the felt here is ~930px."""
    match = re.search(
        r"--p8-avatar:min\((\d+)px,",
        V039,
    )
    assert match, "desktop avatar rule missing"
    assert int(match.group(1)) >= 80


def test_the_board_cards_are_desktop_sized():
    width = int(re.search(r"--p8-card-w:(\d+)px", V039).group(1))
    height = int(re.search(r"--p8-card-h:(\d+)px", V039).group(1))
    assert "width:calc(var(--p8-card-w) * var(--p8-card-factor,1))!important" in V039
    # v038's phone card is 45x63; anything at or under that is the bug.
    assert width > 45 and height > 63
