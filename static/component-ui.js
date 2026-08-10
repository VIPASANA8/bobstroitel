(() => {
  "use strict";

  function viewerSeat(game, tableData) {
    if (game?.viewer_player_id && game?.players?.[game.viewer_player_id]) {
      return Number(game.players[game.viewer_player_id].seat);
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

  /*
   * Converts physical seats into visual seats. Visual 0 is always the viewer,
   * which means CSS can compose the hero at the bottom independently of the engine.
   */
  window.syncComponentSeatLayout = function syncComponentSeatLayout(game, tableData) {
    const anchor = viewerSeat(game, tableData);
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
      if (genericPosition) {
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

  window.addEventListener("load", () => {
    if (!document.querySelector('script[data-v015-fixes]')) {
      const v015 = document.createElement("script");
      v015.src = "/static/v015-fixes.js";
      v015.dataset.v015Fixes = "1";
      document.body.appendChild(v015);
    }

    if (!document.querySelector('script[data-v016-fixes]')) {
      const v016 = document.createElement("script");
      v016.src = "/static/v016-fixes.js";
      v016.dataset.v016Fixes = "1";
      document.body.appendChild(v016);
    }
  });
})();
