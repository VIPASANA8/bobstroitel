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


def test_the_pot_uses_the_same_maths_as_everything_else():
    """Three layers drew the pot three different ways. v031 is the one that
    wins -- it overrides chipStackHtml and renderPotChips last -- so a fix
    anywhere else was invisible. All of them agree now."""
    body = POT_LAYER[POT_LAYER.index("function growingPotStackHtml"):]
    body = body[:body.index(chr(10) + "  }")]
    assert "visualStackCount(n, false)" in body
    assert "chipLayers(n, col, false)" in body
    assert "visibleTotal" not in POT_LAYER, "the old linear scale is gone"

    winner = Path("static/v031-pot-cluster-mobile-fix.js").read_text(encoding="utf-8")
    assert "chipLayers(n, col, false)" in winner
    assert "Math.min(9," not in winner, "nine-chip columns are gone from the one that renders"
    assert "Math.max(1, visualStackCount" in winner, "a small pot may be one stack"


def test_layers_never_run_away_or_collapse():
    """Whatever the amount, a column stays between two chips and six."""
    body = APP[APP.index("function chipLayers"):]
    body = body[:body.index("\n}")]
    assert "Math.max(2, Math.min(6," in body, "the pot"
    assert "Math.max(2, Math.min(7," in body, "and the single wager stack"
