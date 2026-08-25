"""A rejected action (or a resync landing back on unchanged state) never
moves online-table.js's own snapshot-dedup hash (revision, acting_player,
stacks, ...), so renderSnapshot() short-circuits and
configureReferenceActions() -- the only code that writes button.disabled --
never runs again. isActionPending() itself goes back to false once the
pending flag clears (the overlay disappears), but the buttons stay disabled
from the render that fired while it was still true: inert for the rest of
that turn, "regardless of turn state" as reported live. v038 now listens
for poker8:action-pending itself and forces one more render pass whenever
pending flips back to false, independent of whether the snapshot hash
actually changed."""

import json
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")


def _extract_listener():
    start = SOURCE.index('window.addEventListener("poker8:action-pending"')
    end = SOURCE.index("\n  });\n", start) + len("\n  });\n")
    return SOURCE[start:end]


def test_the_listener_is_registered_after_queuesync_exists():
    listener = _extract_listener()
    assert "queueSync()" in listener
    # Must come after queueSync's own definition in source order, or the
    # closure would reference it before it's assigned.
    assert SOURCE.index("const queueSync = () =>") < SOURCE.index(
        'window.addEventListener("poker8:action-pending"'
    )


def _run(pending):
    listener = _extract_listener()
    harness = """
    const calls = [];
    function queueSync() { calls.push("queueSync"); }
    let registered = null;
    const window = { addEventListener(name, fn) { registered = fn; } };
    %s
    registered({ detail: { pending: %s } });
    console.log(JSON.stringify(calls));
    """ % (listener, json.dumps(pending))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_pending_turning_off_forces_a_render_pass():
    assert _run(pending=False) == ["queueSync"]


def test_pending_turning_on_does_not_force_an_extra_pass():
    # The render that disables the buttons already happens through the
    # normal snapshot path when the action is first sent -- only the
    # re-enable needs this extra nudge.
    assert _run(pending=True) == []
