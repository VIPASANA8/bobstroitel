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

  renderWagerMarkers = function renderWagerMarkersV031() {
    const layer = $("wagerLayer");
    if (!layer) return;
    layer.innerHTML = "";
    if (!game || game.terminal) return;

    for (const player of Object.values(game.players || {})) {
      const wager = Number(player.street_invested || 0);
      if (!(wager > 0)) continue;
      const point = wagerPointForPlayer(game, player.id);
      if (!point) continue;

      const marker = document.createElement("div");
      marker.className = `bet-marker ${game?.acting_player === player.id ? "acting-wager" : ""}`.trim();
      marker.dataset.playerId = player.id;
      marker.style.left = `${point.x}px`;
      marker.style.top = `${point.y}px`;
      marker.innerHTML = `${chipStackHtml(wager, true)}<span>${formatBB(wager)}</span>`;
      layer.appendChild(marker);
    }
  };

  const style = document.createElement("style");
  style.id = "v031-pot-cluster-mobile-fix-style";
  style.textContent = `
    .chip-cluster.pot-cluster{
      position:relative !important;
      display:block !important;
      width:100% !important;
      min-width:132px !important;
      height:64px !important;
    }

    .chip-cluster.pot-cluster .chip-column.pot-stack{
      position:absolute !important;
      left:50% !important;
      bottom:0 !important;
      width:26px !important;
      height:58px !important;
      margin:0 !important;
      transform:translate(calc(-50% + var(--stack-x, 0px)), var(--stack-y, 0px)) rotate(calc((var(--col) - 3) * 1deg)) !important;
      z-index:var(--stack-z, 1) !important;
    }

    .bet-marker.acting-wager span{
      padding:0 !important;
      border-radius:0 !important;
      background:transparent !important;
      border:0 !important;
      box-shadow:none !important;
      text-shadow:0 1px 4px rgba(0,0,0,.85),0 0 12px rgba(76,214,255,.18) !important;
    }

    @media (max-width:780px){
      body.v014 .pot-chips .chip-cluster.pot-cluster,
      .neon-ref-v107 .pot-chips .chip-cluster.pot-cluster{
        min-width:132px !important;
        height:56px !important;
      }

      body.v014 .pot-chips .chip-column.pot-stack,
      .neon-ref-v107 .pot-chips .chip-column.pot-stack{
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
