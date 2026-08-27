"""The showdown modal used to close the instant `game` went null between
hands -- which happens for everyone at the table, not just when a new hand
starts. It has to survive that gap and only let go once a real new hand
is actually live."""

import json
import subprocess
import tempfile
from pathlib import Path

V025 = Path("static/v025-showdown-compare.js").read_text(encoding="utf-8")


def test_the_anchor_still_exists_to_extract():
    assert "let lastTerminalGame = null;" in V025
    assert "renderGame = function renderGameV025() {" in V025


def _run(game_sequence):
    """Drives the real wrapped renderGame() once per entry in game_sequence,
    setting the global `game` to each value first. Returns lastTerminalGame's
    value (by hand_id, or null) after every call."""
    start = V025.index("let lastTerminalGame = null;")
    end = V025.index("};\n", V025.index("renderGame = function renderGameV025()")) + 3
    block = V025[start:end]
    harness = r"""
    let game = null;
    function originalRenderGameStub() {}
    let renderGame = originalRenderGameStub;
    let syncCalls = 0, modalCalls = 0;
    function syncShowdownLayout() { syncCalls++; }
    function renderComparisonModal() { modalCalls++; }

    """ + block + r"""

    const sequence = %s;
    const log = [];
    for (const g of sequence) {
      game = g;
      renderGame();
      log.push(lastTerminalGame ? lastTerminalGame.hand_id : null);
    }
    console.log(JSON.stringify({ log, syncCalls, modalCalls }));
    """ % json.dumps(game_sequence)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_terminal_hand_is_cached_and_survives_game_going_null():
    """result -> the between-hands gap (game null, e.g. "countdown" phase) --
    the cached hand must still be there, not cleared."""
    out = _run([
        {"hand_id": "h1", "terminal": True},
        None,
        None,
    ])
    assert out["log"] == ["h1", "h1", "h1"]


def test_a_genuinely_new_hand_going_live_clears_it():
    """Real next hand: game is non-null and not terminal. That is the one
    signal that should let the old result go."""
    out = _run([
        {"hand_id": "h1", "terminal": True},
        None,
        {"hand_id": "h2", "terminal": False},
    ])
    assert out["log"] == ["h1", "h1", None]


def test_a_second_terminal_hand_replaces_the_cache_directly():
    out = _run([
        {"hand_id": "h1", "terminal": True},
        {"hand_id": "h2", "terminal": True},
    ])
    assert out["log"] == ["h1", "h2"]


def test_never_having_seen_a_hand_is_not_confused_with_the_gap():
    out = _run([None, None])
    assert out["log"] == [None, None]
