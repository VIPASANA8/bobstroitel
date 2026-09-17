(() => {
  "use strict";

  function viewerSeat(game, tableData) {
    if (game?.viewer_player_id && game?.players?.[game.viewer_player_id]) {
      return Number(game.players[game.viewer_player_id].seat);
    }

    // Between hands `game` is null, and the last resort below anchors the whole
    // layout on whichever human sits first -- someone else's seat. The seat
    // list carries the viewer's own id through those phases, so match on it
    // before falling back to guessing.
    const viewerId = game?.viewer_player_id || tableData?.viewer_player_id;
    if (viewerId && Array.isArray(tableData?.seats)) {
      const own = tableData.seats.find(seat => seat?.active && seat?.id === viewerId);
      if (own) return Number(own.seat);
    }

    const activeProfile = game?.active_profile_id || tableData?.active_profile_id;
    if (activeProfile && Array.isArray(tableData?.seats)) {
      const row = tableData.seats.find(
        seat => seat?.active && seat?.occupant_type === "human" && seat?.profile_id === activeProfile
      );
      if (row) return Number(row.seat);
    }

    const human = tableData?.seats?.find?.(seat => seat?.active && seat?.occupant_type === "human");
    return human ? Number(human.seat) : 0;
  }

  window.syncComponentSeatLayout = function syncComponentSeatLayout(game, tableData) {
    const anchor = viewerSeat(game, tableData);
    // Idle decoration only. While a hand runs, the players in it carry real
    // positions and a real dealer button; a seat sitting the hand out still has
    // a generic chip, and dressing that one up gave it a second, wrong dealer
    // button next to the true one.
    const liveHand = Boolean(game && !game.terminal);
    const idlePositionByVisualSeat = {
      0: "BTN",
      1: "HJ",
      2: "CO",
      3: "SB",
      4: "BB",
      5: "MP",
      6: "UTG",
    };

    document.querySelectorAll(".seat[data-seat]").forEach((seatEl) => {
      const physical = Number(seatEl.dataset.seat);
      const visual = ((physical - anchor) % 7 + 7) % 7;
      seatEl.dataset.visualSeat = String(visual);

      const positionChip = seatEl.querySelector(".position-chip");
      const genericPosition = positionChip && /^(БОТ|ИГРОК)$/i.test(positionChip.textContent.trim());
      if (genericPosition && !liveHand) {
        positionChip.textContent = idlePositionByVisualSeat[visual] || positionChip.textContent;
        positionChip.classList.toggle("btn-pos", visual === 0);

        if (visual === 0) {
          const card = seatEl.querySelector(".seat-card");
          if (card && !card.querySelector(".dealer-button")) {
            const dealer = document.createElement("div");
            dealer.className = "dealer-button component-idle-dealer";
            dealer.title = "Дилер / BTN";
            dealer.textContent = "D";
            card.appendChild(dealer);
          }
        }
      }
    });
  };

  window.syncComponentUi = function syncComponentUi(game, tableData) {
    window.syncComponentSeatLayout?.(game, tableData);
  };

  // DOMContentLoaded, not window.load: the mobile v2 look does not exist
  // until this whole chain finishes appending scripts, and window.load waits
  // on the external telegram-web-app.js round trip -- every extra second
  // there is a second spent showing the old v0.11 table underneath.
  document.addEventListener("DOMContentLoaded", () => {
    // One file, one request: every v0xx layer, in the order the old loaders
    // ran them, built by tools/bundle_table_layers.py. It plants each
    // layer's own marker first, so the loaders still inside the layers
    // find the next one "already loaded" and stand down.
    if (document.querySelector("script[data-table-layers]")) return;
    const layers = document.createElement("script");
    layers.src = "/static/table-layers.js?v=guest-tables-15";
    layers.dataset.tableLayers = "1";
    document.body.appendChild(layers);
  });
})();
