"""Four things that surfaced in the UI after the last round of merges.

The middle two share a root cause: only the REST route ever stamped
`viewer_seat_no`, and the websocket snapshot is what actually drives a live
table. Between hands `game` is null, so the seat number is the only thing
tying a chair to the viewer -- without it v040 found no hero, rotated the
table into spectator layout, offered the "Сесть" button over the seat the
viewer was already sitting in, and left the ready countdown with no avatar
to ring, so it landed in the middle of the felt on top of the board.
"""

from pathlib import Path

ONLINE = Path("static/online-table.js").read_text(encoding="utf-8")
V038 = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
V037 = Path("static/v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")


def test_a_pending_action_dims_the_buttons_without_narrating_itself():
    assert "Отправляем действие" not in ONLINE
    assert ".poker8-online.p8-action-pending #actionButtons{opacity:.62" in ONLINE


def test_every_snapshot_carries_the_viewers_seat_number():
    """Not just the REST one -- the socket delivers all the rest."""
    assert "state.viewer_seat_no = viewerSeatNo(state) ?? viewerSeatedSeat;" in ONLINE
    # A seat the viewer no longer holds is somebody else's now.
    assert "if (state && state.viewer_seat_no == null && state.viewer_player_id) {" in ONLINE


def test_the_ready_ring_has_no_home_but_the_hero_avatar():
    """The felt fallback drew a 62px countdown over the board for anyone with
    no seat of their own to ring."""
    body = V038[V038.index("function ensureReadyCountdown()"):]
    body = body[:body.index("function setReadyCountdown(")]
    assert "const host = document.querySelector('.seat[data-visual-seat=\"0\"] .avatar-wrap');" in body
    assert ".felt" not in body
    assert "countdown?.remove();" in body


def test_the_header_icons_are_all_one_size():
    assert "width:42px;height:42px" in V037.replace(" ", "")  # .mobile-hint-button
    assert (
        "body.v014.poker8-v2-sixmax :is(.mobile-menu-button,.mobile-chat-button){\n"
        "        width:42px!important;height:42px!important;"
        "min-width:42px!important;min-height:42px!important;border-radius:12px!important;"
    ) in V038
