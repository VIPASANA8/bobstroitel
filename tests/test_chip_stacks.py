"""How many chips are drawn, and how tall they stand."""

import re
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")


def test_pot_chips_render_at_full_opacity_without_relying_on_a_transition():
    """.pot-chips's base rule (style.css) fades opacity .15 -> 1 over .18s
    when .has-chips is toggled on, via a CSS transition. renderPotChips can
    repaint several times a second while a decision is on the clock, and
    each repaint that touches the element restarts that transition -- caught
    live via getAnimations(): the transition sat at playState "running",
    localTime 0, progress 0, indefinitely. The pot chips never actually
    reached visible opacity; a screenshot from a real table showed the two
    wing slots empty. v038 now sets opacity directly instead of leaning on
    the transition ever finishing."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    rule = table[table.index(".pot-chips{"):]
    rule = rule[:rule.index("}") + 1]
    assert "opacity:1!important" in rule
    assert "transition:none!important" in rule


def test_three_explicit_layers_plaque_below_chips_below_the_amount():
    """Plaque < chips < number, not just "the pot wins." .pot-total (the
    plaque, including its background) must NOT carry its own z-index -- any
    explicit value, even a low one, would make it a stacking context and cap
    every child (including the number) at that level regardless of the
    child's own z-index. Only .pot-total strong gets one, and it needs
    position:relative to take effect at all."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    total_rule = table[table.index(".pot-total{top:25%"):]
    total_rule = total_rule[:total_rule.index("}") + 1]
    assert "z-index" not in total_rule, "the plaque must stay at auto to not trap the number below it"

    chips_rule = table[table.index(".pot-chips{"):]
    chips_rule = chips_rule[:chips_rule.index("}") + 1]
    chips_z = int(re.search(r"z-index:(\d+)", chips_rule).group(1))

    number_rule = table[table.index(".pot-total strong{"):]
    number_rule = number_rule[:number_rule.index("}") + 1]
    assert "position:relative!important" in number_rule
    number_z = int(re.search(r"z-index:(\d+)", number_rule).group(1))

    assert number_z > chips_z


def test_the_pot_cluster_stays_clear_of_the_felts_own_border_at_its_widest():
    """A real screenshot at pot=41 showed the chip piles overlapping the
    felt's own decorative border. .table-center spans the felt's full
    border-box width (measured live: 321px felt, .table-center also 0-321
    relative to it) -- not just the inner surface inside the 13px border --
    so a .pot-chips row centred in that span can put its outer edge on the
    border itself.

    The row is one shrink-to-fit cluster now rather than two halves held
    apart by a fixed width, so the widest case is all 7 columns side by side
    (17px per column once the -5px overlap margin is accounted for) instead
    of a 4/3 split across 170px. Narrower than what it replaced, but the
    clearance is checked rather than assumed."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    rule = table[table.index(".pot-chips{"):]
    rule = rule[:rule.index("}") + 1]
    # Shrink-to-fit is the whole point: a fixed width would re-centre the
    # cluster inside empty air, and an inherited min-width would restore the
    # span this test exists to keep off the border.
    assert "width:auto!important" in rule
    assert "min-width:0!important" in rule
    assert "justify-content:center!important" in rule

    felt_w, border, column_step, column_w = 321, 13, 17, 22
    # 62.5px measured live at the old fixed width (170px); 32.5px measured
    # live at the width that produced the reported overlap (230px) -- the
    # midpoint is a real threshold, not an arbitrary one.
    required_clearance_from_border = 50

    widest = column_w + 6 * column_step  # 7 columns, the cap in renderPotChips
    left_edge = (felt_w - widest) / 2
    assert left_edge - border > required_clearance_from_border, "the cluster reaches the border again"


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
    for name in ("chipStackHtml", "renderPotChips", "potWingHtml"):
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


def test_every_calculated_column_lands_in_one_cluster():
    """renderPotChips used to split its columns across a left and a right
    wing so the amount sat between them. On a small pot that produced two
    lone stacks marooned either side of the plate, reading as two pots.
    Every column goes into a single cluster now.

    Checked against each column's own `--cols`, which potWingHtml writes as
    the size of the cluster it belongs to: if the columns were split again,
    that number would come out below the total on screen."""
    import json
    import re as _re
    import subprocess
    import tempfile

    start = APP.index("const CHIP_DENOMS")
    end = APP.index(chr(10) + "}", APP.index("function renderPotChips(value) {")) + 2
    source = APP[start:end]
    probe = """
    let game = null;
    function $() { return { innerHTML: "", classList: { toggle() {} } }; }
    const out = {};
    for (const n of [1, 3, 8, 30, 90, 400]) {
      const target = { innerHTML: "", classList: { toggle() {} } };
      const originalDollar = $;
      $ = () => target;
      renderPotChips(n);
      $ = originalDollar;
      out[n] = target.innerHTML;
    }
    console.log(JSON.stringify(out));
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(source + chr(10) + probe)
        path = handle.name

    try:
        result = subprocess.run(["node", path], capture_output=True, text=True, check=True)
    finally:
        Path(path).unlink(missing_ok=True)

    for pot, html in json.loads(result.stdout).items():
        clusters = html.count("chip-cluster")
        columns = html.count("chip-column")
        assert clusters == 1, f"pot {pot} drew {clusters} clusters"
        assert columns >= 1, pot
        declared = {int(value) for value in _re.findall(r"--cols:(\d+)", html)}
        assert declared == {columns}, f"pot {pot}: {columns} columns on screen, cluster says {declared}"


def test_the_countdown_sits_at_the_center_of_the_felt():
    """No longer tied to the room label's variable -- the label is silent for
    a seated player now, so the ring has the felt center to itself, the same
    ground the board and pot occupy once a hand actually deals."""
    layer = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    ring = layer[layer.index(".v038-ready-countdown{"):]
    assert "top:50%" in ring[:200]
    assert "top:calc(var(--p8-prompt-y, 36%) - 64px)" not in layer
    assert "top:calc(55% - 66px)" not in layer
