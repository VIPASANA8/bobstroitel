"""An all-in before the river shows all 5 cards, waits 3s, then the modal --
instead of the felt snapping straight to a verdict."""

import json
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")
V025 = Path("static/v025-showdown-compare.js").read_text(encoding="utf-8")


def _extract(start_marker, end_marker):
    start = APP.index(start_marker)
    end = APP.index(end_marker, start)
    return APP[start:end]


def test_the_anchors_still_exist_to_extract():
    """Guards the slice below: if these move, the harness needs to move with
    them rather than silently testing a stale copy."""
    assert "window.Poker8LegacyView = {" in APP
    assert "let onlineRunoutHandId = null;" in APP
    assert "async function revealOnlineRunout(previousGame, finishedGame) {" in APP


def _run(events):
    """Feed a sequence of {op: "snapshot"|"resolveReveal"|"resolveSleep", ...}
    through the real renderSnapshot/revealOnlineRunout, with revealRemainingBoard
    and sleep replaced by controllable promises so the test drives the timing
    by hand instead of racing real ones. Returns a log of every renderGame()
    and revealRemainingBoard() call, plus `game`'s value after each event.
    """
    legacy_view = _extract("window.Poker8LegacyView = {", "async function revealOnlineRunout")
    runout_fn = _extract("async function revealOnlineRunout(previousGame, finishedGame) {\n", "\n}\n")
    harness = r"""
    let game = null;
    let tableData = null;
    const window = {};
    const log = [];
    let pendingReveals = [];
    let pendingSleeps = [];
    function revealRemainingBoard(previousGame, nextGame) {
      log.push(["reveal", previousGame && previousGame.hand_id || null, nextGame.hand_id]);
      return new Promise(resolve => pendingReveals.push(resolve));
    }
    function sleep(ms) {
      log.push(["sleep", ms]);
      return new Promise(resolve => pendingSleeps.push(resolve));
    }
    function renderGame() {
      log.push(["renderGame", game && game.hand_id || null, game && game.terminal || false]);
    }

    """ + legacy_view + "\n" + runout_fn + "\n}\n" + r"""

    const drain = () => new Promise(resolve => setTimeout(resolve, 0));
    const events = %s;
    for (const ev of events) {
      if (ev.op === "snapshot") {
        window.Poker8LegacyView.renderSnapshot({ table: {}, state: ev.state, viewerState: "seated" });
      } else if (ev.op === "resolveReveal") {
        const r = pendingReveals.shift();
        if (r) r();
      } else if (ev.op === "resolveSleep") {
        const r = pendingSleeps.shift();
        if (r) r();
      }
      // Let the resolved promise's continuation actually run (it is a
      // microtask chain: past the `await`, possibly into the next `await`,
      // e.g. resolving revealRemainingBoard has to reach sleep()'s own call
      // before there is anything for a later resolveSleep to resolve) before
      // the next event is driven, or these race the very thing being tested.
      await drain();
      log.push(["checkpoint", game && game.hand_id || null, game && game.terminal || false, onlineRunoutHandId, pendingReveals.length, pendingSleeps.length]);
    }
    log.push(["final", game && game.hand_id || null, onlineRunoutHandId]);
    console.log(JSON.stringify(log));
    """ % json.dumps(events)
    wrapped = "(async () => {\n" + harness + "\n})();"
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as handle:
        handle.write(wrapped)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def _state(hand_id, board, terminal, phase="active"):
    return {
        "hand_id": hand_id, "phase": phase, "terminal": terminal, "board": board,
        "players": {}, "current_seats": {}, "viewer_player_id": None,
        "ready_seats": [], "pot": 0, "street": "river" if len(board) >= 5 else "flop",
        # None, not missing: `viewer?.id === state.acting_player` is `undefined
        # === undefined` (true) with no acting_player at all, which then reads
        # a field off a null viewer and throws -- an unrelated quirk in the
        # code under test that a real snapshot never hits because the server
        # always sends a real acting_player or nothing comparably falsy.
        "acting_player": None,
        "current_bet": 0, "min_raise_size": 1, "legal_actions": [],
    }


def test_a_normal_river_showdown_is_not_treated_as_a_runout():
    """The river is its own non-terminal snapshot with a chance to act, so by
    the time terminal arrives the board is already 5 cards -- no reveal, no
    wait, straight to renderGame() like before this feature existed."""
    log = _run([
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], False)},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
    ])
    kinds = [row[0] for row in log if row[0] in ("reveal", "renderGame")]
    assert kinds == ["renderGame", "renderGame"], "no reveal call for an ordinary river showdown"


