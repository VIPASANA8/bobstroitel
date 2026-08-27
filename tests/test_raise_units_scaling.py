"""The server decodes amount_units as amount_units / table.big_blind_units
(online/runtime.py) -- only "micro" rooms happen to have big_blind_units=100.
A hardcoded *100 client-side silently sent a smaller number than typed on
"low" (200) or "mid" (1000) tables, so a raise well above the displayed
minimum still failed the engine's own min-raise check on the rescaled-down
amount. Reported live: minimum showed 4, a raise of 7 was rejected."""

import json
import subprocess
import tempfile
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")


def _extract():
    start = APP.index("async function sendAction(action, amount = 0) {")
    end = APP.index("\n}\n", start) + 3
    return APP[start:end]


def test_the_function_is_still_there_to_extract():
    block = _extract()
    assert "tableData?.big_blind_units" in block
    assert "Poker8Transport.sendAction" in block


def _sent_amount_units(big_blind_units, amount):
    block = _extract()
    harness = f"""
    const window = {{}};
    let game = {{ hand_id: "h1", terminal: false }};
    let animationBusy = false;
    let tableData = {{ big_blind_units: {json.dumps(big_blind_units)} }};
    window.Poker8OnlineTable = true;
    let sent = null;
    window.Poker8Transport = {{ sendAction(action, amountUnits) {{ sent = {{ action, amountUnits }}; }} }};
    const Poker8Transport = window.Poker8Transport;
    {block}
    sendAction("raise", {json.dumps(amount)}).then(() => {{
      console.log(JSON.stringify(sent));
    }});
    """
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_micro_table_sends_bb_times_100():
    sent = _sent_amount_units(100, 7)
    assert sent == {"action": "raise", "amountUnits": 700}


def test_a_low_table_scales_by_its_own_200_not_a_hardcoded_100():
    """This is the exact reported failure: a raise of 7 on a 200-unit table
    used to send 700 (7 * hardcoded 100), which the server then divided by
    200 -- landing at 3.5, below the displayed minimum of 4."""
    sent = _sent_amount_units(200, 7)
    assert sent == {"action": "raise", "amountUnits": 1400}


def test_a_mid_table_scales_by_its_own_1000():
    sent = _sent_amount_units(1000, 7)
    assert sent == {"action": "raise", "amountUnits": 7000}


def test_missing_big_blind_units_falls_back_to_100_not_zero():
    sent = _sent_amount_units(None, 7)
    assert sent == {"action": "raise", "amountUnits": 700}
