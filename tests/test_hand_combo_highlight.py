"""Which of the viewer's own cards -- hole or board -- make up their current
best hand, highlighted live as the board fills in. High card is not a
combination, so nothing lights up for it."""

import json
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")


def _extract_evaluator():
    start = APP.index("const HAND_RANK_VALUE")
    end = APP.index("\n}\n", APP.index("function bestHandCombo(")) + 3
    return APP[start:end]


def test_the_evaluator_block_is_still_there_to_extract():
    block = _extract_evaluator()
    assert "function evaluateFiveScore(" in block
    assert "function bestHandCombo(" in block


def _best_combo(hole, board):
    block = _extract_evaluator()
    harness = block + f"\nconsole.log(JSON.stringify(bestHandCombo({json.dumps(hole)}, {json.dumps(board)})));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_high_card_has_nothing_to_highlight():
    combo = _best_combo(["Ah", "Kd"], ["9c", "6s", "2h"])
    assert combo is None


def test_fewer_than_five_real_cards_has_nothing_to_highlight():
    """Preflop: two hole cards, no board yet."""
    combo = _best_combo(["Ah", "Kd"], [])
    assert combo is None


def test_a_hidden_hole_card_has_nothing_to_highlight_even_with_a_full_board():
    """Hot-seat mode (multiple humans on one device) shows a player's hole
    cards only on their own turn -- the rest of the time hole_cards comes
    back as ["??", "??"]. The five real board cards alone could still score
    as a straight or better, but that is not "your combination" if your own
    two cards are not even visible yet."""
    combo = _best_combo(["??", "??"], ["7s", "8h", "9c", "Td", "Jh"])
    assert combo is None


def test_one_hidden_hole_card_also_suppresses_the_highlight():
    combo = _best_combo(["Ah", "??"], ["7s", "8h", "9c", "Td", "Jh"])
    assert combo is None


def test_a_pair_highlights_only_the_two_paired_cards_not_the_kickers():
    """A pair of aces with a 9-6-2 board is still the best 5-card hand you
    have, but the 9/6/2 only matter for breaking a tie against another pair
    of aces -- they are not what makes this hand a pair, so only the two
    aces light up."""
    combo = _best_combo(["Ah", "Ad"], ["9c", "6s", "2h"])
    assert sorted(combo) == sorted(["Ah", "Ad"])


def test_two_pair_highlights_all_four_paired_cards_not_the_kicker():
    combo = _best_combo(["Ah", "Ad"], ["9c", "9s", "2h"])
    assert sorted(combo) == sorted(["Ah", "Ad", "9c", "9s"])


def test_trips_highlights_only_the_three_matching_cards():
    combo = _best_combo(["Ah", "Ad"], ["Ac", "9s", "2h"])
    assert sorted(combo) == sorted(["Ah", "Ad", "Ac"])


def test_quads_highlights_the_four_matching_cards_not_the_kicker():
    combo = _best_combo(["Ah", "Ad"], ["Ac", "As", "2h"])
    assert sorted(combo) == sorted(["Ah", "Ad", "Ac", "As"])


def test_a_flush_picks_the_five_matching_suit_cards_over_a_pair():
    """No kicker to strip here -- a flush is defined by all five cards."""
    combo = _best_combo(["Ah", "Kh"], ["9h", "6h", "2h", "As", "9s"])
    assert sorted(combo) == sorted(["Ah", "Kh", "9h", "6h", "2h"])


def test_best_of_seven_cards_is_the_highest_scoring_five():
    """Board alone makes a straight (7-8-9-10-J); the two hole cards should
    not get pulled in over it. A straight uses all five cards -- no kicker."""
    combo = _best_combo(["2c", "3d"], ["7s", "8h", "9c", "Td", "Jh"])
    assert sorted(combo) == sorted(["7s", "8h", "9c", "Td", "Jh"])


