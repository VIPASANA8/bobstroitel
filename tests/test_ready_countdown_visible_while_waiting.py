"""The center-table countdown ring used to only fire from hand_starts_at (the
final 5s grace once everyone is ready), so a player who had not clicked ready
saw no clock at all during the 30s ready_deadline window the server already
tracks and already sends in the snapshot. Wire it in as a fallback."""

import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/online-table.js").read_text(encoding="utf-8")


def _extract_line():
    start = SOURCE.index("const countdownEndsAt = state?.hand_starts_at")
    end = SOURCE.index("\n", start)
    return SOURCE[start:end]


def test_the_line_is_still_there_to_extract():
    assert "ready_deadline" in _extract_line()


def _ends_at(state):
    line = _extract_line()
    harness = f"""
    const state = {state};
    {line}
    console.log(countdownEndsAt);
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return result.stdout.strip()


def test_hand_starts_at_wins_when_both_are_armed():
    state = '{"hand_starts_at": "2026-01-01T00:00:05Z", "ready_deadline": "2026-01-01T00:00:30Z"}'
    assert _ends_at(state) == "2026-01-01T00:00:05Z"


def test_ready_deadline_drives_the_ring_while_still_waiting_on_others():
    state = '{"hand_starts_at": null, "ready_deadline": "2026-01-01T00:00:30Z"}'
    assert _ends_at(state) == "2026-01-01T00:00:30Z"


def test_neither_armed_means_no_countdown():
    state = "{}"
    assert _ends_at(state) == "undefined"
