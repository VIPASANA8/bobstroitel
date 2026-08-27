"""The raise/all-in amount stopped getting overwritten mid-decision."""

import json
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")


def _extract_block():
    start = APP.index("if (localPlayerAlive()) {\n  // Was: reseed")
    end = APP.index("\n}\n", start) + len("\n}\n")
    return APP[start:end]


def test_the_block_is_still_there_to_extract():
    """Anchors the slice below -- if this text moves, the extraction (and the
    behavioural test after it) needs to move with it, not silently test
    nothing."""
    block = _extract_block()
    assert "amountSeededForTurn" in block
    assert "syncAmountControls(game.human_min_raise_to)" in block


def _run(renders):
    """Feed a sequence of {hand_id, street, acting_player, history, human_min_raise_to,
    humanTurn} states through the real seeding block, one render each, and
    report what syncAmountControls was called with on each render: the seeded
    minimum, "kept" (no argument -- the field was left alone), or null."""
    block = _extract_block()
    harness = """
    let amountSeededForTurn = null;
    let game = null;
    let calls = [];
    function syncAmountControls(preferred) {
      calls.push(preferred === undefined ? "kept" : preferred);
    }
    function turnToken() {
      return [game.hand_id, game.street, game.acting_player, game.history.length].join(":");
    }
    function isLocalHumanTurn() { return game.humanTurn; }
    function localPlayerAlive() { return true; }

    const renders = %s;
    for (const r of renders) {
      game = r;
      %s
    }
    console.log(JSON.stringify(calls));
    """ % (json.dumps(renders), block)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_repeated_render_of_the_same_decision_does_not_reseed():
    """This is the bug: renderGame() fires on every snapshot -- several a
    second while a decision is on the clock -- and it used to call
    syncAmountControls(human_min_raise_to) every single time, silently
    replacing whatever the player had just set with the slider or a preset.
    Three renders of the identical decision must seed once and then leave the
    field alone."""
    same_spot = {"hand_id": "h1", "street": "preflop", "acting_player": "p1",
                 "history": [], "human_min_raise_to": 8, "humanTurn": True}
    calls = _run([same_spot, same_spot, same_spot])
    assert calls == [8, "kept", "kept"]


def test_a_new_decision_reseeds_to_the_new_minimum():
    turn1 = {"hand_id": "h1", "street": "preflop", "acting_player": "p1",
             "history": [], "human_min_raise_to": 8, "humanTurn": True}
    turn2 = {"hand_id": "h1", "street": "flop", "acting_player": "p1",
             "history": [1], "human_min_raise_to": 15, "humanTurn": True}
    calls = _run([turn1, turn1, turn2, turn2])
    assert calls == [8, "kept", 15, "kept"]


def test_leaving_and_returning_to_your_turn_reseeds():
    """Passing the action to a bot and back is a new decision even if the
    street and history length happen to match again."""
    yours = {"hand_id": "h1", "street": "flop", "acting_player": "p1",
             "history": [1], "human_min_raise_to": 15, "humanTurn": True}
    bots_turn = {"hand_id": "h1", "street": "flop", "acting_player": "p2",
                 "history": [1], "human_min_raise_to": 0, "humanTurn": False}
    calls = _run([yours, bots_turn, yours])
    assert calls == [15, "kept", 15]
