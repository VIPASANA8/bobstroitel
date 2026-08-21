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
    # The v2 table is the table at every width now -- this block used to be
    # @media (max-width:780px), which is what kept desktop on the old look
    # with none of the HUD. Asserting the old string would pass on the
    # comment that replaced it, so assert the rule that replaced it.
    assert '@media all{' in source


def test_v025_showdown_modal_is_readable_on_mobile():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'static' / 'v025-showdown-compare.js').read_text(encoding='utf-8')

    assert 'grid-template-columns:84px 75px minmax(0,1fr);' in source
    assert '.v025-who b{display:block;margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#eef5ff;font-size:12px;' in source
    assert 'width:34px;' in source and 'height:46px;' in source
    assert '.v025-hand{color:#dbe6f5;font-size:12px;' in source
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


def test_v038_cinematic_table_is_mobile_presentation_only():
    root = Path(__file__).resolve().parents[1]
    loader = (root / 'static' / 'v037-poker8-v2-reference-table.js').read_text(encoding='utf-8')
    component_loader = (root / 'static' / 'component-ui.js').read_text(encoding='utf-8')
    source = (root / 'static' / 'v038-poker8-v2-cinematic-table.js').read_text(encoding='utf-8')
    ready_source = (root / 'static' / 'v024-ready-phase.js').read_text(encoding='utf-8')
    app_source = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    wager_source = (root / 'static' / 'v031-pot-cluster-mobile-fix.js').read_text(encoding='utf-8')
    wager_loader = (root / 'static' / 'v030-seat-ready-fix.js').read_text(encoding='utf-8')
    index_source = (root / 'static' / 'index.html').read_text(encoding='utf-8')

    assert '/static/v038-poker8-v2-cinematic-table.js?v=' in loader
    assert '/static/v037-poker8-v2-reference-table.js?v=' in component_loader
    # v033 and v034 were dead -- nothing loaded them, and these two lines were
    # the only thing keeping 280 lines of them alive. They are gone. The
    # invariant worth having is the other way round: every layer a loader names
    # has to exist, or the chain breaks silently at a 404 halfway through.
    named = set()
    for js in (root / 'static').glob('*.js'):
        named.update(re.findall(r'/static/(v\d+-[a-z0-9-]+\.js)', js.read_text(encoding='utf-8')))
    missing = sorted(name for name in named if not (root / 'static' / name).exists())
    assert missing == [], missing
    assert 'data-v038-poker8-v2-cinematic-table' in loader
    assert (root / 'static' / 'assets' / 'poker8-v2-table-mobile.webp').exists()
    assert '@media (max-width:780px)' in source
    assert 'url("/static/assets/poker8-v2-table-mobile.webp")' in source
    assert '100vw calc(var(--table-stage-h) + 50px)' in source
    assert 'background-position:center,center -50px' in source
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
    # The stage calc above only reserves the action panel's space; it does not
    # stop .layout/.left-column inheriting a full-viewport height from
    # style.css. Without this override the left column alone fills .app-shell,
    # so the sidebar holding the action buttons is laid out past the bottom of
    # an overflow:hidden shell -- the buttons render but are off-screen and
    # unreachable, which reads as "the action buttons never appear".
    assert 'body.v014.poker8-v2-sixmax .layout,' in source
    assert 'min-height:0!important;height:auto!important;flex:none!important;' in source
    assert '--seat-3-y:13%' in source
    # $= (suffix match), not =, so a spectator's "spectator-N" dataset still
    # resolves an accent color instead of leaving every avatar unstyled.
    assert '[data-visual-seat$="3"]{--seat-accent:142' in source
    assert '--seat-2-x:7%' in source and '--seat-4-x:84%' in source
    assert '--seat-1-y:58%' in source and '--seat-5-y:58%' in source
    assert '--seat-2-y:22%' in source and '--seat-4-y:22%' in source
    assert '--seat-0-y:80%' in source
    assert '--pot-y:25%' in source
    assert '--board-y:38%' in source and '--pot-chips-y:47%' in source
    # Every seat's avatar is the same size now (item 6: 1.5x smaller than the
    # old 74px; item 5: the hero seat no longer overrides it to 82px).
    assert 'width:49px!important;height:49px!important' in source
    assert '.seat-card:has(.player-cards:not(:empty)) .avatar-wrap::before' in source
    assert 'width:calc(100% - 44px)!important' in source
    assert 'box-sizing:border-box!important' in source
    assert '.felt::after{display:none!important;}' in source
    assert '.player-avatar::before{' in source
    assert '.player-avatar::after{' in source
    assert 'clip-path:polygon(50% 0,84% 16%,100% 72%,76% 92%,63% 68%,50% 61%,37% 68%,24% 92%,0 72%,16% 16%);' in source
    assert 'width:34px!important;height:48px!important;border-radius:5px!important;' in source
    assert 'width:45px!important;height:63px!important;' in source
    assert 'font-size:20px!important;line-height:1!important;' in source
    assert 'width:22px!important;height:9px!important;border-width:1px!important;' in source
    assert '.player-avatar span{opacity:0!important' in source
    assert '.player-avatar[style*="--profile-avatar-image"]::before' in source
    assert 'overflow:visible!important' in source
    assert '.mobile-game-header{' in source and 'transparent 38%,transparent 62%' in source
    assert 'linear-gradient(150deg,#07110d 0%,#010303 100%)!important' in source
    # Dropped: it hue-shifted every 3rd column regardless of which denomination
    # it held, scrambling the real chip colours chipsForAmount already sets.
    assert '.pot-chips .chip-column:nth-child(3n+2) .poker-chip' not in source
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
    assert '.viewer-seat .player-cards{top:-47px!important' in source
    # The hero's identity plate no longer overrides width/position -- it now
    # matches every other seat's plate, same as the avatar (item 5 uniformity).
    assert 'seat[data-visual-seat="0"] .seat-identity' not in source
    assert '.viewer-seat .player-cards .card-suit' in source
    assert '.player-cards .card:not(.back)' in source
    assert 'v038-ready-countdown' in source
    assert 'syncAllSeatReadyMarks' in source
    assert '.v038-turn-timer' in source
    assert '.v038-turn-context' in source
    assert 'syncTableTurnHud' in source
    assert 'TURN_VISUAL_MS = 30000' in source
    assert 'actor?.street_invested' in source
    assert 'window.clearInterval(turnVisualTicker)' in source
    # The clock follows the server deadline and only falls back to a fixed 30 s
    # for local hands, which carry no deadline.
    assert 'game?.action_deadline ? Date.parse(game.action_deadline) : NaN' in app_source
    assert 'Date.now() + 30000 : serverDeadline' in app_source
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
    assert 'COMMIT_CONFIRM_MS = 3000' in source
    # The label is the remaining seconds now, in both motion modes -- the
    # window shortens when the turn clock would land first, so a fixed
    # "3 SEC" would have been a promise the button could not keep.
    assert 'content:attr(data-arm-label)' in source
    assert 'animation:v038ConfirmDrain var(--v038-arm-ms,3000ms)' in source
    assert 'v038-armed' in source
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
    # Off turn every armable slot becomes a pre-action, fold included, so the
    # branch just passes the source straight through.
    assert "togglePendingAction(source);" in source
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
    assert '.seat .seat-card.v032-in-hand:not(.v032-active-turn){\n        border:0!important;background:transparent!important;box-shadow:none!important;outline:0!important;' in source
    # The size moved onto the type scale (see test_type_scale); what this
    # line is really pinning is the plate the wager sits on.
    assert '.bet-marker span{' in source
    assert 'background:rgba(1,7,6,.84)!important' in source
    assert 'left:calc(25% - 20.5px)' in source
    assert 'left:calc(75% + 20.5px)' in source
    assert 'invested > 0 ? `ПОСТАВИЛ · ${compactStackLabel(invested)}` : ""' in source
    assert 'latestActionText' not in source
    assert 'HAND_RESULT_HOLD_MS = 7000' in source
    assert 'roomResetHandId' in source
    assert 'document.body.classList.toggle("v038-hand-complete", Boolean(game?.terminal));' in source
    assert 'body.v014.poker8-v2-sixmax.v038-hand-complete .player-cards{opacity:0!important;transform:translateX(-50%) translateY(-12px) scale(.92)!important;}' in source
    assert 'game = null' in source
    assert 'v038-room-resetting' in source
    assert 'body.v014.poker8-v2-sixmax.v038-room-resetting .player-cards{opacity:0!important;transform:translateX(-50%) translateY(-12px) scale(.92)!important;}' in source
    assert 'body.v014.poker8-v2-sixmax.v038-room-awaiting .avatar-wrap::before' in source
    assert 'body.v014.poker8-v2-sixmax.v038-room-awaiting .avatar-wrap::after' in source
    assert 'body.v014.poker8-v2-sixmax.v038-room-resetting .avatar-wrap::before' in source
    assert 'body.v014.poker8-v2-sixmax.v038-hand-complete .avatar-wrap::after' in source
    assert 'opacity:0!important;' in source
    assert 'v038-room-prompt' in source
    # The ring hangs off the same variable as the label it sits above, so
    # a five or six handed layout moves both together -- pinned apart
    # they overlapped. See test_chip_stacks.
    assert 'top:calc(var(--p8-prompt-y, 36%) - 64px)' in source
    assert 'НОВАЯ РАЗДАЧА' in source
    assert 'Нажмите на свою аватарку' in source
    assert 'previousQueueAutomation' in source
    assert 'const host = document.querySelector(".table-frame")' in source
    # "ХОД · name" was dropped -- the seat's own glow already shows whose turn
    # it is, so this box now only ever shows the street's bet amount.
    assert "ХОД ·" not in source
    assert '.v038-turn-context span{display:block;color:#ecfffd;font-size:10px' in source
    assert "mark.innerHTML = '<b>✓</b>'" in source
    assert 'mark.querySelector("small")' not in source
    assert "closest?.('.seat[data-visual-seat=\"0\"], .v038-room-prompt')" in source
    assert 'pointer-events:auto;cursor:pointer;' in source
    assert 'if (mobile && visualSeat === 0)' in wager_source
    assert 'x: from.x + 66' in wager_source
    assert 'y: from.y - 30' in wager_source
    assert 'v031.src = "/static/v031-pot-cluster-mobile-fix.js?v=' in wager_loader
    # A wager used to fan out into two, three or four stacks by size. It is
    # one stack now whatever it is worth, with the height carrying the amount
    # -- see test_chip_stacks. The pot still widens with the money.
    assert 'if (compact) return 1;' in app_source
    assert 'if (n < 12) return 2;' in app_source
    assert 'if (n < 120) return 4;' in app_source
    assert 'const arcLift = Math.min(18, Math.max(10, Math.abs(dx) * .08 + Math.abs(dy) * .04));' in app_source
    assert '${dy * .52 - arcLift}px' in app_source
    assert 'filter: "brightness(1.28) drop-shadow(0 7px 8px rgba(0,0,0,.42))"' in app_source
    assert 'offset: .86' in app_source
    assert 'radial-gradient(ellipse at 50% 18%,rgba(255,255,255,.36),transparent 48%)' in (root / 'static' / 'style.css').read_text(encoding='utf-8')
    # The version has to be there and has to move when the file does, so
    # pinning which one it is would break on every stylesheet edit --
    # which is exactly what the version exists to survive.
    assert '/static/style.css?v=' in index_source
    assert '/static/app.js?v=' in index_source
    assert '/static/component-ui.js?v=' in index_source


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
    assert 'v041PlatePulse' in v041


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
