"""Local-trainer chrome leaked onto the desktop online table.

`.seat-edit` (the "•••" seat editor) was hidden only by `mobile.css:77`,
and `mobile.css` is linked with `media="(max-width: 780px)"`
(`index.html`), so it never applied above 780px. `.table-count` was hidden
only inside `style.css`'s own `max-width:780px` blocks. Measured live on
production at 1280px: a "•••" button on every bot seat and a header
reading "4 / 7 игроков" -- on six-max tables, from the seven-seat era.

These are controls for the *local trainer*, not for a narrow screen, so
the key is the mode (`.poker8-online`), never the viewport. That is also
the pattern the file already used for `.local-only-control`,
`.solver-panel` and friends. Local mode must keep all of it.
"""

import re
from pathlib import Path

SOURCE = Path("static/online-table.js").read_text(encoding="utf-8")

#: Everything below this offset is inside the phone-only block and would
#: therefore never reach desktop -- which is the whole bug.
PHONE_BLOCK = SOURCE.index("@media(max-width:780px){")


def _rule_offset(selector):
    matches = [m.start() for m in re.finditer(re.escape(selector), SOURCE)]
    assert matches, f"no rule found for {selector}"
    return min(matches)


def test_the_leaking_controls_are_hidden_by_mode():
    for selector in (".poker8-online .seat-edit", ".poker8-online .table-count"):
        assert f"{selector}," in SOURCE or f"{selector}{{" in SOURCE, selector


def test_those_hides_sit_outside_the_phone_only_block():
    # The positional check is the one that actually encodes the bug: a rule
    # that is correct but sits below this offset is width-gated again and
    # desktop is back to where it started.
    for selector in (".poker8-online .seat-edit", ".poker8-online .table-count"):
        assert _rule_offset(selector) < PHONE_BLOCK, selector


def test_the_local_trainer_identity_is_hidden_online_only():
    assert ".poker8-online .topbar .brand-wrap .eyebrow" in SOURCE
    assert ".poker8-online .topbar h1" in SOURCE
    assert _rule_offset(".poker8-online .topbar h1") < PHONE_BLOCK


def test_local_mode_still_gets_every_one_of_them():
    """No unscoped kill rule -- opening index.html with no ?table= must
    still show the trainer's own topbar, seat editors and player count."""
    for bare in (
        ".seat-edit{display:none",
        ".table-count{display:none",
        ".topbar h1{display:none",
    ):
        for hit in re.finditer(re.escape(bare), SOURCE):
            prefix = SOURCE[max(0, hit.start() - 60):hit.start()]
            assert ".poker8-online" in prefix, f"unscoped hide: {bare}"
