"""Committing the whole stack gets a beat to take it back, not a second tap."""

from pathlib import Path

SOURCE = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")


def _function(name):
    body = SOURCE[SOURCE.index(f"function {name}("):]
    return body[:body.index("\n  }") + 4]


def test_the_first_press_arms_it_rather_than_sending_it():
    """It used to fire on the press, which left the drain bar in the stylesheet
    with nothing to drive it."""
    body = _function("confirmCommit")
    assert "armedTimer = window.setTimeout" in body
    assert "fireArmedCommit" in body
    # The only sendAction for an armed all-in lives in the timer's callback.
    assert "sendAction" not in body.split("if (!localTurn)")[1].split("}")[0]


def test_pressing_again_takes_it_back_instead_of_confirming_it():
    body = _function("confirmCommit")
    assert "clearArmedAction();" in body, "the second press has to cancel"


def test_the_bar_never_outlasts_the_turn_clock():
    """Three seconds, or whatever the server's own deadline leaves, whichever
    is sooner -- the bar must not be why a hand times out."""
    body = _function("confirmCommit")
    assert "game.action_deadline" in body
    assert "Math.min(COMMIT_CONFIRM_MS" in body
    assert "- 500" in body, "and it commits before the deadline, not on it"


def test_the_bar_drains_over_the_window_actually_used():
    assert "animation:v038ConfirmDrain var(--v038-arm-ms,3000ms)" in SOURCE
    assert 'content:attr(data-arm-label)' in SOURCE
    assert "COMMIT_CONFIRM_MS = 3000" in SOURCE


def test_the_armed_spot_is_rechecked_before_the_stack_goes_in():
    """A new street, a new actor or a changed amount all mean this is no longer
    the bet that was asked for."""
    body = _function("fireArmedCommit")
    assert "fingerprint !== armedFingerprintOf(source)" in body
    assert "isLocalHumanTurn()" in body


def test_folding_arms_the_same_way_shoving_does():
    """Folding is as final as pushing the stack in, so it gets the same beat to
    take it back. Checking does not -- the left slot is one or the other
    depending on the spot, and only the fold half arms."""
    handler = SOURCE[SOURCE.index("const liveAllIn = slot ==="):]
    handler = handler[:handler.index("clearPendingAction(false);")]
    assert 'if (liveKey === "fold") return confirmCommit("fold"' in handler
    assert 'liveKey === "check"' not in handler, "checking is not a commitment"

    firing = _function("fireArmedCommit")
    assert 'source === "fold"' in firing and 'sendAction("fold", 0)' in firing


def test_a_player_on_the_way_out_is_not_asked_to_confirm():
    """Leaving through the lobby or the leave button folds the hand server-side
    anyway -- the seat is going. A beat to reconsider is a beat wasted."""
    body = _function("confirmCommit")
    assert "viewerIsLeaving()" in body
    leaving = body[body.index("viewerIsLeaving()"):]
    assert "sendAction(" in leaving[:400], "it sends straight away instead of arming"

    predicate = _function("viewerIsLeaving")
    assert 'viewerState === "leaving"' in predicate
