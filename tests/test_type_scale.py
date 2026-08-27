"""One type scale on the felt, and names that arrive short enough to fit."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")
TABLE = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")

#: Mobile gameplay adds dedicated readable steps for player names, stacks,
#: sizing output and HERO without shrinking them into the desktop scale.
#: Both spellings. `font:800 11px/1 Inter` is a size too, and reading only
#: `font-size:` is how thirteen of them survived four passes.
SIZE = re.compile(r"font(?:-size)?:\s*(?:(?:normal|italic|oblique|small-caps|bold|bolder|lighter|\d{3})\s+)*([0-9.]+)px")

SCALE = {10, 12, 13, 15, 16, 18, 20, 24, 27, 36}


def test_the_table_sets_type_only_on_the_scale():
    sizes = {float(size) for size in SIZE.findall(TABLE)}
    assert sizes <= SCALE, f"off the scale: {sorted(sizes - SCALE)}"
    assert len(sizes) >= 4, "a scale nobody uses is not a scale"


def test_every_override_layer_holds_the_scale():
    """v038 alone was not enough -- 7, 11, 14 and 17 arrived from other layers.

    Twenty-seven files stack their styles onto this table and the last one wins,
    so a scale that only one of them honours is not a scale on the screen.
    """
    strays = {}
    for layer in sorted(Path("static").glob("v0*.js")):
        sizes = {float(size) for size in SIZE.findall(layer.read_text(encoding="utf-8"))}
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
        sizes = {float(size) for size in SIZE.findall(text)}
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


#: Node has no canvas, so the policy takes its measurement as an argument and
#: the test supplies one. These are the real widths of Inter 800 10px, taken
#: from the browser: Cyrillic runs wider than Latin, which is the whole reason
#: counting characters could not do this job.
_WIDTH = "const w = t => [...t].reduce((n, c) => n + (/[А-Яа-яЁё]/.test(c) ? 6.4 : 5.6), 0);"


def _trim(*names):
    source = APP[APP.index("const SEAT_NAME_PX"):]
    source = source[:source.index("function seatDisplayName")]
    body = APP[APP.index("function seatDisplayName"):]
    source += body[:body.index(chr(10) + "}") + 2]
    probe = (_WIDTH + chr(10)
             + "const out = " + json.dumps(list(names)) + ".map(n => seatDisplayName(n, w));"
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


def test_a_single_long_token_is_left_for_the_plate_to_cut():
    """It has no seam, so JS has nothing to decide.

    Slicing the string here was worse than useless: it guessed at where the
    plate would run out using a character count, and the plate already knows
    exactly, with text-overflow. So the name goes through whole and CSS cuts it.
    """
    [trimmed] = _trim("xXxBrokenHeartxXx")
    assert trimmed == "xXxBrokenHeartxXx"


def test_a_name_that_already_fits_is_left_alone():
    assert _trim("Экземпляр", "ShadowLord", "дед внутри", "Guest-397975") == [
        "Экземпляр", "ShadowLord", "дед внутри", "Guest-397975"]


def test_an_empty_name_still_says_something():
    assert _trim("", "   ") == ["Игрок", "Игрок"]

def test_the_lobby_gets_the_same_base():
    """It links network.css and nothing else, so style.css never reaches it."""
    sheet = Path("static/network.css").read_text(encoding="utf-8")
    assert "button,input,select,textarea{font:inherit}" in sheet
    assert "small{font-size:12px}" in sheet
    assert "body{font-size:15px;" in sheet


def test_the_name_box_is_the_plate_on_every_seat():
    """The hero seat kept a max-width of 66px inside an 84px plate -- the same
    cap, in the same units, that started this."""
    for rule in re.findall(r"\.seat-name\{[^}]*\}", TABLE) +                 re.findall(r'\[data-visual-seat="0"\] \.seat-name\{[^}]*\}', TABLE):
        assert "max-width:100%!important" in rule, rule
