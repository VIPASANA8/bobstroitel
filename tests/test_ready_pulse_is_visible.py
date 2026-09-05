"""The "tap your avatar" pulse has to actually paint.

It animated `border-color` and `box-shadow` on `.player-avatar`, and
`.v011 .player-avatar` declares both of those `!important`. An `!important`
declaration outranks an animation, and `!important` inside `@keyframes` is
ignored by the spec -- so the animation ran for its full 1.7s, every cycle,
and changed nothing on screen. Heads-up, with no other movement on the felt,
that read as no animation at all.
"""

import re
from pathlib import Path


V038 = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
#: Every layer that gets a say about the hero avatar's own frame.
LAYERS = [
    Path(name).read_text(encoding="utf-8")
    for name in (
        "static/style.css", "static/mobile.css",
        "static/v038-poker8-v2-cinematic-table.js",
        "static/v039-poker8-v2-desktop-parity.js",
        "static/v040-poker8-v2-dynamic-seats.js",
    )
]

KEYFRAMES = re.search(r"@keyframes v038ReadyPulse\{(.*?)\}\}", V038, re.S).group(1)
RULE = V038[V038.index(".avatar-wrap:not(.v038-viewer-ready) .player-avatar{"):][:400]


def _stamped_important(prop: str) -> bool:
    """Whether any layer declares `prop` on .player-avatar as !important.

    The shorthand counts: `.v011 .player-avatar` stamps `border`, not
    `border-color`, and that is what beat the keyframes -- checking only the
    longhand would have let the original bug straight through.
    """
    return any(
        re.compile(
            rf"\.player-avatar[^{{]*\{{[^}}]*\b{re.escape(name)}\s*:[^;}}]*!important", re.S
        ).search(layer)
        for name in {prop, prop.split("-")[0]}
        for layer in LAYERS
    )


def test_the_pulse_does_not_animate_a_property_a_layer_stamps_important():
    for prop in re.findall(r"([a-z-]+)\s*:", KEYFRAMES):
        assert not _stamped_important(prop), f"v038ReadyPulse animates {prop}, which some layer stamps !important"


def test_the_pulse_still_animates_something():
    """Deleting the keyframes' contents would pass the test above."""
    assert "outline-color" in KEYFRAMES
    assert "border-color" not in KEYFRAMES and "box-shadow" not in KEYFRAMES


def test_the_base_outline_does_not_outrank_its_own_keyframes():
    """The declaration that gives the animation something to interpolate must
    stay un-important for the same reason the border broke it."""
    assert "outline:2px solid transparent;" in RULE
    assert "outline:2px solid transparent!important" not in RULE
    assert "outline-offset:2px;" in RULE


def test_motion_can_be_turned_off_without_losing_the_affordance():
    """Nothing else says where to tap, so the ring stays lit."""
    reduced = V038[V038.index("@media(prefers-reduced-motion:reduce){", V038.index("v038ReadyPulse")):][:600]
    assert "animation:none" in reduced
    assert "outline-color" in reduced
