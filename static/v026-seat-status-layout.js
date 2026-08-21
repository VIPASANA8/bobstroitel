(() => {
  "use strict";

  function normalizeSeatStatuses() {
    document.querySelectorAll(".seat-card").forEach(card => {
      const status = card.querySelector(".avatar-wrap > .player-status");
      if (status) {
        card.appendChild(status);
        status.classList.add("v026-seat-status");
      }

      const ready = card.querySelector(":scope > .v024-ready-badge");
      if (ready) ready.classList.add("v026-seat-status");
    });
  }

  onRendered("seats", normalizeSeatStatuses);

  const previousSyncComponentUi = window.syncComponentUi;
  window.syncComponentUi = function syncComponentUiV026(gameState, tableState) {
    previousSyncComponentUi?.(gameState, tableState);
    normalizeSeatStatuses();
  };

  const style = document.createElement("style");
  style.id = "v026-seat-status-layout-style";
  style.textContent = `
    @media (max-width:780px){
      /* Pull the two upper seats inward and down so the HUD/table rim never clips them. */
      body.v014{
        --seat-3-x:29% !important;
        --seat-3-y:18.7% !important;
        --seat-4-x:71% !important;
        --seat-4-y:18.7% !important;
      }

      /* One shared status rail under every occupied seat-card. */
      body.v014 .seat-card > .player-status.v026-seat-status,
      body.v014 .seat-card > .v024-ready-badge.v026-seat-status{
        position:absolute !important;
        left:50% !important;
        right:auto !important;
        top:calc(100% + 5px) !important;
        bottom:auto !important;
        transform:translateX(-50%) !important;
        z-index:45 !important;
        box-sizing:border-box !important;
        display:inline-flex !important;
        align-items:center !important;
        justify-content:center !important;
        min-width:46px !important;
        height:17px !important;
        margin:0 !important;
        padding:0 7px !important;
        border-radius:999px !important;
        font-size:10px !important;
        font-weight:950 !important;
        line-height:1 !important;
        letter-spacing:.035em !important;
        white-space:nowrap !important;
        pointer-events:none !important;
      }

      body.v014 .seat-card > .player-status.v026-seat-status.status-thinking{
        color:#bde9ff !important;
        border:1px solid rgba(75,191,255,.43) !important;
        background:rgba(4,28,48,.91) !important;
        box-shadow:0 0 9px rgba(47,184,255,.13) !important;
      }

      body.v014 .seat-card > .player-status.v026-seat-status.status-fold{
        color:#98a7b8 !important;
        border:1px solid rgba(126,145,171,.26) !important;
        background:rgba(8,13,26,.90) !important;
      }

      body.v014 .seat-card > .player-status.v026-seat-status.status-turn{
        color:#b9ffe2 !important;
        border:1px solid rgba(55,220,162,.38) !important;
        background:rgba(4,38,29,.91) !important;
      }

      body.v014 .seat-card > .player-status.v026-seat-status.status-allin{
        color:#ffe0a2 !important;
        border:1px solid rgba(238,186,76,.42) !important;
        background:rgba(44,29,2,.91) !important;
      }

      body.v014 .seat-card > .player-status.v026-seat-status .thinking-dots{
        display:inline-flex !important;
        align-items:center !important;
        gap:1px !important;
        margin-left:2px !important;
      }

      body.v014 .seat-card > .player-status.v026-seat-status .thinking-dots b{
        width:2px !important;
        height:2px !important;
        border-radius:50% !important;
      }

      /* Ready/not-ready uses exactly the same geometry as the in-hand status. */
      body.v014 .seat-card > .v024-ready-badge.v026-seat-status i{
        width:5px !important;
        height:5px !important;
        flex:0 0 5px !important;
      }

      /* Give the new outside status rail enough breathing room. */
      body.v014 .seat{
        overflow:visible !important;
      }
    }
  `;
  document.head.appendChild(style);

  normalizeSeatStatuses();
})();
