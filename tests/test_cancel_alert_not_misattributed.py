"""Clicking "Отменить" (the queued-state Observe button, which calls
cancelQueue()) used to pop "на балансе не хватило фишек на вход" -- the
server marks both a self-initiated cancel and an insufficient-funds
auto-cancel with the exact same queue_state "cancelled" (see cancel_ready
and the funds check in online/seating.py), so noticeLostSeatRequest()
couldn't tell them apart from that state alone. Fixed with a flag this tab
sets right before it asks for its own cancel."""

import json
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/online-table.js").read_text(encoding="utf-8")


def test_the_guard_flag_exists():
    assert "let voluntaryCancelInFlight = false;" in SOURCE
    assert "voluntaryCancelInFlight = true;" in SOURCE


def _extract(marker, end_marker):
    start = SOURCE.index(marker)
    end = SOURCE.index(end_marker, start) + len(end_marker)
    return SOURCE[start:end]


def _run(queue_state, self_cancelled):
    block = _extract(
        "function noticeLostSeatRequest(queueState) {",
        "\n  }\n",
    )
    harness = """
    let lastQueueState = "waiting";
    let voluntaryCancelInFlight = %s;
    const alerts = [];
    function alert(msg) { alerts.push(msg); }
    %s
    noticeLostSeatRequest(%s);
    console.log(JSON.stringify(alerts));
    """ % (json.dumps(self_cancelled), block, json.dumps(queue_state))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_deliberate_cancel_shows_no_alert():
    assert _run("cancelled", self_cancelled=True) == []


def test_a_server_side_funds_cancel_still_warns():
    alerts = _run("cancelled", self_cancelled=False)
    assert len(alerts) == 1
    assert "не хватило фишек" in alerts[0]


def test_expiry_still_warns_regardless_of_the_new_flag():
    # Expiry has nothing to do with a self-initiated cancel, so the guard
    # must not accidentally swallow this one too.
    alerts = _run("expired", self_cancelled=True)
    assert len(alerts) == 1
    assert "истекла" in alerts[0]