def test_an_allin_before_the_river_reveals_then_waits_then_commits():
    """Preflop all-in: the very next snapshot is already terminal with all 5
    cards. Must not touch `game` (or fire renderGame) until the reveal and
    the 3s wait both resolve."""
    log = _run([
        {"op": "snapshot", "state": _state("h1", [], False)},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
    ])
    reveal_calls = [row for row in log if row[0] == "reveal"]
    # previousGame is hand h1 itself, mid-hand (the first, non-terminal
    # snapshot already committed normally) -- not a null `game`, which would
    # only be true before any hand had ever been seen.
    assert reveal_calls == [["reveal", "h1", "h1"]]
    # The 3s wait only starts once the reveal itself resolves -- not exercised
    # here (see test_the_reveal_completing_is_what_finally_commits_and_renders).
    assert not [row for row in log if row[0] == "sleep"]
    # `game` after the runout snapshot must still be the pre-terminal hand --
    # the checkpoint logged immediately after that snapshot event.
    checkpoints = [row for row in log if row[0] == "checkpoint"]
    assert checkpoints[-1][1] == "h1"
    assert checkpoints[-1][2] is False, "the terminal result was committed before the reveal even started"
    assert checkpoints[-1][3] == "h1", "onlineRunoutHandId not armed"


def test_the_reveal_completing_is_what_finally_commits_and_renders():
    log = _run([
        {"op": "snapshot", "state": _state("h1", [], False)},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
        {"op": "resolveReveal"},
        {"op": "resolveSleep"},
    ])
    render_calls = [row for row in log if row[0] == "renderGame"]
    # One renderGame() from the first (non-terminal) snapshot, none from the
    # runout snapshot itself, one more once the reveal+wait finish.
    assert render_calls == [["renderGame", "h1", False], ["renderGame", "h1", True]]
    final = log[-1]
    assert final == ["final", "h1", None], "game ends up committed, and the guard clears"


def test_a_redundant_snapshot_mid_reveal_does_not_restart_or_commit_early():
    """The poll timer or a resync can re-deliver the same still-revealing
    hand. It must not fire a second reveal, and it must not fall through to
    committing `game` while the first reveal is still in flight."""
    log = _run([
        {"op": "snapshot", "state": _state("h1", [], False)},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
    ])
    reveal_calls = [row for row in log if row[0] == "reveal"]
    assert len(reveal_calls) == 1, "a duplicate snapshot restarted the reveal"
    checkpoints = [row for row in log if row[0] == "checkpoint"]
    assert checkpoints[-1][2] is False, "the duplicate snapshot committed the terminal result early"


def test_a_new_hand_arriving_mid_reveal_is_not_clobbered_when_the_old_reveal_finishes():
    """The server starts the next hand a fixed 7s after the current one ends
    (next_hand_at in online/runtime.py), with no idea a client-side reveal is
    still playing out -- so h2's own first snapshot can arrive before h1's
    reveal resolves. It must not be committed early (that would skip h1's
    winner entirely), and it must not be dropped either (that was the actual
    bug report: the felt jumped straight to h2 with no result shown, and the
    pot h1 already paid out looked like it had vanished). It waits, then
    catches up right after h1 finally commits."""
    log = _run([
        {"op": "snapshot", "state": _state("h1", [], False)},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
        {"op": "snapshot", "state": _state("h2", [], False)},  # a new hand takes over mid-reveal
    ])
    checkpoints = [row for row in log if row[0] == "checkpoint"]
    # h1's own terminal snapshot must still not be committed, and h2 must not
    # have jumped ahead of it either.
    assert checkpoints[-1][1] == "h1"
    assert checkpoints[-1][2] is False

    log = _run([
        {"op": "snapshot", "state": _state("h1", [], False)},
        {"op": "snapshot", "state": _state("h1", ["Ah", "Kd", "Qs", "2c", "3d"], True, phase="result")},
        {"op": "snapshot", "state": _state("h2", [], False)},
        {"op": "resolveReveal"},
        {"op": "resolveSleep"},
    ])
    render_calls = [row for row in log if row[0] == "renderGame"]
    # h1's winner is shown (terminal:true) before h2 is ever painted -- not
    # skipped, and not raced.
    assert render_calls == [
        ["renderGame", "h1", False],
        ["renderGame", "h1", True],
        ["renderGame", "h2", False],
    ]
    final = log[-1]
    assert final == ["final", "h2", None]
