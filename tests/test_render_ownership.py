"""One owner per render function; layers append, they do not replace.

Four layers used to reassign renderSeats, each wrapping the one before, so a
call walked a five-deep chain that only worked while every link remembered to
call its predecessor -- and one throw anywhere in it silently cost the work of
every layer after.
"""

import re
from pathlib import Path

APP = Path("static/app.js").read_text(encoding="utf-8")
LAYERS = sorted(Path("static").glob("v0*.js"))

OWNED = ("renderSeats", "renderMobileHeader", "renderPotChips", "chipStackHtml")


def test_the_owned_functions_live_in_one_file():
    for name in OWNED:
        assert f"function {name}(" in APP, name


def test_no_layer_takes_one_back():
    offenders = []
    for layer in LAYERS:
        source = layer.read_text(encoding="utf-8")
        for name in OWNED:
            if re.search(rf"^\s*{name} = ", source, re.M):
                offenders.append(f"{layer.name} overrides {name}")
    assert offenders == [], offenders


def test_layers_hook_in_instead():
    """The registrations that replaced those four wrappers."""
    hooks = {
        "v024-ready-phase.js": ["renderSeatReadiness", "publishReadySnapshot", "renderReadyControls"],
        "v026-seat-status-layout.js": ["normalizeSeatStatuses"],
        "v027-compact-seats-controls.js": ["decorateSeats"],
        "v028-center-ready.js": ["syncCenterReadyUi"],
    }
    for name, expected in hooks.items():
        source = (Path("static") / name).read_text(encoding="utf-8")
        for fn in expected:
            assert f"onRendered(" in source and fn in source, f"{name}: {fn}"


def test_one_failing_hook_does_not_cost_the_others():
    """The whole point of the chain being gone: a layer that throws used to
    take every layer after it down with it."""
    body = APP[APP.index("function runRenderHooks"):]
    body = body[:body.index("\n}")]
    assert "try {" in body and "catch" in body
    assert "console.error" in body, "and it has to say so rather than vanish"
