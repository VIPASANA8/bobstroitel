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


V039 = Path("static/v039-poker8-v2-desktop-parity.js").read_text(encoding="utf-8")


def test_the_ring_on_the_avatar_is_not_a_phone_only_idea():
    """It was written inside @media (max-width:780px), so desktop fell back to
    the fixed 62px disc: smaller than the avatar once the seat's scale reached
    it, with the number in the middle rather than on the rim."""
    # The first mention is prose in the file header; the block itself is
    # the indented one that opens a brace.
    head = V038[:V038.index("      @media (max-width:780px){")]
    assert ".avatar-wrap>:is(.v038-turn-timer,.v038-ready-countdown){" in head
    # And no second helping of the seat's own scale on top of it.
    assert "poker8-desktop-v2 .v038-ready-countdown" not in V039


def test_desktop_draws_everyone_elses_readiness_too():
    """The hero's tick reaches desktop only because setReadyCountdown calls
    syncAvatarReadyControl; nothing called the pass that marks the other
    seats, so only your own confirmation was ever visible there."""
    desktop = V038[V038.index('if (document.body.classList.contains("poker8-desktop-v2")) {'):]
    desktop = desktop[:desktop.index("      return;")]
    assert "runSyncStep(syncAllSeatReadyMarks);" in desktop


def test_the_deck_has_one_back():
    """It took --seat-accent, so a face-down card changed hue with what the
    seat was doing, and desktop drew a second variant off --avatar-hue. A back
    carries nothing about the seat holding it -- it is the deck."""
    back = V038[V038.index(".player-cards .card.back{"):]
    back = back[:back.index("}")]
    assert "--seat-accent" not in back and "--avatar-hue" not in back
    assert "linear-gradient(150deg,#0B2020,#071A1A)" in back
    assert "rgba(22,207,160,.22)" in back
    assert ".player-cards .card.back{" not in V039


def test_the_desktop_header_stays_one_row():
    """style.css:502 lets .top-actions wrap. Free until the reservation strip
    took 300px out of the same line; then the controls spilled onto a second
    row and the bar stood twice as tall."""
    rule = V039[V039.index("body.v014.poker8-desktop-v2 .top-actions{"):]
    rule = rule[:rule.index("}")]
    assert "flex-wrap:nowrap!important" in rule
    assert "body.v014.poker8-desktop-v2 .top-actions > *{flex:0 0 auto!important;}" in V039


def test_desktop_colours_the_seats_by_what_they_did():
    """The v038-action-* colours were never width-gated; desktop just had
    nothing putting the classes on, so every seat stayed resting green whether
    it had folded, called or shoved."""
    desktop = V038[V038.index('if (document.body.classList.contains("poker8-desktop-v2")) {'):]
    desktop = desktop[:desktop.index("      return;")]
    assert "runSyncStep(syncSeatActionStates);" in desktop
    head = V038[:V038.index("      @media (max-width:780px){")]
    assert ".seat-card.v038-action-fold .player-avatar{" in head


def test_the_phone_ring_has_one_source():
    """Two seats were pulled off v038's arc here in percentages, so the ring's
    right half sat 9% below its left -- and which half won came down to the
    order the stylesheets happened to land in."""
    assert 'seat[data-visual-seat="5"]{left:' not in V039
    assert 'seat[data-visual-seat="4"]{left:' not in V039


COMPONENT_CSS = Path("static/component-ui.css").read_text(encoding="utf-8")


def test_the_ring_measures_against_the_whole_countdown():
    """Both halves of the fraction were measured from now on every call, and
    the event fires on every snapshot -- so the ring stood at 100% for the
    whole count while the number beside it counted down correctly."""
    body = V038[V038.index("function setReadyCountdown(endsAt) {"):]
    body = body[:body.index("let referenceActive")]
    assert "if (next !== readyCountdownEndsAt) {" in body
    assert body.count("readyCountdownDuration = Math.max(1,") == 1


