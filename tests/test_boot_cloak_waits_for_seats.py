"""A crooked table flashed for about a second on entry.

The boot cloak in index.html hides `.table-frame` until `p8-boot-ready`.
v041 -- the last mobile layer to load -- added that class the moment its
stylesheet was in place. But styles being ready is not the same as the
table being ready: v040 positions the seats from `applyDynamicLayout`,
which only runs once `syncComponentUi` is called with real data, i.e.
after the first snapshot arrives over the network. In between, the table
was visible with every seat still at `style.css`'s seven-seat defaults.

So the cloak now lifts from v040, after a layout pass, and v041 must not
lift it at all. index.html's ~3s failsafe still guarantees the cloak can
never stick.
"""

import re
from pathlib import Path

V040 = Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
V041 = Path("static/v041-poker8-v2-turn-clarity.js").read_text(encoding="utf-8")
INDEX = Path("static/index.html").read_text(encoding="utf-8")


def test_the_layer_that_positions_seats_is_the_one_that_lifts_the_cloak():
    assert 'document.body.classList.add("p8-boot-ready")' in V040


def test_no_layer_lifts_it_merely_on_load():
    """v041 loading means the styles arrived, not that a seat has moved."""
    assert "p8-boot-ready" not in V041


def test_every_exit_path_clears_it():
    """Including the empty-table one -- with no seats to place there is
    nothing left to jump, so waiting the full failsafe there would be a
    blank table for no reason."""
    start = V040.index("function applyDynamicLayout(gameState, tableState) {")
    wrapper = V040[start:V040.index("function applyDynamicLayoutInner")]
    assert "finally" in wrapper, "an early return would skip the class"
    assert 'classList.add("p8-boot-ready")' in wrapper

    # The real work must have moved into the inner function, or the wrapper
    # is wrapping nothing.
    inner = V040[V040.index("function applyDynamicLayoutInner"):]
    assert "orderedActiveSeats" in inner[:2000]


def test_the_failsafe_survives():
    """The cloak must never be able to stick if a layer fails to load."""
    match = re.search(r'setTimeout\(\(\) => document\.body\.classList\.add\("p8-boot-ready"\), (\d+)\)', INDEX)
    assert match, "index.html lost its boot failsafe"
    assert int(match.group(1)) <= 5000
