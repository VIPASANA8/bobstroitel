"""mode-active used to light up whichever button was still on offer
(`take.classList.toggle("mode-active", !queued)`) instead of the one that
matches the viewer's actual current state -- the same thing aria-pressed
on the very next line already said. A passive spectator (queued=false) got
"Занять место" highlighted as if they had already chosen it, while
aria-pressed correctly pointed at "Наблюдатель". Fixed by keying both
classes off the exact same condition as their aria-pressed neighbour."""

import json
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("static/online-table.js").read_text(encoding="utf-8")


def _extract_block():
    start = SOURCE.index("  function syncHeaderSeatButtons(state) {")
    end = SOURCE.index("\n  }\n", start) + len("\n  }\n")
    return SOURCE[start:end]


def test_the_block_is_still_there_to_extract():
    block = _extract_block()
    assert 'classList.toggle("mode-active"' in block
    assert "aria-pressed" in block


def _fake_button():
    return {
        "hidden": False,
        "disabled": False,
        "textContent": "",
        "title": "",
        "classes": set(),
        "attrs": {},
    }


def _run(queued):
    block = _extract_block()
    harness = """
    const viewerState = %s;
    function viewerSeatNo() { return null; }
    function isPreHand() { return false; }
    const elements = {
      mobileHeaderSeatActions: { hidden: false },
      mobileHeaderReadyUp: { hidden: false },
      mobileHeaderTakeSeat: {
        textContent: "", disabled: false, title: "",
        classList: { set: new Set(), toggle(name, on) { on ? this.set.add(name) : this.set.delete(name); } },
        setAttribute(name, value) { this[name] = value; },
      },
      mobileHeaderObserve: {
        textContent: "", disabled: false, title: "",
        classList: { set: new Set(), toggle(name, on) { on ? this.set.add(name) : this.set.delete(name); } },
        setAttribute(name, value) { this[name] = value; },
      },
    };
    function $(id) { return elements[id] || null; }
    %s
    syncHeaderSeatButtons({});
    console.log(JSON.stringify({
      takeActive: elements.mobileHeaderTakeSeat.classList.set.has("mode-active"),
      takePressed: elements.mobileHeaderTakeSeat["aria-pressed"],
      observeActive: elements.mobileHeaderObserve.classList.set.has("mode-active"),
      observePressed: elements.mobileHeaderObserve["aria-pressed"],
    }));
    """ % (json.dumps(queued), block)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_a_passive_spectator_sees_observe_as_the_active_mode_not_take_seat():
    out = _run("spectator")
    assert out["observeActive"] is True
    assert out["takeActive"] is False
    # mode-active must agree with aria-pressed on the same button, or the
    # visual toggle and the accessibility state tell a screen reader and a
    # sighted user two different stories.
    assert out["observePressed"] == "true"
    assert out["takePressed"] == "false"


def test_a_queued_seat_request_flips_take_seat_to_the_active_mode():
    out = _run("waiting")
    assert out["takeActive"] is True
    assert out["observeActive"] is False
    assert out["takePressed"] == "true"
    assert out["observePressed"] == "false"
