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
      mobileHeaderSeatActions: {
        hidden: false,
        classList: { set: new Set(), toggle(name, on) { on ? this.set.add(name) : this.set.delete(name); } },
      },
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
      soloClass: elements.mobileHeaderSeatActions.classList.set.has("ready-up-only"),
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


def _run_solo_ready_up():
    # awaitingReady = viewerState === "seated" && isPreHand() && seatNo != null
    #   && !ready_seats.includes(seatNo) -- built directly rather than routed
    # through _run(queued), which only ever drives the spectator/waiting pair.
    block = _extract_block()
    harness = """
    const viewerState = "seated";
    // The seat the server counts as really seated -- see viewer_seat_no. A
    // seat that is only held reports viewer_state "seated" with no number,
    // and that is the case this button must not appear in.
    let viewerSeatedSeat = 2;
    function isPreHand() { return true; }
    const elements = {
      mobileHeaderSeatActions: {
        hidden: false,
        classList: { set: new Set(), toggle(name, on) { on ? this.set.add(name) : this.set.delete(name); } },
      },
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
    syncHeaderSeatButtons({ ready_seats: [] });
    console.log(JSON.stringify({
      soloClass: elements.mobileHeaderSeatActions.classList.set.has("ready-up-only"),
      readyHidden: elements.mobileHeaderReadyUp.hidden,
      takeHidden: elements.mobileHeaderTakeSeat.hidden,
    }));
    """ % block
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(harness)
        path = handle.name
    result = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(result.stdout)


def test_the_lone_ready_up_button_gets_centred_on_the_header():
    """Was reported live as crooked: with the seat/observe pair hidden, the
    wrap shrunk to fit this one button and inherited wherever the header's
    hamburger-vs-utility width imbalance happened to land it. Centring is
    only safe while this button is genuinely alone -- see the CSS comment on
    .ready-up-only for why sharing the row with the wider pair is exactly
    the overlap bug the flow-layout fix solved."""
    out = _run_solo_ready_up()
    assert out["soloClass"] is True
    assert out["readyHidden"] is False
    assert out["takeHidden"] is True


def test_the_pair_never_gets_the_solo_centring_class():
    # Absolute-centring the wrap while the wider pair shares it is exactly
    # the overlap bug the flow-layout fix (see the CSS comment) solved --
    # the class must stay off whenever the pair is what's showing.
    assert _run("spectator")["soloClass"] is False
    assert _run("waiting")["soloClass"] is False


def test_the_seat_pair_is_as_wide_as_its_widest_label_really_renders():
    """88px was measured in Inter. A phone that falls back to its own system
    face draws the same string wider, and "Занять место" arrived as
    "Занять ме...". The pair still has one fixed width -- the labels swap in
    place and an auto width resized them on every click -- but that width is
    now measured from the widest label in whatever font actually rendered."""
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    rule = source[source.index("#mobileHeaderTakeSeat,"):]
    rule = rule[:rule.index("}")]
    assert "width:var(--p8-seat-action-w" in rule
    assert "width:88px" not in rule

    sizer = source[source.index("function sizeHeaderSeatButtons() {"):]
    sizer = sizer[:sizer.index(chr(10) + "  }")]
    # Every label either button can carry, or the swap resizes the pair.
    for label in ("Занять место", "Наблюдать", "В очереди", "Отменить"):
        assert label in source
    assert "SEAT_ACTION_LABELS" in sizer
    assert "getComputedStyle" in sizer, "measured in the rendered font, not assumed"
    assert "innerWidth" in sizer, "capped so a wide face cannot push the row apart"

    # placeHeaderActions is the one that already runs on every render and on
    # the resize/breakpoint change -- the two moments the font or the width
    # budget can have moved.
    place = source[source.index("function placeHeaderActions() {"):]
    assert "sizeHeaderSeatButtons();" in place[:place.index(chr(10) + "  }")]
