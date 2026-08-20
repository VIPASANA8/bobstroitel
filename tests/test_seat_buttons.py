"""The empty seats are how you sit down at a network table."""

import re
from pathlib import Path


def test_an_empty_seat_is_pressable_on_a_network_table():
    """Every network table rendered its six empty seats disabled, so the only
    thing on screen offering a way in could not be pressed."""
    source = Path("static/app.js").read_text(encoding="utf-8")
    locked = re.search(r"const locked = (.+);", source).group(1)
    assert "ONLINE_TABLE_ID ? false" in locked, \
        "an online table must not lock its empty seats"


def test_only_one_empty_seat_carries_the_offer():
    """Six identical circles round an empty table is the same offer six times."""
    app = Path("static/app.js").read_text(encoding="utf-8")

    assert "function seatHtml(config, player, offerSeat = true)" in app
    assert 'if (ONLINE_TABLE_ID && !offerSeat) return "";' in app
    assert "config.seat === offeredSeat" in app


def test_the_seat_click_is_delegated_so_a_redraw_cannot_lose_it():
    """The mobile layers rebuild the seat ring on every snapshot, and a handler
    bound to the element dies with the node it was bound to."""
    app = Path("static/app.js").read_text(encoding="utf-8")
    online = Path("static/online-table.js").read_text(encoding="utf-8")

    # Offline only: online must not bind to the node at all.
    binding = app[app.index('document.querySelectorAll("[data-add-seat]")') - 400:]
    binding = binding[:binding.index("});") + 3]
    assert "if (!ONLINE_TABLE_ID) {" in binding

    handler = online[online.index('closest?.("[data-add-seat]")') - 300:]
    handler = handler[:handler.index("});") + 3]
    assert 'document.addEventListener("click"' in handler
    assert "ready(Number(button.dataset.addSeat))" in handler
    assert "seatNo == null ? firstOpenSeat(latestState) : seatNo" in online


def test_a_drawer_button_marked_hidden_is_actually_hidden():
    """[hidden] is only display:none in the user-agent sheet, so a rule that
    sets display outranks it -- and every button the drawer meant to hide
    stayed on screen, owner-only controls included."""
    online = Path("static/online-table.js").read_text(encoding="utf-8")

    # Same ancestors plus the attribute, so it outranks the display rule on
    # specificity and does not depend on which one the file lists first.
    assert ".poker8-online .mobile-drawer .network-table-action[hidden]{display:none}" in online
    assert ".poker8-online .mobile-drawer .network-table-action{display:block" in online


def test_leaving_your_own_room_says_the_room_stays_open():
    """One open room per player, and leaving does not close it -- so somebody
    who left and tried to open another was told they already had one, with no
    idea which or why."""
    online = Path("static/online-table.js").read_text(encoding="utf-8")
    handler = online[online.index('$("mobileDrawerLeave")'):]
    handler = handler[:handler.index("});")]
    assert "ownsThisRoom" in handler
    assert "Закрыть комнату" in handler, "and it points at the control that does close it"


def test_closing_a_dialog_does_not_submit_it():
    """A button with no type inside a form is a submit button, so both dialog
    crosses submitted the form they were meant to abandon: closing the buy-in
    seated you at the table, and closing the room form opened a room."""
    markup = Path("static/lobby.html").read_text(encoding="utf-8")
    script = Path("static/lobby.js").read_text(encoding="utf-8")

    closers = re.findall(r'<button class="dialog-close"[^>]*>', markup)
    assert len(closers) == 2, "both dialogs still have a cross"
    for closer in closers:
        assert 'type="button"' in closer, closer
    assert '.dialog-close' in script and 'close("cancel")' in script


def test_a_seat_being_released_shows_progress_and_keeps_asking():
    """The seat is released at the next hand boundary, up to a minute away. The
    card used to sit unchanged until the player reloaded by hand, so the wait
    was indistinguishable from a stuck page."""
    markup = Path("static/lobby.html").read_text(encoding="utf-8")
    script = Path("static/lobby.js").read_text(encoding="utf-8")
    css = Path("static/network.css").read_text(encoding="utf-8")

    assert 'id="leaveSpinner"' in markup
    assert ".session-spinner{" in css and "animation:session-spin" in css
    rule = css[css.index(".session-spinner{"):css.index("}", css.index(".session-spinner{"))]
    # An inline span ignores width and height: measured on the live page it came
    # out nought by nought, which is a spinner nobody can see.
    assert "display:inline-block" in rule, rule
    assert "width:" in rule and "height:" in rule
    assert ".session-spinner[hidden]{display:none}" in css, \
        "or the spinner outlives the wait, like every other hidden button here"

    watch = script[script.index("function watchLeaving()"):]
    watch = watch[:watch.index("function stopWatchingLeaving")]
    assert "/leave" in watch, "a lost leave request has to be re-sent"
    assert "setInterval" in watch
    assert "if (leaveWatch) return;" in watch, "one watcher, however often it renders"
