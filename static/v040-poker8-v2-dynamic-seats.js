(() => {
  "use strict";

  const MOBILE_QUERY = "(max-width: 780px)";
  const DESKTOP_QUERY = "(min-width: 781px)";
  const isMobile = () => window.matchMedia?.(MOBILE_QUERY)?.matches ?? false;
  const isDesktop = () => window.matchMedia?.(DESKTOP_QUERY)?.matches ?? false;

  // Pot/board/chips sit in a fixed proportional band regardless of felt
  // height (they're positioned in %, top:25/38/47 -- see v038/v019): roughly
  // y 22%-56%, x 14%-86%. Every seat point below keeps its centre outside
  // that band with margin for the seat's own half-height, or the seat visibly
  // sits on top of the pot/board/cards.
  const LAYOUTS = {
    1: [[50, 80]],
    2: [[50, 80], [50, 15]],
    3: [[50, 80], [18, 14], [82, 14]],
    4: [[50, 80], [14, 66], [50, 13], [86, 66]],
    5: [[50, 80], [12, 63], [24, 14], [76, 14], [88, 63]],
    6: [[50, 80], [12, 61], [12, 19], [50, 13], [88, 19], [88, 61]],
  };

  // В режиме наблюдения у стола нет закреплённого нижнего места.
  // Поэтому два активных игрока выводятся слева и справа, а не друг напротив друга.
  const SPECTATOR_LAYOUTS = {
    2: [[12, 50], [88, 50]],
    3: [[50, 13], [18, 70], [82, 70]],
    4: [[50, 13], [86, 66], [50, 88], [14, 66]],
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
        /* Only the position needs to visibly flip. A live table re-renders
           this element from scratch on every snapshot, which restarts any
           transition on it before it can finish -- animating width/height
           here left the seat box stuck near its pre-transition size
           indefinitely. Dropping them makes the size exact on every paint,
           independent of how often re-renders arrive. */
        transition:transform 460ms cubic-bezier(.22,.8,.24,1)!important;
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
      /* Boxes shrunk ~0.66x to match the item-6 avatar resize (74px -> 49px). */
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat{width:79px!important;height:83px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-3 .seat.v040-dynamic-seat{width:71px!important;height:79px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-4 .seat.v040-dynamic-seat,
      body.v014.poker8-v2-sixmax.p8-player-count-5 .seat.v040-dynamic-seat{width:67px!important;height:77px!important;}
      /* The hero seat used to be pinned at a fixed 87x87 regardless of player
         count -- now it takes the same per-count size as every other seat. */
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] .avatar-wrap{top:7px!important;}
      body.v014.poker8-v2-sixmax.p8-player-count-2 .seat.v040-dynamic-seat[data-visual-seat="1"] .seat-identity{top:50px!important;}
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
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-cards{top:-30px!important;}
      body.v014.poker8-desktop-v2:not(.p8-spectator-layout) .seat.v040-dynamic-seat[data-visual-seat="0"] .player-cards .card{width:40px!important;height:56px!important;}
    }
  `;
  document.head.appendChild(style);

  function playerForSeat(gameState, seat) {
    const physical = Number(seat.dataset.seat);
    const fromGame = Object.values(gameState?.players || {}).find(player => Number(player?.seat) === physical) || null;
    if (fromGame) return fromGame;
    // A seat can be occupied without being in gameState.players -- e.g.
    // someone seated while a hand they aren't dealt into is running (see
    // current_seats on the server, and the same fallback in app.js's
    // seatHtml/renderSeats). The seat-card app.js already rendered for them
    // is the only signal of that here; .viewer-seat is the same fallback's
    // own "is this you" marker, reused instead of re-deriving it a third time.
    const card = seat.querySelector(".seat-card");
    if (!card) return null;
    return { seat: physical, id: null, isViewerCard: card.classList.contains("viewer-seat") };
  }

  function orderedActiveSeats(gameState, tableState) {
    const seats = [...document.querySelectorAll(".seat[data-seat]")];
    const active = seats.filter(seat => playerForSeat(gameState, seat));
    if (!active.length) return { active, viewer: null };

    const viewerId = gameState?.viewer_player_id;
    let viewer = active.find(seat => {
      const player = playerForSeat(gameState, seat);
      return player?.id === viewerId || player?.isViewerCard;
    }) || null;
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
    // This runs on every snapshot/poll, i.e. continuously on a live table. A
    // remove-then-add of the class the body already carries still restarts
    // the width/height/transform transitions on .v040-dynamic-seat (verified:
    // it happens even with no other DOM change), so the seat box never
    // settles at its target size on an active table -- it sits stuck near
    // its pre-transition width for as long as renders keep arriving.
    const countClass = `p8-player-count-${count}`;
    if (!document.body.classList.contains(countClass)) {
      document.body.classList.remove(...[1, 2, 3, 4, 5, 6].map(value => `p8-player-count-${value}`));
      document.body.classList.add(countClass);
    }

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
