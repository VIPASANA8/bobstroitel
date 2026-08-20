(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v036-poker8-v2-prehand-pass-style";
  style.textContent = `
    /* Was @media (max-width:780px) -- see v032. */
    @media all{
      /* Keep the approved 6-max ring; only give hero a little more air above the rim. */
      body.v014.poker8-v2-sixmax{
        --seat-0-y:85.2%!important;
        min-height:100dvh!important;
        background:linear-gradient(180deg,#080705 0,#020404 68%,#010304 100%)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{
        top:85.2%!important;
      }

      /* Pre-hand control should be obvious without becoming the visual focal point. */
      body.v014.poker8-v2-sixmax .v028-center-ready{
        top:54.8%!important;
        width:146px!important;
        gap:5px!important;
      }
      body.v014.poker8-v2-sixmax .v028-center-status{
        min-width:92px!important;
        height:19px!important;
        padding:0 7px!important;
        font-size:8px!important;
        letter-spacing:.045em!important;
        opacity:.82!important;
      }
      body.v014.poker8-v2-sixmax .v028-center-ready-button{
        width:138px!important;
        height:38px!important;
        border-radius:11px!important;
        font-size:11px!important;
        box-shadow:0 0 10px rgba(47,179,255,.10),inset 0 0 12px rgba(65,197,255,.035)!important;
      }

      /* Keep intrinsic control height, but extend its visual surface to the phone bottom.
         This removes the dead black tail without making the controls themselves taller. */
      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        position:relative!important;
        min-height:0!important;
        height:auto!important;
        margin-bottom:0!important;
        padding-bottom:calc(12px + env(safe-area-inset-bottom))!important;
        border-bottom:1px solid rgba(57,151,158,.15)!important;
        border-radius:0!important;
        overflow:visible!important;
      }
      body.v014.poker8-v2-sixmax .action-panel::after{
        content:"";
        position:absolute;
        z-index:-1;
        left:0;
        right:0;
        top:calc(100% - 1px);
        height:180px;
        pointer-events:none;
        background:
          radial-gradient(circle at 50% 0,rgba(24,95,84,.055),transparent 48%),
          linear-gradient(180deg,rgba(1,4,5,1),rgba(1,3,4,1));
        border-left:1px solid rgba(40,76,80,.18);
        border-right:1px solid rgba(40,76,80,.18);
      }

      body.v014.poker8-v2-sixmax .app-shell{
        min-height:100dvh!important;
        background:linear-gradient(180deg,transparent 0,transparent 72%,rgba(1,3,4,.98) 72%,#010304 100%)!important;
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

  if (!document.querySelector('script[data-v037-poker8-v2-reference-table]')) {
    const v037 = document.createElement("script");
    v037.src = "/static/v037-poker8-v2-reference-table.js";
    v037.setAttribute("data-v037-poker8-v2-reference-table", "");
    document.body.appendChild(v037);
  }
})();
