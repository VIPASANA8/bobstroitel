(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v019-center-polish";
  style.textContent = `
    @media (max-width:780px){
      /* v0.19: center order is POT -> BOARD -> POT CHIPS. */
      body.v014{
        --board-y:40.5% !important;
        --pot-chips-y:52.0% !important;
      }

      /* Keep wager amount pills, but remove every background/plate around the chips themselves. */
      body.v014 .wager-layer .bet-marker,
      body.v014 .wager-layer .bet-marker > .chip-cluster,
      body.v014 .wager-layer .bet-marker .chip-column,
      body.v014 .pot-chips,
      body.v014 .pot-chips > .chip-cluster,
      body.v014 .pot-chips .chip-column{
        background:transparent !important;
        border:0 !important;
        outline:0 !important;
        box-shadow:none !important;
        backdrop-filter:none !important;
      }

      body.v014 .wager-layer .bet-marker > .chip-cluster,
      body.v014 .pot-chips > .chip-cluster{
        padding:0 !important;
        border-radius:0 !important;
        filter:none !important;
      }

      body.v014 .wager-layer .bet-marker.v016-latest-wager > .chip-cluster{
        filter:none !important;
        box-shadow:none !important;
      }

      /* Pot chip container itself must be visually invisible. */
      body.v014 .pot-chips{
        filter:none !important;
      }

      /* One centered axis for BANK and its amount. */
      body.v014 .pot-total{
        left:50% !important;
        transform:translateX(-50%) !important;
        width:150px !important;
        min-width:150px !important;
        padding:0 !important;
        display:flex !important;
        flex-direction:column !important;
        align-items:center !important;
        justify-content:center !important;
        gap:3px !important;
        text-align:center !important;
      }

      body.v014 .pot-total .pot-total-label,
      body.v014 .pot-total #pot{
        display:block !important;
        width:100% !important;
        margin:0 !important;
        padding:0 !important;
        text-align:center !important;
      }

      body.v014 .pot-total .pot-total-label{
        line-height:1 !important;
      }

      body.v014 .pot-total #pot{
        line-height:1.05 !important;
      }
    }
  `;
  document.head.appendChild(style);
})();
