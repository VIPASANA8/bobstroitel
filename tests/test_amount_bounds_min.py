"""amountBounds() used to hardcode min=1 for an opening bet (human_to_call
== 0), so the slider let you submit below the real minimum (the big blind)
and the engine rejected it -- while a raise (human_to_call > 0) always used
the correct human_min_raise_to. Bug only showed up in the opening-bet case,
which matches the user report ("появляется не всегда")."""

import json
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")


def _extract_block():
    start = APP.index("function amountBounds() {")
    end = APP.index("\n}\n", start) + len("\n}\n")
    return APP[start:end]


def test_the_block_is_still_there_to_extract():
    block = _extract_block()
    assert "human_min_raise_to" in block
    assert "min_raise_size" in block


def _run(game, amount_input=None):
    block = _extract_block()
    harness = """
    const game = %s;
    function localViewerPlayer() { return game.player; }
    function isLocalHumanTurn() { return game.humanTurn; }
    function $(id) { return id === "amount" ? { value: %s } : null; }
    %s
    console.log(JSON.stringify(amountBounds()));
    """ % (json.dumps(game), json.dumps(amount_input), block)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_an_opening_bet_floors_at_the_real_minimum_not_one():
    game = {
        "humanTurn": True,
        "human_to_call": 0,
        "current_bet": 0,
        "min_raise_size": 2,
        "human_min_raise_to": 2,
        "player": {"street_invested": 0, "stack": 100},
    }
    bounds = _run(game)
    assert bounds["min"] == 2


def test_a_raise_still_floors_at_human_min_raise_to():
    game = {
        "humanTurn": True,
        "human_to_call": 4,
        "current_bet": 4,
        "min_raise_size": 4,
        "human_min_raise_to": 8,
        "player": {"street_invested": 4, "stack": 100},
    }
    bounds = _run(game)
    assert bounds["min"] == 8


def test_the_bb_option_to_raise_over_limpers_also_floors_correctly():
    """current_bet already sits at the big blind, to_call is 0 (you can
    check), but a raise from here must still start at current_bet +
    min_raise_size -- not 1."""
    game = {
        "humanTurn": True,
        "human_to_call": 0,
        "current_bet": 2,
        "min_raise_size": 2,
        "human_min_raise_to": 4,
        "player": {"street_invested": 2, "stack": 100},
    }
    bounds = _run(game)
    assert bounds["min"] == 4
