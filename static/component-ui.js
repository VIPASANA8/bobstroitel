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

    if (!document.querySelector('script[data-v018-fixes]')) {
      const v018 = document.createElement("script");
      v018.src = "/static/v018-fixes.js";
      v018.dataset.v018Fixes = "1";
      document.body.appendChild(v018);
    }

    if (!document.querySelector('script[data-v019-fixes]')) {
      const v019 = document.createElement("script");
      v019.src = "/static/v019-center-polish.js";
      v019.dataset.v019Fixes = "1";
      document.body.appendChild(v019);
    }

    if (!document.querySelector('script[data-v020-fixes]')) {
      const v020 = document.createElement("script");
      v020.src = "/static/v020-fixes.js?v=table-guide-1";
      v020.dataset.v020Fixes = "1";
      document.body.appendChild(v020);
    }

    if (!document.querySelector('script[data-v022-balance-topup]')) {
      const v022 = document.createElement("script");
      v022.src = "/static/v022-balance-topup.js";
      v022.dataset.v022BalanceTopup = "1";
      document.body.appendChild(v022);
    }

    if (!document.querySelector('script[data-v023-brand-balance-fix]')) {
      const v023 = document.createElement("script");
      v023.src = "/static/v023-brand-balance-fix.js";
      v023.dataset.v023BrandBalanceFix = "1";
      document.body.appendChild(v023);
    }

    if (!document.querySelector('script[data-v024-ready-phase]')) {
      const v024 = document.createElement("script");
      v024.src = "/static/v024-ready-phase.js?v=table-guide-1";
      v024.dataset.v024ReadyPhase = "1";
      document.body.appendChild(v024);
    }

    if (!document.querySelector('script[data-v025-showdown-compare]')) {
      const v025 = document.createElement("script");
      v025.src = "/static/v025-showdown-compare.js?v=table-guide-1";
      v025.dataset.v025ShowdownCompare = "1";
      document.body.appendChild(v025);
    }

    if (!document.querySelector('script[data-v026-seat-status-layout]')) {
      const v026 = document.createElement("script");
      v026.src = "/static/v026-seat-status-layout.js?v=table-guide-1";
      v026.dataset.v026SeatStatusLayout = "1";
      document.body.appendChild(v026);
    }

    if (!document.querySelector('script[data-v027-compact-seats-controls]')) {
      const v027 = document.createElement("script");
      v027.src = "/static/v027-compact-seats-controls.js?v=table-guide-1";
      v027.dataset.v027CompactSeatsControls = "1";
      document.body.appendChild(v027);
    }

    if (!document.querySelector('script[data-v028-center-ready]')) {
      const v028 = document.createElement("script");
      v028.src = "/static/v028-center-ready.js?v=table-guide-1";
      v028.dataset.v028CenterReady = "1";
      document.body.appendChild(v028);
    }

    if (!document.querySelector('script[data-v029-ready-style]')) {
      const v029 = document.createElement("script");
      v029.src = "/static/v029-ready-style.js";
      v029.dataset.v029ReadyStyle = "1";
      document.body.appendChild(v029);
    }

    if (!document.querySelector('script[data-v030-seat-ready-fix]')) {
      const v030 = document.createElement("script");
      v030.src = "/static/v030-seat-ready-fix.js?v=table-guide-1";
      v030.dataset.v030SeatReadyFix = "1";
      document.body.appendChild(v030);
    }

    if (!document.querySelector('script[data-v032-poker8-v2-sixmax]')) {
      const v032 = document.createElement("script");
      v032.src = "/static/v032-poker8-v2-mobile-sixmax.js?v=table-guide-1";
      v032.dataset.v032Poker8V2Sixmax = "1";
      v032.addEventListener("load", () => {
        if (!document.querySelector('script[data-v037-poker8-v2-reference-table]')) {
          const finalMobile = document.createElement("script");
          finalMobile.src = "/static/v037-poker8-v2-reference-table.js?v=table-guide-1";
          finalMobile.dataset.v037Poker8V2ReferenceTable = "1";
          document.body.appendChild(finalMobile);
        }
      }, { once:true });
      document.body.appendChild(v032);
    } else if (!document.querySelector('script[data-v037-poker8-v2-reference-table]')) {
      const finalMobile = document.createElement("script");
      finalMobile.src = "/static/v037-poker8-v2-reference-table.js?v=table-guide-1";
      finalMobile.dataset.v037Poker8V2ReferenceTable = "1";
      document.body.appendChild(finalMobile);
    }
  });
})();
