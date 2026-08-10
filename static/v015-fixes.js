(() => {
  "use strict";

  const originalWagerPointForPlayer = wagerPointForPlayer;

  wagerPointForPlayer = function wagerPointForPlayerV015(state, playerId) {
    if (!isMobileLayout()) return originalWagerPointForPlayer(state, playerId);

    const from = seatPointForPlayer(state, playerId);
    const to = potPoint();
    if (!from || !to) return to || from;

    const seatNumber = state?.players?.[playerId]?.seat;
    const seatEl = document.querySelector(`.seat[data-seat="${seatNumber}"]`);
    const visualSeat = Number(seatEl?.dataset.visualSeat ?? seatNumber ?? -1);

    const layout = {
      0: { t: 0.30, dx: 0, dy: -4 },
      1: { t: 0.30, dx: 7, dy: -3 },
      2: { t: 0.30, dx: 10, dy: 0 },
      3: { t: 0.32, dx: 8, dy: 7 },
      4: { t: 0.32, dx: -8, dy: 7 },
      5: { t: 0.30, dx: -10, dy: 0 },
      6: { t: 0.30, dx: -7, dy: -3 },
    }[visualSeat] || { t: 0.30, dx: 0, dy: 0 };

    return {
      x: from.x + (to.x - from.x) * layout.t + layout.dx,
      y: from.y + (to.y - from.y) * layout.t + layout.dy,
    };
  };

  togglePendingAction = function togglePendingActionV015(kind) {
    if (!game || !localPlayerAlive() || game.terminal) return;
    const localPlayer = localViewerPlayer();
    const estimateToCall = Math.max(
      0,
      Number(game.current_bet || 0) - Number(localPlayer?.street_invested || 0)
    );
    const amount = Number($("amount")?.value || 0);

    // Повторное нажатие обновляет выбранное авто-действие, а не снимает его.
    pendingAction = { kind, amount, estimateToCall, selectedAt: Date.now() };
    pendingInvalidReason = "";
    renderQueuedActionStatus();
  };

  const style = document.createElement("style");
  style.id = "v015-mobile-wager-fixes";
  style.textContent = `
    @media (max-width:780px){
      body.v014 .bet-marker{
        gap:0 !important;
        pointer-events:none !important;
      }
      body.v014 .bet-marker .chip-cluster{
        transform:scale(.72) !important;
        transform-origin:center bottom !important;
      }
      body.v014 .bet-marker span{
        margin-top:0 !important;
        padding:2px 5px !important;
        font-size:6.8px !important;
        line-height:1 !important;
        border-radius:6px !important;
      }
    }
  `;
  document.head.appendChild(style);
})();
