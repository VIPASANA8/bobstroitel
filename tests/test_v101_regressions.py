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
    assert '@media (max-width:780px)' in source


def test_v038_uses_full_height_arc_and_viewport_edge_controls():
    root = Path(__file__).resolve().parents[1]
    source = (root / "static" / "v038-poker8-v2-cinematic-table.js").read_text(encoding="utf-8")
    index = (root / "static" / "index.html").read_text(encoding="utf-8")
    component = (root / "static" / "component-ui.js").read_text(encoding="utf-8")
    loader = (root / "static" / "v037-poker8-v2-reference-table.js").read_text(encoding="utf-8")

    assert "--p8-arc-radius:calc(46vw)" in source
    assert "--p8-arc-diagonal:calc(var(--p8-arc-radius) * .70710678)" in source
    assert '--p8-seat-angles:"180 135 90 45 0"' in source
    assert 'data-visual-seat="1"]{left:calc(50% - var(--p8-arc-radius))' in source
    assert 'data-visual-seat="2"]{left:calc(50% - var(--p8-arc-diagonal))' in source
    assert 'data-visual-seat="3"]{left:50%' in source
    assert 'data-visual-seat="4"]{left:calc(50% + var(--p8-arc-diagonal))' in source
    assert 'data-visual-seat="5"]{left:calc(50% + var(--p8-arc-radius))' in source
    assert "height:calc(100dvh - var(--p8-header-h))" in source
    assert ".action-panel" in source and "position:fixed!important" in source
    assert "background:transparent!important" in source
    assert "mobileConnectionDot" in source
    assert "mobileHelpButton" in source
    assert "ЗАНЯТЬ МЕСТО" not in source
    assert '/static/component-ui.js?v=edge-actions-1' in index
    assert '/static/v037-poker8-v2-reference-table.js?v=edge-actions-1' in component
    assert '/static/v038-poker8-v2-cinematic-table.js?v=edge-actions-1' in loader


def test_v025_showdown_modal_is_readable_on_mobile():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v025-showdown-compare.js').read_text(encoding='utf-8')

    assert 'grid-template-columns:84px 75px minmax(0,1fr);' in source
    assert '.v025-who b{display:block;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#eef5ff;font-size:12px;' in source
    assert 'width:34px;' in source and 'height:46px;' in source
    assert '.v025-hand{color:#dbe6f5;font-size:11px;' in source
    assert '.v025-reason{\n        margin-top:5px;' in source


def test_v038_preserves_existing_game_state_and_animation_contracts():
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
        '--profile-avatar-image', 'previousQueueAutomation',
    ):
        assert token in source
    assert 'READY_COUNTDOWN_MS = 5000' in ready
    assert 'poker8:ready-countdown' in ready and 'poker8:ready-snapshot' in ready
    assert 'if (mobile && visualSeat === 0)' in wager
    assert 'x: from.x + 66' in wager and 'y: from.y - 30' in wager
    assert 'const arcLift = Math.min(18, Math.max(10, Math.abs(dx) * .08 + Math.abs(dy) * .04));' in app
    assert '${dy * .52 - arcLift}px' in app
    assert 'actionDeadline = Date.now() + 30000' in app
