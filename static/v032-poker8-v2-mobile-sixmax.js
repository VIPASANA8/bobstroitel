(() => {
  "use strict";


  function activeSeatElements() {
    return [...document.querySelectorAll('.seat[data-seat]')].filter((seat) => {
      const card = seat.querySelector('.seat-card');
      return Boolean(card && !seat.querySelector('.seat-empty'));
    });
  }

  function viewerPhysicalSeat(gameState, tableState) {
    if (gameState?.viewer_player_id && gameState?.players?.[gameState.viewer_player_id]) {
      return Number(gameState.players[gameState.viewer_player_id].seat);
    }
    const activeProfile = gameState?.active_profile_id || tableState?.active_profile_id;
    const human = tableState?.seats?.find?.((seat) =>
      seat?.active && seat?.occupant_type === 'human' && (!activeProfile || seat?.profile_id === activeProfile)
    );
    return human ? Number(human.seat) : 0;
  }

  function sixMaxOrder(anchor, seats) {
    return [...seats].sort((a, b) => {
      const pa = Number(a.dataset.seat);
      const pb = Number(b.dataset.seat);
      const da = ((pa - anchor) % 7 + 7) % 7;
      const db = ((pb - anchor) % 7 + 7) % 7;
      return da - db;
    });
  }

  function chooseVisibleSeats(anchor) {
    const all = [...document.querySelectorAll('.seat[data-seat]')];
    const active = sixMaxOrder(anchor, activeSeatElements());
    if (active.length > 6) return null;

    const activeSet = new Set(active);
    const empties = sixMaxOrder(anchor, all.filter((seat) => !activeSet.has(seat)));
    return [...active, ...empties].slice(0, 6);
  }

  function applySixMaxLayout(gameState, tableState) {
    // This gate is what kept the whole v2 table on phones. Everything the five
    // v2 layers draw hangs off the poker8-v2-sixmax class added below, so
    // desktop got none of it: no seat accents, no action grid, no HUD summary,
    // no turn clock, no all-in bar -- and fell further behind with every
    // mobile fix. The layout is written in percentages of the felt, so it
    // scales; the handful of fixed pixel values are re-tuned for desktop in
    // v039, which is where desktop geometry belongs.
    const anchor = viewerPhysicalSeat(gameState, tableState);
    const visible = chooseVisibleSeats(anchor);
    if (!visible) {
      document.body.classList.remove('poker8-v2-sixmax');
      document.querySelectorAll('.seat[data-seat]').forEach((seat) => seat.classList.remove('v032-hidden-seat'));
      return false;
    }

    document.body.classList.add('poker8-v2-sixmax');
    const visibleSet = new Set(visible);
    const ordered = sixMaxOrder(anchor, visible);

    document.querySelectorAll('.seat[data-seat]').forEach((seat) => {
      seat.classList.toggle('v032-hidden-seat', !visibleSet.has(seat));
    });

    ordered.forEach((seat, index) => {
      seat.dataset.visualSeat = String(index);
    });

    return true;
  }

  const previousSyncComponentSeatLayout = window.syncComponentSeatLayout;
  window.syncComponentSeatLayout = function syncPoker8V2SixMax(gameState, tableState) {
    previousSyncComponentSeatLayout?.(gameState, tableState);
    applySixMaxLayout(gameState, tableState);
  };

  const previousSyncComponentUi = window.syncComponentUi;
  window.syncComponentUi = function syncPoker8V2(gameState, tableState) {
    previousSyncComponentUi?.(gameState, tableState);
    applySixMaxLayout(gameState, tableState);
    decorateState(gameState);
  };

  function decorateState(gameState) {
    const players = gameState?.players || {};
    document.querySelectorAll('.seat[data-seat]').forEach((seat) => {
      const physical = Number(seat.dataset.seat);
      const player = Object.values(players).find((p) => Number(p?.seat) === physical);
      const card = seat.querySelector('.seat-card');
      if (!card) return;
      card.classList.toggle('v032-folded', Boolean(player?.folded));
      card.classList.toggle('v032-active-turn', Boolean(player && gameState?.acting_player === player.id));
      card.classList.toggle('v032-in-hand', Boolean(player && !player.folded));
    });
  }

  function formatStack(value) {
    const n = Number(value || 0);
    if (Math.abs(n) < 10000) return n.toLocaleString('en-US', { maximumFractionDigits: n < 100 ? 1 : 0 });
    if (Math.abs(n) < 1_000_000) return `${(n / 1000).toFixed(n < 100_000 ? 1 : 0)}K`;
    return `${(n / 1_000_000).toFixed(n < 10_000_000 ? 1 : 0)}M`;
  }

  const previousFormatBB = window.formatBB;
  if (typeof previousFormatBB === 'function') {
    window.formatPoker8Stack = formatStack;
  }

  const style = document.createElement('style');
  style.id = 'v032-poker8-v2-mobile-sixmax-style';
  style.textContent = `
    /* Was @media (max-width:780px). The v2 table is the table now, at every
       width; desktop geometry is tuned in v039. */
    @media all{
      body.poker8-v2-sixmax{
        --table-stage-h:clamp(492px,65dvh,540px);
        --seat-0-x:50%; --seat-0-y:88.8%;
        --seat-1-x:15%; --seat-1-y:66.5%;
        --seat-2-x:12%; --seat-2-y:28.5%;
        --seat-3-x:50%; --seat-3-y:10.5%;
        --seat-4-x:88%; --seat-4-y:28.5%;
        --seat-5-x:85%; --seat-5-y:66.5%;
        --pot-y:30%; --pot-chips-y:39.5%; --board-y:49.5%;
        background:
          radial-gradient(circle at 50% 2%,rgba(14,92,62,.10),transparent 28%),
          linear-gradient(180deg,#080604 0,#050504 40%,#020303 100%) !important;
      }

      body.poker8-v2-sixmax .mobile-game-header{
        height:50px!important;
        padding:6px 10px!important;
        background:linear-gradient(180deg,rgba(6,7,7,.96),rgba(4,5,5,.84))!important;
        border-bottom:1px solid rgba(68,231,210,.12)!important;
        backdrop-filter:blur(10px)!important;
      }
      body.poker8-v2-sixmax .mobile-street-pill{display:none!important}
      body.poker8-v2-sixmax .mobile-primary-action{display:none!important}
      body.poker8-v2-sixmax .mobile-menu-button{
        width:42px!important;height:42px!important;border-radius:13px!important;
        border:1px solid rgba(52,214,255,.64)!important;
        background:linear-gradient(180deg,rgba(7,28,34,.96),rgba(3,12,17,.98))!important;
        box-shadow:0 0 0 1px rgba(52,214,255,.13),0 0 18px rgba(38,201,255,.16),inset 0 0 14px rgba(29,180,221,.07)!important;
      }
      body.poker8-v2-sixmax .mobile-game-header::after{
        content:'⚙';position:absolute;right:11px;top:6px;width:42px;height:42px;display:grid;place-items:center;
        border:1px solid rgba(52,214,255,.64);border-radius:13px;color:#d9f8ff;font-size:20px;
        background:linear-gradient(180deg,rgba(7,28,34,.96),rgba(3,12,17,.98));
        box-shadow:0 0 0 1px rgba(52,214,255,.13),0 0 18px rgba(38,201,255,.13),inset 0 0 14px rgba(29,180,221,.06);
        pointer-events:none;
      }

      body.poker8-v2-sixmax .app-shell{padding-top:50px!important;min-height:100dvh!important;width:100%!important}
      body.poker8-v2-sixmax .table-frame{
        height:var(--table-stage-h)!important;min-height:var(--table-stage-h)!important;padding:0 7px!important;
        background:
          radial-gradient(ellipse at 50% 45%,rgba(49,28,12,.38),transparent 58%),
          linear-gradient(180deg,#130c07,#080604)!important;
        border:0!important;border-radius:0!important;overflow:hidden!important;
      }
      body.poker8-v2-sixmax .felt{
        inset:auto!important;width:100%!important;height:100%!important;min-height:0!important;
        border:10px solid transparent!important;
        border-radius:47% / 35%!important;
        background:
          linear-gradient(#063d27,#063d27) padding-box,
          linear-gradient(90deg,#2c1307 0,#7b3e17 18%,#2c1307 35%,#9a5b25 52%,#321607 69%,#76401c 84%,#231005 100%) border-box!important;
        outline:1px solid rgba(89,255,203,.48)!important;
        box-shadow:
          inset 0 0 80px rgba(0,0,0,.48),
          inset 0 0 0 2px rgba(77,255,199,.13),
          0 0 0 2px rgba(10,8,6,.88),
          0 0 17px rgba(28,238,188,.22),
          0 0 30px rgba(255,55,191,.08)!important;
      }
      body.poker8-v2-sixmax .felt::before{
        inset:8px!important;border:1px solid rgba(54,255,203,.45)!important;
        box-shadow:0 0 9px rgba(46,255,208,.22),inset 0 0 9px rgba(46,255,208,.10)!important;
      }
      body.poker8-v2-sixmax .table-glow{
        inset:14%!important;background:radial-gradient(ellipse,rgba(34,170,111,.10),transparent 67%)!important;
      }
      body.poker8-v2-sixmax .v032-hidden-seat{display:none!important}

      body.poker8-v2-sixmax .seat{width:88px!important;min-height:82px!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="0"]{left:var(--seat-0-x)!important;top:var(--seat-0-y)!important;width:126px!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:var(--seat-1-x)!important;top:var(--seat-1-y)!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:var(--seat-2-x)!important;top:var(--seat-2-y)!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="3"]{left:var(--seat-3-x)!important;top:var(--seat-3-y)!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:var(--seat-4-x)!important;top:var(--seat-4-y)!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:var(--seat-5-x)!important;top:var(--seat-5-y)!important}

      body.poker8-v2-sixmax .seat-card{
        min-height:72px!important;padding:19px 5px 6px!important;border-radius:14px!important;
        border:1px solid rgba(119,89,162,.46)!important;
        background:linear-gradient(180deg,rgba(8,8,10,.95),rgba(2,3,5,.985))!important;
        box-shadow:0 8px 22px rgba(0,0,0,.44),inset 0 0 16px rgba(255,255,255,.018)!important;
        transition:opacity .24s ease,filter .24s ease,box-shadow .2s ease,border-color .2s ease!important;
      }
      body.poker8-v2-sixmax .player-avatar{width:42px!important;height:42px!important;border-width:1.5px!important;background:#050607!important}
      body.poker8-v2-sixmax .avatar-wrap{top:-20px!important}
      body.poker8-v2-sixmax .seat-name{max-width:72px!important;font-size:10px!important;font-weight:850!important}
      body.poker8-v2-sixmax .seat-stack{font-size:12px!important;color:#57e1a6!important;font-weight:900!important}
      body.poker8-v2-sixmax .position-chip{font-size:7px!important;padding:2px 4px!important}

      body.poker8-v2-sixmax .seat-card.v032-in-hand:not(.v032-active-turn){
        border-color:rgba(199,70,255,.46)!important;
        box-shadow:0 0 10px rgba(199,70,255,.08),0 8px 22px rgba(0,0,0,.44)!important;
      }
      body.poker8-v2-sixmax .seat-card.v032-active-turn{
        border-color:rgba(255,158,49,.82)!important;
        box-shadow:0 0 0 1px rgba(255,158,49,.18),0 0 18px rgba(255,137,24,.30),0 8px 24px rgba(0,0,0,.48)!important;
      }
      body.poker8-v2-sixmax .seat-card.v032-folded{
        opacity:.28!important;filter:saturate(.18) brightness(.68)!important;box-shadow:none!important;
      }
      body.poker8-v2-sixmax .seat-card.v032-folded .player-cards{opacity:0!important;transform:translateY(-7px) scale(.94)!important;pointer-events:none!important}

      body.poker8-v2-sixmax .player-cards{
        position:absolute!important;left:50%!important;top:-43px!important;transform:translateX(-50%)!important;
        min-height:0!important;gap:2px!important;z-index:-1!important;transition:opacity .22s ease,transform .22s ease!important;
      }
      body.poker8-v2-sixmax .player-cards .card{
        width:34px!important;height:47px!important;border-radius:6px!important;font-size:13px!important;
        background:linear-gradient(160deg,#07100d,#020403)!important;color:#eafff6!important;
        border:1px solid rgba(85,244,192,.58)!important;
        box-shadow:0 0 8px rgba(63,238,188,.18),inset 0 0 12px rgba(33,160,119,.08)!important;
      }
      body.poker8-v2-sixmax .player-cards .card.red{color:#ff6d88!important;border-color:rgba(255,72,123,.62)!important;box-shadow:0 0 8px rgba(255,72,123,.16)!important}
      body.poker8-v2-sixmax .player-cards .card.back{
        background:linear-gradient(145deg,#07110e,#020403)!important;
        border-color:rgba(111,255,206,.48)!important;
      }

      body.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-card.viewer-seat{
        min-height:74px!important;padding:20px 7px 6px!important;border-color:rgba(43,167,255,.88)!important;
        box-shadow:0 0 0 1px rgba(44,169,255,.16),0 0 18px rgba(44,169,255,.26),0 8px 26px rgba(0,0,0,.48)!important;
      }
      /* Size/position dropped here too (item 5/6: every avatar is the same
         size and offset, hero included) -- this compound selector otherwise
         outranks v038's own flat sizing (4 classes vs 3) and was silently
         winning on top of it. */
      body.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .seat-name{font-size:11px!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .seat-stack{font-size:14px!important;color:#31b8ff!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards{top:-60px!important;z-index:-1!important;gap:3px!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="0"] .viewer-seat .player-cards .card{width:46px!important;height:64px!important;font-size:17px!important;border-color:rgba(45,174,255,.78)!important;box-shadow:0 0 12px rgba(38,166,255,.25)!important}

      body.poker8-v2-sixmax .pot-total{top:var(--pot-y)!important;min-width:104px!important;padding:5px 10px!important;border-radius:11px!important;background:rgba(3,16,10,.58)!important;border:1px solid rgba(72,211,156,.20)!important}
      body.poker8-v2-sixmax .pot-total-label{font-size:9px!important;color:#a5b9ae!important}
      body.poker8-v2-sixmax .pot-total strong{font-size:24px!important;color:#f4fff8!important;text-shadow:0 1px 5px rgba(0,0,0,.9)!important}
      body.poker8-v2-sixmax .pot-chips{top:var(--pot-chips-y)!important}
      body.poker8-v2-sixmax .board-cards{top:var(--board-y)!important;gap:4px!important}
      body.poker8-v2-sixmax .board-cards .card{
        width:43px!important;height:61px!important;font-size:16px!important;border-radius:7px!important;
        background:linear-gradient(155deg,#07100d,#010302)!important;color:#effff8!important;
        border:1px solid rgba(66,255,195,.63)!important;
        box-shadow:0 0 9px rgba(60,255,196,.22),inset 0 0 14px rgba(42,161,122,.08)!important;
      }
      body.poker8-v2-sixmax .board-cards .card.red{color:#ff667f!important;border-color:rgba(255,75,116,.68)!important;box-shadow:0 0 9px rgba(255,75,116,.19)!important}

      body.poker8-v2-sixmax .mobile-hud-card{display:none!important}
      body.poker8-v2-sixmax .street-badge{display:none!important}
      body.poker8-v2-sixmax .result-text{display:none!important}

      body.poker8-v2-sixmax .action-panel,
      body.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        min-height:calc(100dvh - 50px - var(--table-stage-h))!important;
        padding:8px 9px calc(9px + env(safe-area-inset-bottom))!important;
        border-top:1px solid rgba(78,231,215,.22)!important;
        background:linear-gradient(180deg,rgba(5,7,8,.98),rgba(1,2,3,1))!important;
        box-shadow:0 -12px 28px rgba(0,0,0,.52)!important;
      }
      body.poker8-v2-sixmax .action-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:6px!important}
      body.poker8-v2-sixmax .action-grid .action-slot{
        min-height:50px!important;border-radius:12px!important;font-size:10px!important;
        background:linear-gradient(180deg,rgba(8,12,16,.98),rgba(2,5,8,.995))!important;
        box-shadow:inset 0 0 15px rgba(255,255,255,.018),0 0 12px rgba(0,0,0,.35)!important;
      }
      body.poker8-v2-sixmax .action-grid .action-slot.fold{border-color:rgba(255,73,73,.72)!important;color:#ffd7d7!important;box-shadow:0 0 11px rgba(255,64,64,.11)!important}
      body.poker8-v2-sixmax .action-grid .action-slot.check,
      body.poker8-v2-sixmax .action-grid .action-slot.call{border-color:rgba(49,160,255,.72)!important;color:#e1f3ff!important;box-shadow:0 0 11px rgba(49,160,255,.10)!important}
      body.poker8-v2-sixmax .action-grid .action-slot.raise{border-color:rgba(59,234,112,.72)!important;color:#e5ffec!important;box-shadow:0 0 11px rgba(59,234,112,.10)!important}
      body.poker8-v2-sixmax .action-grid .action-slot.all-in{border-color:rgba(255,163,57,.74)!important;color:#fff0d8!important}
      body.poker8-v2-sixmax .quick-sizes button{background:rgba(4,8,10,.96)!important;border-color:rgba(77,116,140,.34)!important}
      body.poker8-v2-sixmax .amount-row{background:rgba(3,6,8,.97)!important;border-color:rgba(53,159,219,.24)!important}
      body.poker8-v2-sixmax .amount-step{border-color:rgba(48,164,255,.52)!important;background:linear-gradient(180deg,rgba(6,31,48,.95),rgba(2,13,23,.99))!important;color:#cdeeff!important}
      body.poker8-v2-sixmax #amountSlider{accent-color:#27a8ff!important}
      body.poker8-v2-sixmax .mobile-auto-action{display:none!important}
      body.poker8-v2-sixmax .mobile-turn-tools{display:none!important}
    }

    @media (max-width:370px){
      body.poker8-v2-sixmax{--table-stage-h:470px}
      body.poker8-v2-sixmax .seat{width:82px!important}
      body.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:118px!important}
      body.poker8-v2-sixmax .board-cards .card{width:40px!important;height:57px!important;font-size:15px!important}
      body.poker8-v2-sixmax .action-grid .action-slot{min-height:48px!important;font-size:9px!important}
    }
  `;
  document.head.appendChild(style);

  window.addEventListener('resize', () => applySixMaxLayout(game, tableData));
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => applySixMaxLayout(game, tableData), { once: true });
  } else {
    applySixMaxLayout(game, tableData);
  }
})();