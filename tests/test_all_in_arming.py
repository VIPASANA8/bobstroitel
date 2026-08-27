"""Irreversible mobile bets require an explicit confirmation tap."""

from pathlib import Path

SOURCE = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")


def _function(name):
    body = SOURCE[SOURCE.index(f"function {name}("):]
    return body[:body.index("\n  }") + 4]


def test_all_in_opens_the_sizing_overlay_without_submitting():
    handler = _function("configureReferenceActions")
    assert 'if (def.allIn)' in handler
    branch = handler[handler.index('if (def.allIn)'):]
    assert 'openSizingMode("all_in", amountBounds().max)' in branch
    assert 'sendAction("all_in"' not in branch.split("if (!liveTurn)")[0]


def test_only_the_explicit_confirmation_submits_all_in():
    body = _function("confirmSizingMode")
    assert 'if (!sizingMode' in body
    assert 'if (action === "all_in") return sendAction("all_in", 0)' in body


def test_vertical_gesture_selects_an_amount_but_never_submits():
    body = _function("finishVerticalBetGesture")
    assert "syncSizingModeText()" in body
    assert "sendAction" not in body
    assert "confirmSizingMode" not in body


def test_stale_or_illegal_sizing_mode_is_closed_before_render():
    body = _function("syncFinalReference")
    assert "aggressiveLegal" in body
    assert "closeSizingMode(false)" in body


def test_all_in_label_is_spelled_consistently():
    assert 'label:"ALL-IN"' in SOURCE
    assert 'label:"ALL IN"' not in SOURCE
