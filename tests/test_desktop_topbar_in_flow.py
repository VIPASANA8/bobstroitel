"""The desktop topbar was an overlay left over from the alpha design.

`style.css:2590` (`.neon-ref-v107 .topbar`) pins it `position:absolute;
inset:0 0 auto; z-index:310; height:76px; pointer-events:none` -- it floated
over a full-bleed table and reserved no height. Measured live at 1732px:
`.layout` began at y:50 while the bar occupied y:0-76, so the chat panel's
own "Чат стола" heading (y:67-86) was painted over by it, and
`style.css:2335`'s `max-width:1440px` left the bar visibly narrower than the
1692px shell it sat on.

v039 puts it back in flow on desktop. Three details are load-bearing and
each was found by measuring rather than reading:

* `height:auto` -- `min-height` alone is inert against that hard `height`,
  so the bar stayed 76px and the trim bought nothing.
* the shell is a flex column and `.layout` flexes -- its old
  `height:calc(100dvh - 76px)` stood for a bar that reserved nothing, and
  would have counted the bar twice once it did.
* the bar takes `min(1500px,100%)`, the same width `style.css:2589` gives
  `.layout`, so header and content share an edge.
"""

import re
from pathlib import Path

V039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")


def _topbar_rule():
    start = V039.index("body.v014.poker8-desktop-v2 .topbar{")
    return V039[start:V039.index("}", start)]


def test_the_topbar_is_in_flow_so_it_reserves_its_own_height():
    rule = _topbar_rule()
    assert "position:relative!important" in rule
    assert "inset:auto!important" in rule


def test_it_is_clickable_again():
    # The alpha bar was click-through because the table lay underneath it.
    assert "pointer-events:auto!important" in _topbar_rule()


def test_height_auto_accompanies_the_min_height():
    rule = _topbar_rule()
    assert "min-height:" in rule
    assert "height:auto!important" in rule, "min-height is inert against style.css's hard height"


def test_the_bar_matches_the_width_the_layout_gets():
    rule = _topbar_rule()
    assert "width:min(1500px,100%)!important" in rule
    assert "margin-inline:auto!important" in rule
    # The number is not invented here -- it mirrors style.css's .layout.
    assert "width:min(1500px,100%)" in Path("static/style.css").read_text(encoding="utf-8")


def test_the_layout_no_longer_subtracts_the_bar_it_now_sits_below():
    start = V039.index("body.v014.poker8-v2-sixmax.poker8-desktop-v2 .layout{")
    rule = V039[start:V039.index("}", start)]
    # The rule's own comment quotes the value it replaced, so strip comments
    # before asserting on the live declarations.
    declarations = re.sub(r"/\*.*?\*/", "", rule, flags=re.S)
    assert "calc(100dvh - 76px)" not in declarations, "would count the in-flow bar twice"
    assert "flex:1 1 auto!important" in rule

    shell_start = V039.index("body.v014.poker8-desktop-v2 .app-shell{")
    shell = V039[shell_start:V039.index("}", shell_start)]
    assert "flex-direction:column!important" in shell
    assert "height:100dvh!important" in shell


def test_the_action_panel_tracks_the_whole_felt_instead_of_a_phone_column():
    start = V039.index("body.v014.poker8-v2-sixmax.poker8-desktop-v2 .table-frame > .action-panel{")
    rule = V039[start:V039.index("}", start)]
    assert "inset:0!important" in rule
    assert "width:100%!important" in rule
    assert "height:100%!important" in rule
