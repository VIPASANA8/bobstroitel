(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v036-poker8-v2-prehand-pass-style";
  style.textContent = `
    @media (max-width:780px){
      /* Keep the approved 6-max ring; only give hero a little more air above the rim. */
      body.v014.poker8-v2-sixmax{
        --seat-0-y:85.2%!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{
        top:85.2%!important;
      }

      /* Pre-hand control should be obvious without becoming the visual focal point. */
      body.v014.poker8-v2-sixmax .v028-center-ready{
        top:55.5%!important;
        width:146px!important;
        gap:5px!important;
      }
      body.v014.poker8-v2-sixmax .v028-center-status{
        min-width:92px!important;
        height:19px!important;
        padding:0 7px!important;
        font-size:8px!important;
        letter-spacing:.045em!important;
        opacity:.86!important;
      }
      body.v014.poker8-v2-sixmax .v028-center-ready-button{
        width:138px!important;
        height:38px!important;
        border-radius:11px!important;
        font-size:11px!important;
        box-shadow:0 0 10px rgba(47,179,255,.10),inset 0 0 12px rgba(65,197,255,.035)!important;
      }

      /* v0.14 stretched the action panel to the viewport bottom. On the real 402×874
         screenshot this leaves ~90px of dead black panel after the slider. Let the
         controls use their intrinsic height and end as a deliberate dock. */
      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        min-height:0!important;
        height:auto!important;
        margin-bottom:0!important;
        padding-bottom:calc(12px + env(safe-area-inset-bottom))!important;
        border-bottom:1px solid rgba(57,151,158,.15)!important;
        border-radius:0 0 14px 14px!important;
      }

      body.v014.poker8-v2-sixmax .app-shell{
        min-height:0!important;
      }

      /* Make the amount slider feel like the end of the dock instead of floating
         above a large empty panel. */
      body.v014.poker8-v2-sixmax .bet-slider-row{
        margin-bottom:1px!important;
      }
      body.v014.poker8-v2-sixmax #amountSlider{
        height:27px!important;
      }
      body.v014.poker8-v2-sixmax .bet-slider-row span{
        line-height:1.05!important;
        white-space:nowrap!important;
      }
    }

    @media (max-width:370px){
      body.v014.poker8-v2-sixmax{
        --seat-0-y:85.8%!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{top:85.8%!important}
    }
  `;
  document.head.appendChild(style);
})();
