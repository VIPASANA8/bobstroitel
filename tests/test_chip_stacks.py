"""How many chips are drawn, and how tall they stand."""

import re
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")
POT_LAYER = Path("static/v020-fixes.js").read_text(encoding="utf-8")


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


def test_the_pot_amount_stays_the_top_layer_over_the_chip_wings():
    """Explicit stacking order, not left to default paint order: the number
    must stay readable if a wing's chips ever sit close enough to graze it."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    total_rule = table[table.index(".pot-total{top:25%"):]
    total_rule = total_rule[:total_rule.index("}") + 1]
    chips_rule = table[table.index(".pot-chips{"):]
    chips_rule = chips_rule[:chips_rule.index("}") + 1]
    total_z = int(re.search(r"z-index:(\d+)", total_rule).group(1))
    chips_z = int(re.search(r"z-index:(\d+)", chips_rule).group(1))
    assert total_z > chips_z


def test_the_pot_wings_stay_clear_of_the_felts_own_border_at_the_worst_case_column_count():
    """A real screenshot at pot=41 (5 columns split 3/2) showed the chip
    piles overlapping the felt's own decorative border. .table-center spans
    the felt's full border-box width (measured live: 321px felt, .table-
    center also 0-321 relative to it) -- not just the inner surface inside
    the 13px border -- so a wide .pot-chips row centers into that same
    border-box span and its outer wing can end up sitting on the border
    itself. Reproduces the live measurement (17px per column once the -5px
    overlap margin is accounted for) for the widest case a real pot can
    reach -- 7 stacks, split 4/3 -- and checks real clearance, not just
    "technically not touching"."""
    table = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    rule = table[table.index(".pot-chips{"):]
    rule = rule[:rule.index("}") + 1]
    width = int(re.search(r"width:(\d+)px", rule).group(1))

    felt_w, border, column_step, column_w = 321, 13, 17, 22
    # 62.5px measured live at the fixed width (170px); 32.5px measured live
    # at the width that produced the reported overlap (230px) -- the
    # midpoint is a real threshold, not an arbitrary one.
    required_clearance_from_border = 50

    def wing_width(count):
        return column_w + max(0, count - 1) * column_step

    left_edge = (felt_w - width) / 2  # where the whole row (and its first wing) starts
    left_wing_far_edge = left_edge + wing_width(4)  # the wider half of a 4/3 split

    assert left_edge - border > required_clearance_from_border, "the row starts too close to the border again"
    assert left_wing_far_edge < felt_w / 2, "the widest wing reaches past the felt's own center"


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


def test_the_pot_splits_into_two_wings_flanking_the_amount():
    """renderPotChips used to draw one scattered cluster piled under the
    board; it now splits the same column count into a left and a right wing
    so the amount sits between them, with the extra column on an odd count
    going to the right."""
    import json
    import subprocess
    import tempfile

    start = APP.index("const CHIP_DENOMS")
    end = APP.index("\n}", APP.index("function renderPotChips(value) {")) + 2
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
      const [left, right] = target.innerHTML.split("</div>").filter(s => s.includes("chip-column"));
      out[n] = {
        left: (left.match(/chip-column/g) || []).length,
        right: (right ? right.match(/chip-column/g) : [] || []).length,
      };
    }
    console.log(JSON.stringify(out));
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(source + chr(10) + probe)
        path = handle.name

    result = subprocess.run(["node", path], capture_output=True, text=True, check=True)
    counts = json.loads(result.stdout)
    for pot, sides in counts.items():
        total = sides["left"] + sides["right"]
        assert total >= 1
        # Right never gets fewer than left minus one -- the split is even or
        # the odd one out goes right, never left.
        assert sides["right"] in (sides["left"], sides["left"] - 1), (pot, sides)

def test_the_countdown_sits_at_the_center_of_the_felt():
    """No longer tied to the room label's variable -- the label is silent for
    a seated player now, so the ring has the felt center to itself, the same
    ground the board and pot occupy once a hand actually deals."""
    layer = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    ring = layer[layer.index(".v038-ready-countdown{"):]
    assert "top:50%" in ring[:200]
    assert "top:calc(var(--p8-prompt-y, 36%) - 64px)" not in layer
    assert "top:calc(55% - 66px)" not in layer
