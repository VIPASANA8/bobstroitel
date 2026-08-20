(() => {
  "use strict";

  function potClusterOffsets(stackCount) {
    const patterns = {
      1: [{ x: 0, y: 10, z: 4 }],
      2: [{ x: -9, y: 12, z: 3 }, { x: 8, y: 10, z: 4 }],
      3: [{ x: -14, y: 13, z: 2 }, { x: 1, y: 4, z: 5 }, { x: 15, y: 11, z: 3 }],
      4: [{ x: -18, y: 15, z: 2 }, { x: -5, y: 8, z: 4 }, { x: 8, y: 4, z: 6 }, { x: 19, y: 12, z: 3 }],
      5: [{ x: -23, y: 16, z: 2 }, { x: -11, y: 10, z: 4 }, { x: 0, y: 2, z: 7 }, { x: 12, y: 8, z: 5 }, { x: 23, y: 14, z: 3 }],
      6: [{ x: -25, y: 17, z: 2 }, { x: -15, y: 12, z: 3 }, { x: -4, y: 6, z: 5 }, { x: 7, y: 2, z: 7 }, { x: 18, y: 9, z: 4 }, { x: 28, y: 15, z: 2 }],
      7: [{ x: -28, y: 18, z: 1 }, { x: -18, y: 13, z: 3 }, { x: -8, y: 8, z: 5 }, { x: 1, y: 1, z: 8 }, { x: 10, y: 6, z: 6 }, { x: 20, y: 11, z: 4 }, { x: 30, y: 17, z: 2 }],
    };
    return patterns[stackCount] || patterns[7];
  }

  const originalChipStackHtml = chipStackHtml;
  chipStackHtml = function chipStackHtmlV031(value, compact = false) {
    if (compact) return originalChipStackHtml(value, true);

    const n = Number(value || 0);
    if (!(n > 0)) return "";

    // A minimum of two meant the smallest pot on the table drew the same
    // footprint as a middling one. One stack is a fine picture of a small pot.
    const stackCount = Math.min(7, Math.max(1, visualStackCount(n, false) + (n >= 8 ? 1 : 0)));
    const palette = chipsForAmount(n, 16);
    const fallback = ["chip-1", "chip-25", "chip-5", "chip-100", "chip-05"];
    const offsets = potClusterOffsets(stackCount);
    const columns = [];

    for (let col = 0; col < stackCount; col++) {
      const cls = palette[col % Math.max(1, palette.length)] || fallback[col % fallback.length];
      // Shared with every other stack on the table -- see chipLayers. This
      // used to be 4 + ((col * 2 + round(n)) % 6), which said nothing about
      // the money and stood nine chips high at its worst.
      const chipCount = chipLayers(n, col, false);
      const chips = Array.from({ length: chipCount }, (_, i) =>
        `<i class="poker-chip ${cls}" style="--i:${i}"></i>`
      ).join("");
      const pos = offsets[col] || { x: 0, y: 0, z: 1 };
      columns.push(
        `<span class="chip-column pot-stack" style="--col:${col};--cols:${stackCount};--stack-x:${pos.x}px;--stack-y:${pos.y}px;--stack-z:${pos.z}">${chips}</span>`
      );
    }

    return `<div class="chip-cluster pot-cluster">${columns.join("")}</div>`;
  };

  const originalRenderPotChips = renderPotChips;
  renderPotChips = function renderPotChipsV031(value) {
    let visualValue = Number(value || 0);
    if (game && !game.terminal) {
      const liveWagers = Object.values(game.players || {}).reduce(
        (sum, player) => sum + Math.max(0, Number(player?.street_invested || 0)),
        0
      );
      visualValue = Math.max(visualValue, Number(game.pot || 0) + liveWagers);
    }

    const target = $("potChips");
    if (!target) return originalRenderPotChips(value);
    target.innerHTML = chipStackHtml(visualValue, false);
    target.classList.toggle("has-chips", visualValue > 0);
  };

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
      text-shadow:0 1px 4px rgba(0,0,0,.85),0 0 12px rgba(92,214,255,.18) !important;
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
