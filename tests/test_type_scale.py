"""One type scale on the felt, and names that arrive short enough to fit."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")
TABLE = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")

#: Five steps. Measured on the live table, the felt carried sixteen sizes --
#: 6 through 29 -- which is not a hierarchy, it is the absence of a decision.
#: The sixth step is for page headings outside the felt -- the lobby and
#: profile share these stylesheets.
SCALE = {10, 12, 15, 20, 27, 36}


def test_the_table_sets_type_only_on_the_scale():
    sizes = {float(size) for size in re.findall(r"font-size:\s*([0-9.]+)px", TABLE)}
    assert sizes <= SCALE, f"off the scale: {sorted(sizes - SCALE)}"
    assert len(sizes) >= 4, "a scale nobody uses is not a scale"


def test_every_override_layer_holds_the_scale():
    """v038 alone was not enough -- 7, 11, 14 and 17 arrived from other layers.

    Twenty-seven files stack their styles onto this table and the last one wins,
    so a scale that only one of them honours is not a scale on the screen.
    """
    strays = {}
    for layer in sorted(Path("static").glob("v0*.js")):
        sizes = {float(size) for size in re.findall(r"font-size:\s*([0-9.]+)px", layer.read_text(encoding="utf-8"))}
        if sizes - SCALE:
            strays[layer.name] = sorted(sizes - SCALE)
    assert not strays, f"off the scale: {strays}"


def test_the_stylesheets_under_the_layers_hold_it_too():
    """The layers were on the scale and the felt still showed nine sizes.

    style.css and its three siblings paint first and are never fully covered,
    so 7, 11, 14, 16 and 17 came through from underneath. Card faces are the
    one exception and they need none: their rank and suit are sized in `em`
    against the card, so they follow whatever the card is, not a text scale.
    """
    strays = {}
    for sheet in ("style.css", "mobile.css", "component-ui.css", "network.css",
                  "online-table.js", "lobby.js"):
        text = (Path("static") / sheet).read_text(encoding="utf-8")
        sizes = {float(size) for size in re.findall(r"font-size:\s*([0-9.]+)px", text)}
        if sizes - SCALE:
            strays[sheet] = sorted(sizes - SCALE)
    assert not strays, f"off the scale: {strays}"


def test_the_inherited_size_is_a_decision():
    """The most common size on the page was the browser default nobody chose.

    `button, input { font: inherit }` sends every unstyled control to the body,
    and the body set no size at all -- so 16px, the one step off the scale,
    was reaching more elements than any rule in any of the twenty-seven layers.
    """
    sheet = Path("static/style.css").read_text(encoding="utf-8")
    rule = sheet[sheet.index(chr(10) + "body {"):]
    size = re.search(r"font-size:\s*([0-9.]+)px", rule[:rule.index("}")])
    assert size and float(size.group(1)) in SCALE


def test_nothing_is_left_at_a_browser_default():
    """Three sizes on the page came from the UA sheet, not from this project.

    `font: inherit` covered button and input but not select or textarea, and
    <small> keeps its 0.83em unless told otherwise -- so a form control and a
    caption sat at 13.33px and 12.5px while everything around them was on the
    scale.
    """
    sheet = Path("static/style.css").read_text(encoding="utf-8")
    assert "button, input, select, textarea { font: inherit; }" in sheet
    assert 'small { font-size: 12px; }' in sheet


def test_the_stack_reads_louder_than_the_name():
    """The number you scan sits a step above the name beside it."""
    name = re.search(r"\.seat-name\{[^}]*font-size:(\d+)px", TABLE)
    stack = re.search(r"\.seat-stack\{[^}]*font-size:(\d+)px", TABLE)
    assert name and stack
    assert int(stack.group(1)) > int(name.group(1))


def test_the_name_gets_the_whole_plate():
    """It was capped at 68px inside a 92px plate -- cut in a box with room."""
    rule = TABLE[TABLE.index(".seat-name{"):]
    assert "max-width:100%!important" in rule[:rule.index("}")]


def _trim(*names):
    source = APP[APP.index("const SEAT_NAME_MAX"):]
    source = source[:source.index(chr(10) + "}") + 2]
    probe = ("const out = " + json.dumps(list(names)) + ".map(seatDisplayName);"
             + chr(10) + "console.log(JSON.stringify(out));" + chr(10))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(source + chr(10) + probe)
        path = handle.name
    # encoding is not optional here: without it text=True decodes with the
    # Windows console codepage and every Cyrillic name comes back mangled.
    result = subprocess.run(["node", path], capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_name_of_several_words_shows_its_first_one_whole():
    """Cutting mid-word gave "Яромир Пятниц…" and "Институт Неловк…"."""
    assert _trim("Яромир Пятницкий", "Институт Неловких Решений", "Гоша Рубчинский") == [
        "Яромир", "Институт", "Гоша"]


def test_a_single_long_token_has_no_seam_so_it_ends_in_an_ellipsis():
    [trimmed] = _trim("xXxBrokenHeartxXx")
    assert trimmed.endswith("…") and len(trimmed) <= 14


def test_a_name_that_already_fits_is_left_alone():
    assert _trim("Экземпляр", "ShadowLord", "дед внутри", "Guest-397975") == [
        "Экземпляр", "ShadowLord", "дед внутри", "Guest-397975"]


def test_an_empty_name_still_says_something():
    assert _trim("", "   ") == ["Игрок", "Игрок"]
