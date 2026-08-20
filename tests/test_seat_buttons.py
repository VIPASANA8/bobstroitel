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


def test_pressing_one_asks_the_server_for_that_seat_not_the_first_free_one():
    app = Path("static/app.js").read_text(encoding="utf-8")
    online = Path("static/online-table.js").read_text(encoding="utf-8")

    assert 'CustomEvent("poker8:take-seat"' in app
    assert 'window.addEventListener("poker8:take-seat"' in online
    assert "ready(event.detail?.seat" in online
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
    assert ".session-spinner[hidden]{display:none}" in css, \
        "or the spinner outlives the wait, like every other hidden button here"

    watch = script[script.index("function watchLeaving()"):]
    watch = watch[:watch.index("function stopWatchingLeaving")]
    assert "/leave" in watch, "a lost leave request has to be re-sent"
    assert "setInterval" in watch
    assert "if (leaveWatch) return;" in watch, "one watcher, however often it renders"
