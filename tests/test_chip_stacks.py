"""How many chips are drawn, and how tall they stand."""

import re
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")
POT_LAYER = Path("static/v020-fixes.js").read_text(encoding="utf-8")


def test_a_wager_is_one_stack_whatever_it_is_worth():
    """It sits inches from the player it belongs to, beside a label that
    already says the number; spreading it sideways only made it wider."""
    body = APP[APP.index("function visualStackCount"):]
    body = body[:body.index("\n}")]
    assert "if (compact) return 1;" in body


def test_the_height_of_a_stack_says_how_much_is_in_it():
    """It used to be 4 + ((col * 2 + round(n)) % 5): a pot of 20 and a pot of
    25 drew the same, while 20 and 21 drew nothing alike."""
    body = APP[APP.index("function chipLayers"):]
    body = body[:body.index("\n}")]
    assert "Math.log10" in body
    assert "% 5" not in APP[APP.index("function chipStackHtml"):APP.index("function renderPotChips")]


def test_only_one_place_draws_chips():
    """Three implementations were stacked on top of each other -- app.js, v020
    and v031 -- and only the last one loaded drew anything. A fix in either of
    the others was invisible, which cost two rounds of chasing before the chips
    changed at all. One owner now, and the layers may not take it back."""
    for name in ("chipStackHtml", "renderPotChips", "potClusterOffsets"):
        assert f"function {name}(" in APP, f"{name} belongs in app.js"

    layers = sorted(Path("static").glob("v0*.js"))
    assert layers, "the layer chain is still there"
    for layer in layers:
        source = layer.read_text(encoding="utf-8")
        for name in ("chipStackHtml", "renderPotChips"):
            assert re.search(rf"^\s*{name} = ", source, re.M) is None,                 f"{layer.name} overrides {name} again"


def test_layers_never_run_away_or_collapse():
    """Whatever the amount, a column stays between two chips and six."""
    body = APP[APP.index("function chipLayers"):]
    body = body[:body.index("\n}")]
    assert "Math.max(2, Math.min(6," in body, "the pot"
    assert "Math.max(2, Math.min(7," in body, "and the single wager stack"


def test_a_stack_whose_base_sits_higher_is_drawn_behind():
    """Depth comes from the base, never a hand-written number. The old table
    had it inverted: the frontmost z sat on the stack at the top of the
    cluster, so the far chips were drawn over the near ones."""
    import json
    import subprocess
    import tempfile

    source = APP[APP.index("function potClusterOffsets("):]
    source = source[:source.index(chr(10) + "}") + 2]
    probe = (
        "const out = {};" + chr(10)
        + "for (const n of [1,2,3,4,5,6,7]) out[n] = potClusterOffsets(n);" + chr(10)
        + "console.log(JSON.stringify(out));" + chr(10)
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(source + chr(10) + probe)
        path = handle.name

    result = subprocess.run(["node", path], capture_output=True, text=True, check=True)
    for count, points in json.loads(result.stdout).items():
        ordered = sorted(points, key=lambda point: point["y"])
        depths = [point["z"] for point in ordered]
        assert depths == sorted(depths), f"{count} stacks layered out of order: {ordered}"
        layers = {point["z"] for point in points}
        assert len(layers) == len(points), f"{count} stacks share a layer: {points}"

def test_the_countdown_sits_above_the_label_it_belongs_to():
    """They were positioned independently -- 55% - 66px against 36% or 47% --
    and overlapped whenever the layout moved the label down."""
    layer = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    assert "top:var(--p8-prompt-y, 36%)" in layer, "the label reads the variable"
    assert "top:calc(var(--p8-prompt-y, 36%) - 64px)" in layer, "and the ring sits above it"
    assert "top:calc(55% - 66px)" not in layer