def test_the_win_loss_card_is_not_phone_only():
    """The JS that builds it always ran at every width; the rules for it sat
    inside @media (max-width:780px), so on desktop it was an unstyled div
    appended to <body>."""
    showdown = COMPONENT_CSS[COMPONENT_CSS.index("/* Showdown comparison;"):]
    phone = showdown[showdown.index("@media (max-width:780px){"):]
    phone = phone[:phone.index("\n    }\n")]
    assert ".v025-showdown-modal" not in phone
    assert "v025-showdown-layout" in phone, "the seat lane really is phone-only"
    assert "\n    .v025-showdown-modal{" in showdown


def test_the_made_hands_board_card_survives_the_desktop_repaint():
    """v038's amber and v039's mint tie on specificity -- five classes each --
    and v039 re-appends itself to the end of <head>, so on desktop the mint won
    and the card the hand is made of looked like every other one."""
    mint = V039.index("poker8-desktop-v2 .board-cards .card{border-color:rgba(98,255,170")
    amber = V039.index("poker8-desktop-v2 .board-cards .card.hand-combo{")
    assert amber > mint, "the highlight has to be restated after what overwrote it"
    assert "border-color:#f1c867!important" in V039


def test_the_seat_pair_sits_with_the_room_on_desktop():
    """At the far end of a wide bar, "Нажмите на аватар" was a caption with
    nothing near it."""
    online = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "bar.insertBefore(seatGroup, topActions);" in online
    rule = V039[V039.index(".topbar > .mobile-header-seat-actions{"):]
    assert "margin-right:auto!important" in rule[:rule.index("}")]


def test_the_lobby_balance_is_a_number_with_the_profile_chip_after_it():
    """"PLAY" is the only currency there is, so printing it beside the number
    said nothing -- and the balance was the last thing in the bar, pinned to
    the edge. The chip takes that end and pushes the number in."""
    lobby = Path("static/lobby.html").read_text(encoding="utf-8")
    css = Path("static/network.css").read_text(encoding="utf-8")
    js = Path("static/lobby.js").read_text(encoding="utf-8")
    assert 'class="profile-chip"' in lobby
    assert lobby.index('id="wallet"') < lobby.index('class="profile-chip"'), "chip goes last"
    assert "PLAY" not in js
    assert ".profile-chip{" in css and "border-radius:50%" in css


V040 = Path("static/v040-poker8-v2-dynamic-seats.js").read_text(encoding="utf-8")
GUIDE = Path("static/table-guide.js").read_text(encoding="utf-8")
CHAT = Path("online/chat.py").read_text(encoding="utf-8")


def test_the_pot_pile_does_not_outlive_the_width_it_was_measured_at():
    """syncPotChipStack pins #potChips with an inline top in px at !important,
    which outranks even v039's `top:auto!important` -- so a desktop window that
    had ever been narrow kept the phone's measurement and dropped the pile onto
    the board, under the plate it is supposed to sit above."""
    teardown = V038[V038.index("function teardownFinalReference()"):]
    teardown = teardown[:teardown.index("\n  function ")]
    assert 'getElementById("potChips")?.style.removeProperty("top")' in teardown


def test_the_guide_gets_a_desktop_width_and_sections_that_divide():
    assert "width:min(92vw,720px)" in GUIDE, "380px is a phone's panel"
    section = GUIDE[GUIDE.index(".hand-rankings-modal .hr-section{"):]
    section = section[:section.index("}")]
    assert "border-top:" in section and "padding-top:" in section


def test_chat_forgets_an_hour_old_line():
    assert "CHAT_TTL = timedelta(minutes=60)" in CHAT
    # Hidden on read, so the cutoff holds whether or not anything swept it...
    assert "chat_messages.c.created_at >= self._datetime(None) - CHAT_TTL" in CHAT
    # ...and removed on write, so the table does not keep what nobody can read.
    assert "chat_messages.delete().where(" in CHAT
    assert "chat_messages.c.created_at < current - CHAT_TTL," in CHAT
