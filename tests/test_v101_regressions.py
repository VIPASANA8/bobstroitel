import re
from pathlib import Path

from persistence.store import TrainingStore
from poker.engine import PokerEngine


def test_new_bot_on_reused_empty_seat_gets_fresh_id_and_deposit(tmp_path: Path):
    store = TrainingStore(tmp_path / 'db.sqlite3')
    first = store.add_bot(4, 'Первый', 'normal')
    first_id = first['id']
    store.set_balance(first_id, 0.0)
    store.clear_seat(4)

    second = store.add_bot(4, 'Второй', 'hard')
    assert second['id'] != first_id
    assert second['balance'] == store.INITIAL_BALANCE


def test_single_human_cards_can_be_revealed_during_bot_turn(tmp_path: Path):
    store = TrainingStore(tmp_path / 'db.sqlite3')
    store.add_bot(1, 'Бот', 'normal')
    engine = PokerEngine()
    state = engine.new_hand(store.active_seats(), button_seat=0)
    human = next(p for p in state.players.values() if not p.is_bot)
    bot = next(p for p in state.players.values() if p.is_bot)
    state.acting_player = bot.id
    payload = state.to_dict(viewer_player_id=human.id)
    assert payload['players'][human.id]['hole_cards'] != ['??', '??']
    assert payload['players'][bot.id]['hole_cards'] == ['??', '??']


def test_v037_reference_table_pass_is_loaded_and_chat_is_decorative():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v037-poker8-v2-reference-table.js').read_text(encoding='utf-8')
    loader = (root / 'static' / 'v036-poker8-v2-prehand-pass.js').read_text(encoding='utf-8')

    assert '/static/v037-poker8-v2-reference-table.js' in loader
    assert 'data-v037-poker8-v2-reference-table' in loader
    assert 'id = "mobileChatButton"' in source
    assert 'setAttribute("aria-label"' in source
    assert 'type = "button"' in source
    assert 'addEventListener("click"' not in source
    assert 'window.addEventListener("resize", start)' in source
    # The v2 table is the table at every width now -- this block used to be
    # @media (max-width:780px), which is what kept desktop on the old look
    # with none of the HUD. Asserting the old string would pass on the
    # comment that replaced it, so assert the rule that replaced it.
    assert '@media all{' in source


