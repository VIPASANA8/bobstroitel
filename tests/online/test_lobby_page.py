from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.online import create_app
from online.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings.from_mapping({
        "POKER8_ENV": "development",
        "POKER8_DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'online.sqlite3'}",
        "POKER8_DEV_PROFILES": "101:Dev Player",
    })
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_root_serves_lobby_with_six_card_container(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="tableGrid"' in response.text
    assert 'id="quickPlay"' in response.text


def test_public_config_contains_branding_but_no_bot_token(client):
    payload = client.get("/api/config").json()
    assert payload["tenant"]["slug"] == "poker8"
    assert payload["network_brand"] == "Poker8"
    assert "token" not in str(payload).lower()


def test_lobby_join_has_http_safe_request_id_fallback():
    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "crypto.randomUUID?.()" in source


def test_table_transport_has_http_safe_request_id_fallback():
    source = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "const requestId = () => crypto.randomUUID?.()" in source
    assert "command_id = requestId()" in source


def test_lobby_cards_render_buy_in_from_unit_values():
    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "table.min_buy_in_units / table.big_blind_units" in source


def test_online_table_uses_existing_poker8_visual_dom():
    online_source = Path("static/online-table.js").read_text(encoding="utf-8")
    app_source = Path("static/app.js").read_text(encoding="utf-8")
    index_source = Path("static/index.html").read_text(encoding="utf-8")
    assert "window.Poker8LegacyView?.renderSnapshot" in online_source
    assert "onlineSurface" not in online_source
    assert "window.Poker8LegacyView" in app_source
    assert '/static/app.js?v=' in index_source
    assert '/static/online-table.js?v=' in index_source


def test_online_mobile_chat_does_not_cover_table_actions():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "mobileChatButton" in source
    assert "is-open" in source
    assert "if (chat) chat.hidden = false;" not in source

    assert ".poker8-online .online-chat-panel.is-open" in source


def test_online_table_does_not_repaint_legacy_view_for_same_snapshot():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "lastRenderKey" in source
    assert "if (key === lastRenderKey) return;" in source


def test_online_ready_panel_is_hidden_for_seated_users_and_duplicate_clicks():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert ".online-state-panel[hidden]" in source
    assert '["spectator", "waiting"].includes(viewerState)' in source
    assert "readyInFlight" in source


def test_online_waiting_prompt_reflects_the_viewers_own_ready_state():
    """A hand no longer starts purely on seat count -- every seated human
    must click ready first (online/coordinator.py's _may_start_hand). Neither
    ready state is said on the felt any more: "not ready" moved to the header
    (a real action, reachable from where the seat/observe pair lives), and
    "waiting on the others" says nothing at all, because there is nothing
    left for this viewer to do and the avatar's own checkmark already shows
    they clicked ready. Both used to be a card over the felt, covering the
    board and the pot, for a player who never stood up."""
    v038 = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    assert "ЖДЁМ ОСТАЛЬНЫХ" not in v038
    assert "НАЖМИТЕ НА АВАТАР" not in v038
    assert "МЕСТО ЗАНЯТО" not in v038
    assert "syncOnlineRoomPrompt" not in v038
    assert 'prompt?.classList.remove("visible");' in v038

    header = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "НАЖМИТЕ НА АВАТАР" in header
    assert "mobileHeaderReadyUp" in header


def test_online_ready_up_posts_to_the_server_not_the_local_event_bus():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "window.Poker8Transport.readyUp()" in source
    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "/ready-up" in transport


def test_online_ready_handler_does_not_bind_the_removed_room_prompt():
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    bindings = source[source.index("function bindControls() {"):]
    bindings = bindings[:bindings.index("// Delegated, like the hero avatar above")]
    assert ".v038-room-prompt" not in bindings


def test_online_mode_disables_legacy_ready_badges():
    index = Path("static/index.html").read_text(encoding="utf-8")
    source = Path("static/v024-ready-phase.js").read_text(encoding="utf-8")
    assert "window.Poker8OnlineTable" in index
    assert "isOnlineTable() || !preHand()" in source


def test_lobby_card_offers_a_way_to_watch_without_buying_in():
    """Every table card used to route through the buy-in dialog -- the only
    reason opening a table to just watch felt impossible even though the
    server has supported it all along (viewer_state: spectator)."""
    source = Path("static/lobby.js").read_text(encoding="utf-8")
    assert "data-observe-table" in source
    assert "openTable(button.dataset.observeTable)" in source


def test_online_table_header_shows_the_real_seat_state_not_a_stored_choice():
    """Both controls stay up the whole time the viewer has no seat, and the
    pair reads as "where you are now / what you can switch to" -- driven by the
    server's own answer. The old version highlighted a sessionStorage
    preference that could disagree with the actual state, and its "Наблюдатель"
    button did nothing beyond moving that highlight."""
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    assert "mobileHeaderTakeSeat" in source
    assert "mobileHeaderObserve" in source
    assert 'const offer = ["spectator", "waiting"].includes(viewerState);' in source
    # Derived from viewerState, never from a stored preference.
    assert "OBSERVE_MODE_KEY" not in source
    assert 'const queued = viewerState === "waiting";' in source
    assert 'take.textContent = queued ? "В очереди" : "Занять место";' in source
    assert "take.disabled = queued;" in source
    # Observing is now a real action while queued: it hands the seat back.
    assert "cancelQueue()" in source


def test_the_header_offers_ready_up_for_a_seated_player_with_nothing_dealt():
    """A third case shares the same header slot as the seat/observe pair --
    seated, but the current hand (if any) does not include this viewer, and
    they have not clicked ready. Mutually exclusive with the pair: one
    requires no seat, the other requires one, so the wrap stays open exactly
    when either has something to offer."""
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    # The seat number comes from the server (viewer_seat_no) rather than
    # being worked out here: viewer_state reads "seated" for a seat that is
    # only held -- which is what a reconnect, and every restart, leaves --
    # and the ready-up endpoint refuses those.
    assert 'const seatNo = viewerState === "seated" ? (state?.viewer_seat_no ?? viewerSeatedSeat) : null;' in source
    assert "isPreHand()" in source[source.index("function syncHeaderSeatButtons"):]
    assert "wrap.hidden = !offer && !awaitingReady;" in source
    assert 'readyButton.hidden = !awaitingReady;' in source
    assert "readyUp().catch(error => alert(error.message));" in source


def test_the_header_seat_buttons_cannot_overlap_the_chat_and_hint_buttons():
    """The pair used to be absolutely positioned at left:50% with a
    translate(-50%,-50%), so nothing in the header reserved its width. Both
    Russian labels together run ~198px, centring to x:88-286 on a 374px
    screen, while the right-hand utility group (two 42px buttons + 8px gap,
    inside v037's 13px padding) starts at x:269 -- the chat button painted
    over "Наблюдатель" and the hint button ran off the edge, as reported live.

    Staying in flow is what actually prevents it: the header is a flex row
    with justify-content:space-between (v037), so an in-flow group is laid
    out beside its siblings rather than on top of them, at any width.

    The rule was later split in two so desktop could reuse these same nodes
    in its own topbar (see test_desktop_header_actions): the phone-header
    layout (order, margin) stayed width-gated, the flex behaviour went
    global. Both halves are checked here -- the guarantee is unchanged, it
    just no longer lives in a single declaration block.
    """
    source = Path("static/online-table.js").read_text(encoding="utf-8")
    blocks = [
        source[m:source.index("}", m)]
        for m in [
            hit for hit in range(len(source))
            if source.startswith(".poker8-online .mobile-header-seat-actions{", hit)
        ]
    ]
    assert len(blocks) == 2, "expected the phone-layout and the global block"
    joined = "".join(blocks)
    # Never out of flow again, in either half.
    assert "position:absolute" not in joined
    assert "translate(-50%,-50%)" not in joined
    assert "display:flex" in joined
    # Ordered after the hamburger and before the utility group, which carries
    # order:2 -- otherwise flex would lay the three out in DOM append order.
    assert "order:1" in joined

    # Nowrap labels in a flex row overflow rather than wrap once the slack
    # (~16px at 374px) runs out, so they have to be allowed to shrink.
    button_rule = source[source.index(".poker8-online .mobile-header-seat-actions button{"):]
    button_rule = button_rule[:button_rule.index("}")]
    assert "min-width:0" in button_rule
    assert "text-overflow:ellipsis" in button_rule


def test_the_board_stays_up_online_between_hands():
    """`game` goes null between hands for everyone still at the table, not
    just whoever stood up -- clearing the board there wiped the hand that was
    just shown before anyone had a chance to look at it."""
    source = Path("static/app.js").read_text(encoding="utf-8")
    body = source[source.index("if (!game) {"):]
    body = body[:body.index('$("result").textContent = "Посадите людей')]
    assert 'if (!ONLINE_TABLE_ID) renderCards($("board"), []);' in body


def test_no_card_covers_the_felt_while_a_hand_is_running():
    """The prompt is for an idle table only. While a hand runs it sat over the
    board and the pot, and a player sitting that hand out reads their own state
    off the avatar instead -- the checkmark when ready, the pulse when not."""
    source = Path("static/v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    assert "ВЫ НАБЛЮДАЕТЕ" not in source
    # Online has no centre prompt in any state; the idle-room prompt remains
    # available to the local trainer only.
    assert 'prompt?.classList.remove("visible");' in source
    assert "sittingOut" not in source

    # v028 only marks "no hand at all", so the checkmark had nowhere to appear
    # while a hand ran without this seat.
    assert 'document.body.classList.toggle("p8-can-ready"' in source
    assert "body.v014.poker8-v2-sixmax.p8-can-ready .avatar-wrap.v038-viewer-ready .v038-ready-mark{display:grid;}" in source
    assert "body.v014.poker8-v2-sixmax.p8-can-ready .seat[data-visual-seat=\"0\"] .avatar-wrap:not(.v038-viewer-ready) .player-avatar" in source


def test_request_observe_dead_code_is_gone():
    """It was a pure alias for request_leave, and nothing ever called it --
    the client's own 'Наблюдать' needs no server round trip at all, since a
    seatless viewer is already a spectator."""
    seating = Path("online/seating.py").read_text(encoding="utf-8")
    assert "request_observe" not in seating
    router = Path("app/routers/tables.py").read_text(encoding="utf-8")
    assert '"/{table_id}/observe"' not in router
    transport = Path("static/online-transport.js").read_text(encoding="utf-8")
    assert "/observe" not in transport
