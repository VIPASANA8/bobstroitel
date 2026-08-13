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
    ready_source = (root / 'static' / 'v024-ready-phase.js').read_text(encoding='utf-8')
    app_source = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    polish_source = (root / 'static' / 'v033-poker8-v2-polish.js').read_text(encoding='utf-8')

    assert '/static/v038-poker8-v2-cinematic-table.js' in loader
    assert '/static/v037-poker8-v2-reference-table.js' in component_loader
    assert '/static/v033-poker8-v2-polish.js' not in component_loader
    assert '/static/v034-poker8-v2-layout-lock.js' not in component_loader
    assert 'data-v038-poker8-v2-cinematic-table' in loader
    assert (root / 'static' / 'assets' / 'poker8-v2-table-mobile.webp').exists()
    assert '@media (max-width:780px)' in source
    assert 'url("/static/assets/poker8-v2-table-mobile.webp")' in source
    assert '100vw calc(var(--table-stage-h) + 50px)' in source
    assert 'background-position:center -50px' in source
    assert 'background:transparent!important' in source
    assert '--profile-avatar-image' in source
    assert 'compactStackLabel' in source
    assert 'syncSeatStackLabels' in source
    assert 'syncTableNumberLabels' in source
    assert '.pot-total strong,.bet-marker span' in source
    assert 'Math.round(value).toLocaleString("en-US")' in source
    assert '.seat-card::after' in source
    assert '.pot-chips .poker-chip' in source
    assert 'calc(100dvh - 50px - var(--p8-hud-h) - var(--p8-bottom-reserve))' in source
    assert '--seat-3-y:13%' in source
    assert '[data-visual-seat="3"]{--seat-accent:142' in source
    assert '--seat-2-x:7%' in source and '--seat-4-x:93%' in source
    assert '--seat-1-y:58%' in source and '--seat-5-y:58%' in source
    assert '--seat-2-y:22%' in source and '--seat-4-y:22%' in source
    assert '--seat-0-y:80%' in source
    assert '--pot-y:25%' in source
    assert '--board-y:38%' in source and '--pot-chips-y:47%' in source
    assert 'width:74px!important;height:74px!important' in source
    assert '.seat-card:has(.player-cards:not(:empty)) .avatar-wrap::before' in source
    assert 'width:calc(100% - 44px)!important' in source
    assert 'box-sizing:border-box!important' in source
    assert '.player-avatar::before{' in source
    assert '.player-avatar::after{' in source
    assert '.player-avatar span{opacity:0!important' in source
    assert '.player-avatar[style*="--profile-avatar-image"]::before' in source
    assert 'overflow:visible!important' in source
    assert '.mobile-game-header{' in source and 'transparent 38%,transparent 62%' in source
    assert 'linear-gradient(150deg,#07110d 0%,#010303 100%)!important' in source
    assert '.pot-chips .chip-column:nth-child(3n+2) .poker-chip' in source
    assert 'background:transparent!important' in source
    assert '.seat-identity{' in source and 'position:absolute!important' in source
    assert '.seat-stack{margin-inline:auto!important' in source
    assert '.position-chip{display:none!important' in source
    assert '.seat-card > .v024-ready-badge{display:none!important' in source
    assert '.player-status:is(.status-fold,.status-turn,.status-thinking){display:none!important' in source
    assert '.v028-center-ready{display:none!important' in source
    assert 'v038-ready-mark' in source
    assert '.v028-prehand-center-ready .avatar-wrap.v038-viewer-ready .v038-ready-mark' in source
    assert 'poker8:ready-countdown' in source
    assert 'poker8:ready-snapshot' in source
    assert 'READY_COUNTDOWN_MS = 5000' in ready_source
    assert 'cancelViewerReadyCountdown' in ready_source
    assert 'toggleViewerReadyCountdown' in ready_source
    assert 'poker8:ready-countdown' in ready_source
    assert 'poker8:ready-snapshot' in ready_source
    assert 'transform:translateX(-50%) scale(.92)' in source
    assert '.seat-card.v032-active-turn' in source
    assert '.seat-card:is(.v032-in-hand,.v032-active-turn,.all-in)' in source
    assert 'outline:0!important' in source
    assert 'syncTurnIndicators' not in source
    assert '.deck-anchor{display:none!important' in source
    assert '.viewer-seat .player-cards{top:-29px!important' in source
    assert '.viewer-seat .player-cards .card-suit' in source
    assert '.player-cards .card:not(.back)' in source
    assert 'v038-ready-countdown' in source
    assert 'syncAllSeatReadyMarks' in source
    assert '.v038-turn-timer' in source
    assert '.v038-turn-context' in source
    assert 'syncTableTurnHud' in source
    assert 'TURN_VISUAL_MS = 30000' in source
    assert 'minimumFractionDigits: 0' in polish_source
    assert 'actor?.street_invested' in source
    assert 'window.clearInterval(turnVisualTicker)' in source
    assert 'actionDeadline = Date.now() + 30000' in app_source
    assert 'left / 30000 * 100' in app_source
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
    assert '.amount-row{display:none!important' in source
    assert 'min-height:39px!important;height:39px!important' in source
    assert 'linear-gradient(90deg,#21b8ff 0%,#7357ff 34%,#ff39cf 68%,#ffc83d 100%)' in source
    assert 'width:max-content;min-width:82px;max-width:116px' in source
    assert 'text-align:center' in source
    assert 'PRESET_SETTLE_MS = 1000' in source
    assert 'scheduleSettledPreset' in source
    assert 'stripHudUnit' in source
    assert '.seat-card::after{display:none!important' in source
    assert '.seat-card::before,' in source
    assert '.avatar-wrap::after{display:none!important;}' not in source
    assert 'syncSeatActionStates' in source
    assert all(token in source for token in ('v038-action-fold', 'v038-action-passive', 'v038-action-aggressive', 'v038-action-all-in'))
    assert '.seat-card.v032-active-turn .seat-identity' in source
    assert '@keyframes v038ActiveTurnPulse' in source
    assert 'left:calc(25% - 20.5px)' in source
    assert 'left:calc(75% + 20.5px)' in source
    assert 'invested > 0 ? `ПОСТАВИЛ · ${compactStackLabel(invested)}` : ""' in source
    assert 'latestActionText' not in source
    assert 'HAND_RESULT_HOLD_MS = 7000' in source
    assert 'roomResetHandId' in source
    assert 'game = null' in source
    assert 'v038-room-resetting' in source
    assert 'v038-room-prompt' in source
    assert '.v038-ready-countdown{\n        position:absolute;z-index:74;left:50%;top:calc(55% - 66px)' in source
    assert 'НОВАЯ РАЗДАЧА' in source
    assert 'Нажмите на свою аватарку' in source
    assert 'previousQueueAutomation' in source
    assert 'const host = document.querySelector(".table-frame")' in source
    assert '.v038-turn-context strong{display:block;color:#55fff2;font-size:11px' in source
    assert '.v038-turn-context span{display:block;margin-top:3px;color:#ecfffd;font-size:10px' in source
    assert "mark.innerHTML = '<b>✓</b>'" in source
    assert 'mark.querySelector("small")' not in source