def test_v038_uses_full_height_arc_and_viewport_edge_controls():
    root = Path(__file__).resolve().parents[1]
    source = (root / "static" / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    index = (root / "static" / "index.html").read_text(encoding="utf-8")
    component = (root / "static" / "component-ui.js").read_text(encoding="utf-8")
    loader = (root / "static" / "v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")

    assert "--p8-seat-safe-inset:50px" in source
    assert "--p8-arc-radius:min(46vw,calc(50vw - var(--p8-seat-safe-inset)))" in source
    assert "--p8-arc-diagonal:calc(var(--p8-arc-radius) * .70710678)" in source
    assert '--p8-seat-angles:"180 135 90 45 0"' in source
    assert 'data-visual-seat="1"]{--v040-seat-x:calc(50% - var(--p8-arc-radius))' in source
    assert 'data-visual-seat="2"]{--v040-seat-x:calc(50% - var(--p8-arc-diagonal))' in source
    assert 'data-visual-seat="3"]{--v040-seat-x:50%' in source
    assert 'data-visual-seat="4"]{--v040-seat-x:calc(50% + var(--p8-arc-diagonal))' in source
    assert 'data-visual-seat="5"]{--v040-seat-x:calc(50% + var(--p8-arc-radius))' in source
    for count in range(2, 6):
        assert f"p8-player-count-{count} .seat[data-visual-seat=" in source
    assert "height:calc(100dvh - var(--p8-header-h))" in source
    assert ".action-panel" in source and "position:fixed!important" in source
    assert "background:transparent!important" in source
    assert "mobileConnectionDot" in source
    assert "mobileHelpButton" not in source
    assert 'hint.textContent = "?"' in loader
    assert "ЗАНЯТЬ МЕСТО" not in source
    assert '/static/component-ui.js?v=mobile-layout-prod-11' in index
    assert '/static/online-table.js?v=mobile-layout-prod-11' in index
    assert '/static/v037-poker8-v2-reference-table.js?v=mobile-layout-prod-11' in component
    assert '/static/v038-poker8-v2-cinematic-table.js?v=mobile-layout-prod-11' in loader


def test_v025_showdown_modal_is_readable_on_mobile():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v025-showdown-compare.js').read_text(encoding='utf-8')

    assert 'grid-template-columns:84px 75px minmax(0,1fr);' in source
    assert re.search(r'\.v025-who b\{display:block;margin-top:3px;overflow:hidden;'
                     r'text-overflow:ellipsis;white-space:nowrap;color:#[0-9a-f]{6};font-size:12px;', source)
    assert 'width:34px;' in source and 'height:46px;' in source
    assert re.search(r'\.v025-hand\{color:#[0-9a-f]{6};font-size:12px;', source)
    assert '.v025-reason{\n        margin-top:5px;' in source


def test_seat_config_carries_the_participant_id():
    """Between hands `game` is null and the server omits current_seats for
    anyone who played the last hand, so the seat list is the only place the
    viewer's id survives. Without it no seat is marked as the viewer's, the
    hero seat disappears and the table rotates into spectator layout with an
    avatar nobody can click."""
    root = Path(__file__).resolve().parents[1]
    app_source = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    assert 'id: player?.id || null,' in app_source
    component_source = (root / 'static' / 'component-ui.js').read_text(encoding='utf-8')
    # The layout anchor must resolve the viewer by id before it falls back to
    # "first human seat", which is somebody else's seat.
    assert "seat?.id === viewerId" in component_source


def test_v038_preserves_gameplay_contracts_while_replacing_the_mobile_layout():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v038-poker8-v2-cinematic-table.js').read_text(encoding='utf-8')
    ready = (root / 'static' / 'v024-ready-phase.js').read_text(encoding='utf-8')
    wager = (root / 'static' / 'v031-pot-cluster-mobile-fix.js').read_text(encoding='utf-8')
    app = (root / 'static' / 'app.js').read_text(encoding='utf-8')

    for token in (
        'compactStackLabel', 'syncSeatStackLabels', 'syncTableNumberLabels',
        'syncAvatarReadyControl', 'syncAllSeatReadyMarks', 'syncSeatActionStates',
        'syncCompletedHandReset', 'v038-room-prompt', 'v038-ready-countdown',
        'v038-action-fold', 'v038-action-passive', 'v038-action-aggressive',
        'v038-action-all-in', '.seat-card.v032-folded', '.seat-card.all-in',
        '--profile-avatar-image', 'previousQueueAutomation', 'runSyncStep',
        'mobileActionDefinitions', 'openSizingMode', 'confirmSizingMode',
        'beginVerticalBetGesture',
    ):
        assert token in source
    assert 'READY_COUNTDOWN_MS = 5000' in ready
    assert 'poker8:ready-countdown' in ready and 'poker8:ready-snapshot' in ready
    assert 'if (mobile && visualSeat === 0)' in wager
    assert 'x: from.x + 66' in wager and 'y: from.y - 30' in wager
    assert 'const arcLift = Math.min(18, Math.max(10, Math.abs(dx) * .08 + Math.abs(dy) * .04));' in app
    assert '${dy * .52 - arcLift}px' in app


def test_v039_desktop_seat_positions_also_resolve_for_a_spectator():
    # Same bug as v038's hexagon placement, on the desktop parity layer:
    # an exact ="N" match on data-visual-seat leaves a spectator's
    # "spectator-N" dataset (v040) with no left/top at all.
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v039-poker8-v2-desktop-parity.js').read_text(encoding='utf-8')
    for n in range(7):
        assert f'[data-visual-seat$="{n}"]{{left:var(--seat-{n}-x)' in source
        assert f'[data-visual-seat="{n}"]{{left:var(--seat-{n}-x)' not in source


def test_no_layer_writes_a_turn_label_onto_the_seat():
    """The acting seat is shown by its own gradient, pulsing plate and avatar
    glow. Three layers had each added their own "ХОД" caption on top of that at
    some point; the last one lived in v041 as a ::after on the seat name."""
    root = Path(__file__).resolve().parents[1]
    for name in (
        'app.js',
        'v038-poker8-v2-cinematic-table.js',
        'v040-poker8-v2-dynamic-seats.js',
        'v041-poker8-v2-turn-clarity.js',
    ):
        source = (root / 'static' / name).read_text(encoding='utf-8')
        assert 'content:"ХОД"' not in source, name
        assert "content:'ХОД'" not in source, name

    v041 = (root / 'static' / 'v041-poker8-v2-turn-clarity.js').read_text(encoding='utf-8')
    assert '.seat-name::after' not in v041
    # The highlight itself must stay -- it is now the only turn indicator.
    assert 'p8-turn-gradient' in v041
    # Was `v041PlatePulse`. The pulse is gone: it rode on elements that get
    # rebuilt every render, so it restarted from frame zero and jumped.
    # The steady ring is the indicator.
    assert 'border-color:var(--turn)!important' in v041


def test_idle_seat_decoration_never_shows_during_a_hand():
    """The two card backs behind an avatar are decoration for an idle table. A
    seat sitting a hand out has no real cards to replace them, so they told the
    player they held cards while the prompt said the hand was running without
    them -- and component-ui dressed that same seat with a second, wrong dealer
    button next to the real one."""
    root = Path(__file__).resolve().parents[1]
    v038 = (root / 'static' / 'v038-poker8-v2-cinematic-table.js').read_text(encoding='utf-8')
    assert 'body.v014.poker8-v2-sixmax:not(.p8-no-pot) .avatar-wrap::before' in v038

    component = (root / 'static' / 'component-ui.js').read_text(encoding='utf-8')
    assert 'const liveHand = Boolean(game && !game.terminal);' in component
    assert 'if (genericPosition && !liveHand) {' in component


def test_all_in_is_spelled_one_way_and_replaces_the_empty_stack():
    """An all-in player's stack reads 0, which says nothing. The seat shows the
    state there instead, and every layer spells it the same."""
    root = Path(__file__).resolve().parents[1]
    for name in ('app.js', 'v016-fixes.js', 'v038-poker8-v2-cinematic-table.js'):
        source = (root / 'static' / name).read_text(encoding='utf-8')
        assert 'ОЛЛ-ИН' not in source, name
        assert 'Олл-ин' not in source, name
        assert '"ALL IN"' not in source, name

    app_source = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    assert '${allIn ? "ALL-IN" : formatBB(stack)}' in app_source