def test_full_house_highlights_all_five_cards():
    combo = _best_combo(["Ah", "Ad"], ["Ac", "9s", "9h"])
    assert sorted(combo) == sorted(["Ah", "Ad", "Ac", "9s", "9h"])


def _extract_highlight_fn():
    start = APP.index("function highlightLocalHandCombo() {")
    end = APP.index("\n}\n", start) + 3
    return APP[start:end]


def test_highlight_marks_the_right_dom_elements_and_clears_stale_ones():
    evaluator = _extract_evaluator()
    highlight_fn = _extract_highlight_fn()
    harness = r"""
    const document = {
      _all: [],
      querySelectorAll(sel) {
        if (sel === ".card.hand-combo") return this._all.filter(el => el.classList.has("hand-combo"));
        return [];
      },
      querySelector(sel) {
        if (sel.includes('.seat[data-seat="0"]')) return holeContainer;
        return null;
      },
    };
    function fakeEl(code) {
      return {
        dataset: { code },
        classList: {
          _set: new Set(),
          add(c) { this._set.add(c); },
          remove(c) { this._set.delete(c); },
          has(c) { return this._set.has(c); },
        },
      };
    }
    const hole1 = fakeEl("Ah"), hole2 = fakeEl("Ad");
    // A stale highlight from a previous render, on a card not in this hand.
    hole2.classList.add("hand-combo");
    const holeContainer = { children: [hole1, hole2] };
    const b1 = fakeEl("9c"), b2 = fakeEl("6s"), b3 = fakeEl("2h");
    const boardContainer = { children: [b1, b2, b3] };
    document._all = [hole1, hole2, b1, b2, b3];

    const game = { board: ["9c", "6s", "2h"] };
    function localViewerPlayer() { return { seat: 0, hole_cards: ["Ah", "Ad"] }; }
    function $(id) { return id === "board" ? boardContainer : null; }

    """ + evaluator + "\n" + highlight_fn + r"""

    highlightLocalHandCombo();
    console.log(JSON.stringify({
      hole1: hole1.classList.has("hand-combo"),
      hole2: hole2.classList.has("hand-combo"),
      b1: b1.classList.has("hand-combo"),
      b2: b2.classList.has("hand-combo"),
      b3: b3.classList.has("hand-combo"),
    }));
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    marks = json.loads(result.stdout)
    # Only the pair (both hole cards) lights up -- the three board cards are
    # kickers, not part of what makes this a pair.
    assert marks == {"hole1": True, "hole2": True, "b1": False, "b2": False, "b3": False}


def test_stale_highlights_are_cleared_even_when_the_new_hand_has_nothing_to_show():
    """High card: the clear-all pass at the top must still run, or a
    highlight from a previous street survives into a street with no
    combination at all."""
    evaluator = _extract_evaluator()
    highlight_fn = _extract_highlight_fn()
    harness = r"""
    const document = {
      _all: [],
      querySelectorAll(sel) {
        if (sel === ".card.hand-combo") return this._all.filter(el => el.classList.has("hand-combo"));
        return [];
      },
      querySelector() { return null; },
    };
    function fakeEl(code) {
      return {
        dataset: { code },
        classList: {
          _set: new Set(),
          add(c) { this._set.add(c); },
          remove(c) { this._set.delete(c); },
          has(c) { return this._set.has(c); },
        },
      };
    }
    const stale = fakeEl("Ah");
    stale.classList.add("hand-combo");
    document._all = [stale];

    function localViewerPlayer() { return { seat: 0, hole_cards: ["Ah", "Kd"] }; }
    function $(id) { return null; }
    const game = { board: ["9c", "6s", "2h"] };

    """ + evaluator + "\n" + highlight_fn + r"""

    highlightLocalHandCombo();
    console.log(JSON.stringify({ stale: stale.classList.has("hand-combo") }));
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    assert json.loads(result.stdout) == {"stale": False}
