(() => {
  "use strict";

  const originalWagerPointForPlayer = wagerPointForPlayer;

  wagerPointForPlayer = function wagerPointForPlayerV017(state, playerId) {
    if (!isMobileLayout()) return originalWagerPointForPlayer(state, playerId);

    const felt = feltNode();
    if (!felt) return originalWagerPointForPlayer(state, playerId);

    const seatNumber = state?.players?.[playerId]?.seat;
    const seatEl = document.querySelector(`.seat[data-seat="${seatNumber}"]`);
    const visualSeat = Number(seatEl?.dataset.visualSeat ?? seatNumber ?? -1);

    // Fixed wager zones for the mobile composition.
    // They no longer depend on the line seat -> pot, so a bet cannot drift into
    // the bank label or back into a player's cards when the table geometry changes.
    const zones = {
      0: { x: 0.50, y: 0.64 },
      1: { x: 0.32, y: 0.62 },
      2: { x: 0.26, y: 0.43 },
      3: { x: 0.28, y: 0.28 },
      4: { x: 0.72, y: 0.28 },
      5: { x: 0.74, y: 0.43 },
      6: { x: 0.68, y: 0.62 },
    };

    const zone = zones[visualSeat];
    if (!zone) return originalWagerPointForPlayer(state, playerId);

    return {
      x: felt.clientWidth * zone.x,
      y: felt.clientHeight * zone.y,
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
        font-size:10px !important;
        line-height:1 !important;
        border-radius:6px !important;
      }
    }
  `;
  document.head.appendChild(style);
})();
