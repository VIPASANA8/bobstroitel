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
    # Regression assertion for the public-state capability used by v0.10.1:
    # a chosen viewer keeps their own cards visible even when another player acts.
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


def test_v038_cinematic_table_is_mobile_presentation_only():
    root = Path(__file__).resolve().parents[1]
    loader = (root / 'static' / 'v037-poker8-v2-reference-table.js').read_text(encoding='utf-8')
    component_loader = (root / 'static' / 'component-ui.js').read_text(encoding='utf-8')
    source = (root / 'static' / 'v038-poker8-v2-cinematic-table.js').read_text(encoding='utf-8')

    assert '/static/v038-poker8-v2-cinematic-table.js' in loader
    assert '/static/v037-poker8-v2-reference-table.js' in component_loader
    assert '/static/v033-poker8-v2-polish.js' not in component_loader
    assert '/static/v034-poker8-v2-layout-lock.js' not in component_loader
    assert 'data-v038-poker8-v2-cinematic-table' in loader
    assert '@media (max-width:780px)' in source
    assert '--profile-avatar-image' in source
    assert '.seat-card::after' in source
    assert '.pot-chips .poker-chip' in source
    assert 'calc(100dvh - 50px - var(--p8-hud-h) - var(--p8-bottom-reserve))' in source
    assert '--seat-3-y:11%' in source
    assert '[data-visual-seat="3"]{--seat-accent:142' in source
    assert '--seat-2-x:14%' in source and '--seat-4-x:86%' in source
    assert '--seat-1-y:64%' in source and '--seat-5-y:64%' in source
    assert '--seat-2-y:24%' in source and '--seat-4-y:24%' in source
    assert '--seat-0-y:86%' in source
    assert '--pot-y:22%' in source
    assert '--board-y:40%' in source and '--pot-chips-y:55%' in source
    assert 'width:74px!important;height:74px!important' in source
    assert '.seat-card:has(.player-cards:not(:empty)) .avatar-wrap::before' in source
    assert 'width:calc(100% - 44px)!important' in source
    assert 'box-sizing:border-box!important' in source
    assert 'border-width:18px!important' in source
    assert '#001c10' in source
    assert 'inset 0 0 118px rgba(0,0,0,.68)' in source
    assert 'background:transparent!important' in source
    assert '.seat-identity{' in source and 'position:absolute!important' in source
    assert '.position-chip{display:none!important' in source
    assert '.seat-card > .v024-ready-badge.v026-seat-status{display:none!important' in source
    assert '.player-status.status-fold{display:none!important' in source
    assert 'transform:translateX(-50%) scale(.92)' in source
    assert '.seat-card.v032-active-turn' in source
    assert '.seat-card.v032-folded' in source
    assert '.seat-card.all-in' in source
    assert 'calc(100dvh - 250px)' not in source
    assert '--p8-perspective:900px' in source
    assert 'rotateX(5deg)' in source
    assert '--p8-bottom-reserve:46px' in source
    assert 'grid-template-columns:repeat(5,1fr)' in source
    assert '--p8-hud-h:214px' in source
    assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in source
    assert 'grid-template-rows:repeat(2,44px)' in source
    assert '.sidebar{transform:none' in source
    assert 'position:absolute!important' in source
    assert 'bottom:4px!important' in source
    assert 'position:fixed!important' not in source
    assert '.action-slot.all-in{display:none' not in source
    assert '.v038-hud-summary{' in source and 'top:4px!important' in source
    assert 'configureReferenceActions' in source
    assert 'window.addEventListener("resize", queueSync)' in source
    assert '{ key:"call"' in source
    assert '{ key:"all_in"' in source
    assert '{ key:leftKey' in source
    assert '{ key:"aggressive"' in source
    assert 'ALL_IN_CONFIRM_MS = 3000' in source
    assert '? "CONFIRM"' in source
    assert 'v038-all-in-armed' in source
    assert 'v038-size-selected' in source
    assert '.quick-sizes button.v038-max-size{' in source
    assert '#ff3bd5' in source
    assert 'transition:color 180ms' in source
    assert '@media (prefers-reduced-motion:reduce)' in source
    assert 'teardownFinalReference' in source
    assert 'estimatedLocalToCall()' in source
    assert 'rotate:x -5deg' in source
    assert 'fetch(' not in source
    assert 'data-v038-all-in-trigger' in source
    assert 'source === "aggressive"' in source
    assert 'togglePendingAction("aggressive")' in source
    assert 'pendingAction?.kind === def.key' in source
