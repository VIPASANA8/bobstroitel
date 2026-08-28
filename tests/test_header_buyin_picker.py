"""Пресing "Занять место" in the header used to sit at a hardcoded 40 BB
buy-in with no way to change it. Added a slider dialog (showBuyInDialog)
bounded by the table's own min/max_buy_in_bb, and threaded the chosen
amount through ready()'s new optional buyInBB argument -- every other
caller (a direct seat click, the ready-up avatar shortcut) still gets the
old flat 40 BB default by passing nothing."""

import json
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/online-table.js").read_text(encoding="utf-8")


def test_ready_still_defaults_to_forty_bb_for_every_other_caller():
    assert "async function ready(seatNo = null, buyInBB = null) {" in SOURCE
    assert "units(table?.big_blind_units) * 40" in SOURCE


def _extract(marker, end_marker):
    start = SOURCE.index(marker)
    end = SOURCE.index(end_marker, start) + len(end_marker)
    return SOURCE[start:end]


def _run_buyin_units(buy_in_bb, big_blind_units):
    block = _extract(
        "const buyInUnits = buyInBB != null",
        "* 40;",
    )
    harness = """
    const buyInBB = %s;
    const table = { big_blind_units: %s };
    function units(value) { return Math.round(Number(value || 0)); }
    %s
    console.log(JSON.stringify(buyInUnits));
    """ % (json.dumps(buy_in_bb), json.dumps(big_blind_units), block)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_chosen_bb_amount_converts_to_units_off_the_tables_own_blind():
    assert _run_buyin_units(60, 100) == 6000


def test_no_chosen_amount_still_falls_back_to_the_old_flat_forty_bb():
    assert _run_buyin_units(None, 100) == 4000


def _run_slider_bounds(min_bb, max_bb):
    block = _extract(
        "function showBuyInDialog(seatNo = null) {",
        "\n  }\n",
    )
    harness = """
    const table = { min_buy_in_bb: %s, max_buy_in_bb: %s };
    const calls = [];
    function requestAnimationFrame(fn) { fn(); }
    function ensureBuyInDialog() {
      const store = {};
      return {
        querySelector(sel) {
          return {
            set min(v) { store.min = v; }, get min() { return store.min; },
            set max(v) { store.max = v; }, get max() { return store.max; },
            set step(v) { store.step = v; }, get step() { return store.step; },
            set value(v) { store.value = v; }, get value() { return store.value; },
            set textContent(v) { calls.push([sel, v]); },
            focus() {},
          };
        },
        showModal() {},
      };
    }
    %s
    showBuyInDialog();
    console.log(JSON.stringify(calls));
    """ % (json.dumps(min_bb), json.dumps(max_bb), block)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return dict(json.loads(result.stdout))


def test_the_slider_default_clamps_up_when_the_tables_own_minimum_beats_forty():
    # A high-stakes table whose own floor sits above the old flat default --
    # the slider must not open positioned outside its own min/max.
    calls = _run_slider_bounds(60, 150)
    assert calls["[data-min]"] == "60"
    assert calls["[data-max]"] == "150"
    assert calls["[data-value]"] == "60"


def test_the_slider_defaults_to_forty_when_that_falls_inside_the_tables_range():
    calls = _run_slider_bounds(20, 100)
    assert calls["[data-value]"] == "40"
