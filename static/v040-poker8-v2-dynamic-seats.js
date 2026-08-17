(() => {
  "use strict";

  const MOBILE_QUERY = "(max-width: 780px)";
  const DESKTOP_QUERY = "(min-width: 781px)";
  const isMobile = () => window.matchMedia?.(MOBILE_QUERY)?.matches ?? false;
  const isDesktop = () => window.matchMedia?.(DESKTOP_QUERY)?.matches ?? false;

  const LAYOUTS = {
    1: [[50, 80]],
    2: [[50, 80], [50, 15]],
    3: [[50, 80], [23, 24], [77, 24]],
    4: [[50, 80], [16, 50], [50, 15], [84, 50]],
    5: [[50, 80], [16, 61], [28, 18], [72, 18], [84, 61]],
    6: [[50, 80], [8, 58], [8, 22], [50, 13], [86, 22], [86, 58]],
  };

  // В режиме наблюдения у стола нет закреплённого нижнего места.
  // Поэтому два активных игрока выводятся слева и справа, а не друг напротив друга.
  const SPECTATOR_LAYOUTS = {
    2: [[22, 50], [78, 50]],
    3: [[50, 17], [18, 70], [82, 70]],
    4: [[50, 17], [84, 50], [50, 83], [16, 50]],
    5: [[50, 16], [82, 38], [70, 78], [30, 78], [18, 38]],
    6: [[50, 15], [83, 31], [83, 69], [50, 85], [17, 69], [17, 31]],
  };

  const style = document.createElement("style");
  style.id = "v040-poker8-v2-dynamic-seats-style";
  style.textContent = `
    @media (max-width:780px){
      body.v014.poker8-v2-sixmax .seat.v040-empty-seat{display:none!important;}
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat{
        left:var(--v040-seat-x)!important;top:var(--v040-seat-y)!important;
        transform:translate(calc(-50% + var(--v040-flip-x, 0px)),calc(-50% + var(--v040-flip-y, 0px)))!important;
        will-change:transform;
        transition:transform 460ms cubic-bezier(.22,.8,.24,1),width 260ms ease,height 260ms ease!important;
      }
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-card,
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .avatar-wrap,
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-identity{
        transition:transform 460ms cubic-bezier(.22,.8,.24,1),opacity 220ms ease!important;
      }
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat,
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-card,
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .avatar-wrap,
        body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat .seat-identity{transition:none!important;}
      }
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat{width:120px!important;height:126px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-3 .seat.v040-dynamic-seat{width:108px!important;height:120px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-4 .seat.v040-dynamic-seat,
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat.v040-dynamic-seat{width:102px!important;height:116px!important;}
      body.v014.poker8-v2-sixmax .seat.v040-dynamic-seat[data-visual-seat="0"]{width:132px!important;height:132px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] .avatar-wrap{top:10px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] .seat-identity{top:75px!important;}
    }
    @media (min-width:781px){
      body.v014.poker8-desktop-v2 .seat.v040-empty-seat{display:none!important;}
      body.v014.poker8-desktop-v2 .seat.v040-dynamic-seat{
        left:var(--v040-seat-x)!important;top:var(--v040-seat-y)!important;
        transform:translate(calc(-50% + var(--v040-flip-x, 0px)),calc(-50% + var(--v040-flip-y, 0px)))!important;
        transition:transform 320ms cubic-bezier(.22,.8,.24,1)!important;
        will-change:transform;
      }
      body.v014.poker8-desktop-v2.p8-player-count-2 .seat.v040-dynamic-seat{width:138px!important;height:144px!important;}
      body.v014.poker8-desktop-v2.p8-player-count-3 .seat.v040-dynamic-seat{width:132px!important;height:142px!important;}
      body.v014.poker8-desktop-v2.p8-player-count-4 .seat.v040-dynamic-seat,
      body.v014.poker8-desktop-v2.p8-player-count-5 .seat.v040-dynamic-seat,
      body.v014.poker8-desktop-v2.p8-player-count-6 .seat.v040-dynamic-seat{width:126px!important;height:138px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"]{width:144px!important;height:150px!important;z-index:28!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .avatar-wrap{top:2px!important;width:72px!important;height:72px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-avatar{width:72px!important;height:72px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .seat-identity{top:66px!important;width:132px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-cards{top:-30px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-cards .card{width:40px!important;height:56px!important;}
    }
  `;
  document.head.appendChild(style);

  function playerForSeat(gameState, seat) {
    const physical = Number(seat.dataset.seat);
    return Object.values(gameState?.players || {}).find(player => Number(player?.seat) === physical) || null;
  }

  function orderedActiveSeats(gameState, tableState) {
    const seats = [...document.querySelectorAll(".seat[data-seat]")];
    const active = seats.filter(seat => playerForSeat(gameState, seat));
    if (!active.length) return { active, viewer: null };

    const viewerId = gameState?.viewer_player_id;
    let viewer = active.find(seat => playerForSeat(gameState, seat)?.id === viewerId) || null;
    if (!viewer) {
      const currentProfile = gameState?.active_profile_id || tableState?.active_profile_id;
      viewer = active.find(seat => {
        const player = playerForSeat(gameState, seat);
        return Boolean(player?.profile_id && (!currentProfile || player.profile_id === currentProfile));
      }) || null;
    }

    const anchor = viewer ? Number(viewer.dataset.seat) : Number(active[0].dataset.seat);
    const clockwise = [...active].sort((a, b) => {
      const distance = seat => ((Number(seat.dataset.seat) - anchor) % 6 + 6) % 6;
      return distance(a) - distance(b);
    });
    if (viewer) return { active: [viewer, ...clockwise.filter(seat => seat !== viewer)], viewer };
    return { active: clockwise, viewer: null };
  }

  function moveSeatTo(seat, x, y) {
    const nextX = `${x}%`;
    const nextY = `${y}%`;
    if (seat.style.getPropertyValue("--v040-seat-x") === nextX
      && seat.style.getPropertyValue("--v040-seat-y") === nextY) return;

    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    if (reduceMotion || typeof seat.getBoundingClientRect !== "function") {
      seat.style.setProperty("--v040-seat-x", nextX);
      seat.style.setProperty("--v040-seat-y", nextY);
      seat.style.setProperty("--v040-flip-x", "0px");
      seat.style.setProperty("--v040-flip-y", "0px");
      return;
    }

    const before = seat.getBoundingClientRect();
    seat.style.setProperty("--v040-seat-x", nextX);
    seat.style.setProperty("--v040-seat-y", nextY);
    const after = seat.getBoundingClientRect();
    const deltaX = Math.round(before.left - after.left);
    const deltaY = Math.round(before.top - after.top);
    if (!deltaX && !deltaY) return;

    const token = (Number(seat.dataset.v040MotionToken || "0") + 1);
    seat.dataset.v040MotionToken = String(token);
    seat.style.setProperty("--v040-flip-x", `${deltaX}px`);
    seat.style.setProperty("--v040-flip-y", `${deltaY}px`);
    const settle = () => {
      if (seat.dataset.v040MotionToken !== String(token)) return;
      seat.style.setProperty("--v040-flip-x", "0px");
      seat.style.setProperty("--v040-flip-y", "0px");
    };
    requestAnimationFrame(() => requestAnimationFrame(settle));
  }

  function applyDynamicLayout(gameState, tableState) {
    if (!isMobile() && !isDesktop()) return;
    const allSeats = [...document.querySelectorAll(".seat[data-seat]")];
    const { active, viewer } = orderedActiveSeats(gameState, tableState);
    const count = Math.min(6, active.length);
    if (!count) return;

    const activeSet = new Set(active);
    allSeats.forEach(seat => {
      seat.classList.toggle("v040-empty-seat", !activeSet.has(seat));
      seat.classList.toggle("v040-dynamic-seat", activeSet.has(seat));
    });
    document.body.classList.remove(...[1, 2, 3, 4, 5, 6].map(value => `p8-player-count-${value}`));
    document.body.classList.add(`p8-player-count-${count}`);

    const points = !viewer && SPECTATOR_LAYOUTS[count] ? SPECTATOR_LAYOUTS[count] : LAYOUTS[count];
    document.body.classList.toggle("p8-spectator-layout", !viewer);
    active.forEach((seat, index) => {
      const [x, y] = points[index];
      seat.dataset.visualSeat = viewer ? String(index) : `spectator-${index}`;
      moveSeatTo(seat, x, y);
    });
  }

  const previousLayout = window.syncComponentSeatLayout;
  window.syncComponentSeatLayout = function syncPoker8DynamicSeatLayout(gameState, tableState) {
    previousLayout?.(gameState, tableState);
    applyDynamicLayout(gameState, tableState);
  };

  const previousUi = window.syncComponentUi;
  window.syncComponentUi = function syncPoker8DynamicSeatUi(gameState, tableState) {
    previousUi?.(gameState, tableState);
    applyDynamicLayout(gameState, tableState);
  };

  window.addEventListener("resize", () => applyDynamicLayout(window.game, window.tableData), { passive: true });
})();
