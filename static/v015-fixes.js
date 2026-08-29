(() => {
  "use strict";

  /* wagerPointForPlayerV017 used to sit here: a table of fixed wager zones
     for the phone, keyed by visual seat. It has not run in a long time.
     v031 assigns the same global, does not delegate to whatever it found
     there, and is appended later (component-ui -> v030 -> v031), so its
     version is the one every chip has flown by. Removed 2026-08-29; the
     zones are in the history if the phone ever wants them back. */

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
