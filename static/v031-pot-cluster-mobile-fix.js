(() => {
  "use strict";

  // potClusterOffsets, the chipStackHtml override and the renderPotChips
  // override all moved into app.js, beside the function they were overriding.
  // What is left here is the wager geometry, which nothing else defines.

  wagerPointForPlayer = function wagerPointForPlayerV031(state, playerId) {
    const from = seatPointForPlayer(state, playerId);
    const to = potPoint();
    if (!from || !to) return to || from;

    let factor = 0.57;
    let nudgeX = 0;
    let nudgeY = 0;

    const player = state?.players?.[playerId];
    const seatEl = player ? document.querySelector(`.seat[data-seat="${player.seat}"]`) : null;
    const visualSeat = Number(seatEl?.dataset?.visualSeat ?? -1);
    const mobile = window.matchMedia?.("(max-width: 780px)")?.matches;

    if (mobile && visualSeat === 0) {
      return {
        x: from.x + 66,
        y: from.y - 30,
      };
    }

    if (mobile) {
      if (visualSeat === 2) {
        factor = 0.53;
        nudgeX = -2;
        nudgeY = -12;
      } else if (visualSeat === 5) {
        factor = 0.53;
        nudgeX = 2;
        nudgeY = -12;
      } else if (visualSeat === 1 || visualSeat === 6) {
        factor = 0.54;
        nudgeY = -8;
      } else if (visualSeat === 3 || visualSeat === 4) {
        factor = 0.60;
        nudgeY = 3;
      }
    }

    return {
      x: from.x + (to.x - from.x) * factor + nudgeX,
      y: from.y + (to.y - from.y) * factor + nudgeY,
    };
  };

  //: This layer used to reassign renderWagerMarkers to draw a chip stack in
  //: front of each player. The stake is written inside the avatar now, so
  //: there is nothing here to override -- app.js owns the one
  //: implementation, and it draws nothing.

  const style = document.createElement("style");
  style.id = "v031-pot-cluster-mobile-fix-style";
  style.textContent = `
    .bet-marker.acting-wager span{
      padding:0 !important;
      border-radius:0 !important;
      background:transparent !important;
      border:0 !important;
      box-shadow:none !important;
      text-shadow:0 1px 4px rgba(0,0,0,.85),0 0 12px rgba(76,214,255,.18) !important;
    }

    @media (max-width:780px){
      body.v014 .pot-chips .chip-cluster.pot-wing,
      .neon-ref-v107 .pot-chips .chip-cluster.pot-wing{
        min-width:0 !important;
        height:56px !important;
      }

      body.v014 .pot-chips .chip-column,
      .neon-ref-v107 .pot-chips .chip-column{
        width:22px !important;
        height:50px !important;
      }

      .neon-ref-v107 .dealer-button{
        right:-15px !important;
        left:auto !important;
        bottom:34px !important;
        width:22px !important;
        height:22px !important;
        font-size:10px !important;
      }

      .neon-ref-v107 .viewer-seat .dealer-button{
        right:-14px !important;
        left:auto !important;
        bottom:44px !important;
      }
    }
  `;
  document.head.appendChild(style);

  if (game) {
    renderPotChips(game.pot || 0);
    renderWagerMarkers();
  }
})();
