(() => {
  "use strict";

  const previousCardState = new Map();

  function seatKey(seatEl) {
    return seatEl?.dataset?.seat ?? "";
  }

  function decorateSeatCard(seatEl) {
    const card = seatEl?.querySelector?.(".seat-card");
    const cards = card?.querySelector?.(".player-cards");
    if (!card || !cards) return;

    const key = seatKey(seatEl);
    const hasCards = Boolean(cards.querySelector(".card"));
    const previous = previousCardState.get(key);

    card.classList.toggle("v027-compact-seat", !hasCards);

    if (hasCards && previous === false) {
      card.classList.add("v027-expand-start");
      requestAnimationFrame(() => {
        requestAnimationFrame(() => card.classList.remove("v027-expand-start"));
      });
    } else {
      card.classList.remove("v027-expand-start");
    }

    previousCardState.set(key, hasCards);
  }

  function decorateSeats() {
    document.querySelectorAll(".seat[data-seat]").forEach(decorateSeatCard);
  }

  onRendered("seats", decorateSeats);

  const previousSyncComponentUi = window.syncComponentUi;
  window.syncComponentUi = function syncComponentUiV027(gameState, tableState) {
    previousSyncComponentUi?.(gameState, tableState);
    decorateSeats();
  };

  function clearPresetSelection() {
    document.querySelectorAll(".quick-sizes [data-sizing]").forEach(button => {
      button.classList.remove("v027-size-selected");
    });
  }

  document.addEventListener("click", event => {
    const preset = event.target?.closest?.(".quick-sizes [data-sizing]");
    if (!preset) return;
    clearPresetSelection();
    preset.classList.add("v027-size-selected");
  }, true);

  document.addEventListener("input", event => {
    if (event.target?.id === "amount" || event.target?.id === "amountSlider") {
      clearPresetSelection();
    }
  }, true);

  const style = document.createElement("style");
  style.id = "v027-compact-seats-controls-style";
  style.textContent = `
    @media (max-width:780px){
      /* ------------------------------------------------------------
         Compact occupied seats before cards are dealt.
         The card body grows smoothly when the hand begins.
         ------------------------------------------------------------ */
      body.v014 .seat-card{
        transition:min-height .30s cubic-bezier(.22,.72,.24,1),
                   padding .30s cubic-bezier(.22,.72,.24,1),
                   border-radius .30s ease,
                   box-shadow .22s ease !important;
      }

      body.v014 .seat-card .player-cards{
        max-height:54px;
        opacity:1;
        transform:translateY(0) scale(1);
        transform-origin:center top;
        transition:max-height .30s cubic-bezier(.22,.72,.24,1),
                   opacity .18s ease .08s,
                   transform .28s cubic-bezier(.22,.72,.24,1),
                   margin .30s ease !important;
      }

      body.v014 .seat-card.v027-compact-seat,
      body.v014 .seat-card.v027-expand-start{
        min-height:51px !important;
        padding-top:18px !important;
        padding-bottom:5px !important;
      }

      body.v014 .seat[data-visual-seat="0"] .seat-card.v027-compact-seat,
      body.v014 .seat[data-visual-seat="0"] .seat-card.v027-expand-start{
        min-height:63px !important;
        padding-top:21px !important;
        padding-bottom:6px !important;
      }

      body.v014 .seat-card.v027-compact-seat .player-cards,
      body.v014 .seat-card.v027-expand-start .player-cards{
        min-height:0 !important;
        max-height:0 !important;
        height:0 !important;
        margin:0 !important;
        opacity:0 !important;
        overflow:hidden !important;
        pointer-events:none !important;
        transform:translateY(-7px) scale(.92) !important;
      }

      /* Keep READY / THINKING rail attached to the real bottom edge. */
      body.v014 .seat-card.v027-compact-seat > .v026-seat-status,
      body.v014 .seat-card.v027-expand-start > .v026-seat-status{
        top:calc(100% + 4px) !important;
      }

      /* ------------------------------------------------------------
         Main action buttons: clearer families, same poker logic.
         ------------------------------------------------------------ */
      body.v014 .action-grid{
        gap:7px !important;
      }

      body.v014 .action-grid .action-slot{
        min-height:52px !important;
        border-width:1px !important;
        box-shadow:inset 0 0 16px rgba(255,255,255,.018),0 5px 14px rgba(0,0,0,.18) !important;
        transition:transform .12s ease,border-color .15s ease,box-shadow .15s ease,background .15s ease !important;
      }

      body.v014 .action-grid .action-slot.check,
      body.v014 .action-grid .action-slot.fold{
        border-color:rgba(74,178,255,.48) !important;
        background:linear-gradient(180deg,rgba(5,25,47,.94),rgba(3,14,31,.98)) !important;
        color:#d8efff !important;
      }

      body.v014 .action-grid .action-slot.call{
        border-color:rgba(72,170,255,.68) !important;
        background:linear-gradient(180deg,rgba(7,44,83,.96),rgba(3,24,53,.99)) !important;
        color:#e9f6ff !important;
      }

      body.v014 .action-grid .action-slot.raise,
      body.v014 .action-grid .v016-primary-action.raise{
        border-color:rgba(205,82,255,.68) !important;
        background:linear-gradient(180deg,rgba(61,17,78,.96),rgba(31,8,48,.99)) !important;
        color:#f5dcff !important;
        box-shadow:0 0 13px rgba(194,66,255,.08),inset 0 0 17px rgba(218,107,255,.035) !important;
      }

      body.v014 .action-grid .action-slot.all-in{
        border-color:rgba(255,159,54,.68) !important;
        background:linear-gradient(180deg,rgba(66,32,6,.97),rgba(37,17,3,.99)) !important;
        color:#ffe4b7 !important;
      }

      body.v014 .action-grid .action-slot:not(:disabled):active{
        transform:scale(.975) !important;
      }

      /* ------------------------------------------------------------
         Bet presets: each size reads as its own control.
         ------------------------------------------------------------ */
      body.v014 .sizing-wrap{
        margin-top:7px !important;
        gap:7px !important;
      }

      body.v014 .quick-sizes{
        gap:7px !important;
      }

      body.v014 .quick-sizes button{
        position:relative !important;
        min-height:43px !important;
        padding:5px 3px !important;
        overflow:hidden !important;
        border-radius:12px !important;
        border-width:1px !important;
        background:rgba(5,12,28,.96) !important;
        box-shadow:inset 0 0 15px rgba(255,255,255,.018),0 4px 12px rgba(0,0,0,.16) !important;
        transition:transform .12s ease,box-shadow .15s ease,border-color .15s ease !important;
      }

      body.v014 .quick-sizes button::before{
        content:"";
        position:absolute;
        left:8px;
        right:8px;
        bottom:4px;
        height:2px;
        border-radius:99px;
        opacity:.7;
      }

      body.v014 .quick-sizes button:nth-child(1){border-color:rgba(60,181,255,.52) !important;color:#cdeeff !important}
      body.v014 .quick-sizes button:nth-child(1)::before{background:#3cb5ff}
      body.v014 .quick-sizes button:nth-child(2){border-color:rgba(99,117,255,.58) !important;color:#dce1ff !important}
      body.v014 .quick-sizes button:nth-child(2)::before{background:#6375ff}
      body.v014 .quick-sizes button:nth-child(3){border-color:rgba(200,73,255,.60) !important;color:#f1d8ff !important}
      body.v014 .quick-sizes button:nth-child(3)::before{background:#c849ff}
      body.v014 .quick-sizes button:nth-child(4){border-color:rgba(255,161,57,.62) !important;color:#ffe0b4 !important}
      body.v014 .quick-sizes button:nth-child(4)::before{background:#ffa139}

      body.v014 .quick-sizes button strong{
        display:block !important;
        font-size:13px !important;
        font-weight:950 !important;
        line-height:1 !important;
      }

      body.v014 .quick-sizes button small{
        display:block !important;
        margin-top:4px !important;
        font-size:8px !important;
        font-weight:800 !important;
        line-height:1 !important;
        color:rgba(229,238,255,.72) !important;
      }

      body.v014 .quick-sizes button.v027-size-selected{
        transform:translateY(-1px) !important;
        box-shadow:0 0 0 1px currentColor,0 0 14px rgba(111,108,255,.13),inset 0 0 18px rgba(255,255,255,.035) !important;
      }

      body.v014 .quick-sizes button:active{
        transform:scale(.97) !important;
      }

      /* ------------------------------------------------------------
         Amount editor: one coherent control instead of a raw input.
         ------------------------------------------------------------ */
      body.v014 .amount-row{
        position:relative !important;
        order:2 !important;
        display:grid !important;
        grid-template-columns:46px minmax(0,1fr) 46px !important;
        align-items:center !important;
        gap:6px !important;
        min-height:58px !important;
        margin-top:15px !important;
        padding:6px !important;
        border:1px solid rgba(90,116,176,.28) !important;
        border-radius:15px !important;
        background:linear-gradient(180deg,rgba(5,11,27,.97),rgba(2,7,18,.99)) !important;
        box-shadow:inset 0 0 22px rgba(78,91,170,.04),0 5px 16px rgba(0,0,0,.18) !important;
      }

      body.v014 .amount-row::before{
        content:"СУММА СТАВКИ" !important;
        position:absolute !important;
        top:-13px !important;
        left:50% !important;
        transform:translateX(-50%) !important;
        width:auto !important;
        color:#7382a2 !important;
        font-size:7px !important;
        font-weight:850 !important;
        letter-spacing:.11em !important;
        white-space:nowrap !important;
      }

      body.v014 .amount-step{
        width:46px !important;
        height:46px !important;
        border-radius:11px !important;
        border:1px solid rgba(201,71,255,.52) !important;
        background:linear-gradient(180deg,rgba(39,9,55,.95),rgba(20,4,34,.99)) !important;
        color:#f1baff !important;
        font-size:24px !important;
        font-weight:800 !important;
        box-shadow:inset 0 0 14px rgba(220,82,255,.035) !important;
      }

      body.v014 .amount-step:active{
        transform:scale(.94) !important;
      }

      body.v014 .amount-row input[type=number]{
        appearance:textfield !important;
        -moz-appearance:textfield !important;
        width:100% !important;
        height:46px !important;
        padding:0 !important;
        border:0 !important;
        outline:0 !important;
        border-radius:0 !important;
        background:transparent !important;
        box-shadow:none !important;
        color:#fff !important;
        font-size:25px !important;
        font-weight:950 !important;
        line-height:46px !important;
        text-align:center !important;
      }

      body.v014 .amount-row input[type=number]::-webkit-outer-spin-button,
      body.v014 .amount-row input[type=number]::-webkit-inner-spin-button{
        -webkit-appearance:none !important;
        margin:0 !important;
      }

      body.v014 .amount-row > span{
        display:none !important;
      }

      body.v014 .bet-slider-row{
        margin-top:0 !important;
        padding:0 3px !important;
        gap:7px !important;
      }

      body.v014 .bet-slider-row span{
        min-width:42px !important;
        font-size:7px !important;
        font-weight:800 !important;
        color:#687895 !important;
      }

      body.v014 #amountSlider{
        height:28px !important;
      }
    }
  `;
  document.head.appendChild(style);

  decorateSeats();
})();
