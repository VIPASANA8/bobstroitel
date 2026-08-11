(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v034-poker8-v2-layout-lock-style";
  style.textContent = `
    @media (max-width:780px){
      body.v014.poker8-v2-sixmax{
        --seat-0-x:50% !important;
        --seat-0-y:88.8% !important;
        --seat-1-x:15% !important;
        --seat-1-y:66.5% !important;
        --seat-2-x:12% !important;
        --seat-2-y:28.5% !important;
        --seat-3-x:50% !important;
        --seat-3-y:10.5% !important;
        --seat-4-x:88% !important;
        --seat-4-y:28.5% !important;
        --seat-5-x:85% !important;
        --seat-5-y:66.5% !important;
        --pot-y:30% !important;
        --pot-chips-y:39.5% !important;
        --board-y:49.5% !important;
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{left:50%!important;top:88.8%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:15%!important;top:66.5%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:12%!important;top:28.5%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{left:50%!important;top:10.5%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:88%!important;top:28.5%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:85%!important;top:66.5%!important}

      body.v014.poker8-v2-sixmax .pot-total{top:30%!important}
      body.v014.poker8-v2-sixmax .pot-chips{top:39.5%!important}
      body.v014.poker8-v2-sixmax .board-cards{top:49.5%!important}

      body.v014.poker8-v2-sixmax .seat.v032-hidden-seat{
        display:none!important;
        visibility:hidden!important;
        pointer-events:none!important;
      }

      body.v014.poker8-v2-sixmax .seat:not(.v032-hidden-seat){
        padding-top:38px!important;
        margin-top:-38px!important;
        pointer-events:none;
      }
      body.v014.poker8-v2-sixmax .seat:not(.v032-hidden-seat) .seat-card,
      body.v014.poker8-v2-sixmax .seat:not(.v032-hidden-seat) .seat-empty,
      body.v014.poker8-v2-sixmax .seat:not(.v032-hidden-seat) button{
        pointer-events:auto;
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{
        padding-top:55px!important;
        margin-top:-55px!important;
      }
    }

    @media (max-width:370px){
      body.v014.poker8-v2-sixmax{
        --seat-0-y:89.2% !important;
        --seat-1-x:16% !important;
        --seat-2-x:13% !important;
        --seat-4-x:87% !important;
        --seat-5-x:84% !important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{top:89.2%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:16%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:13%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:87%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:84%!important}
    }
  `;
  document.head.appendChild(style);

  if (!document.querySelector('script[data-v035-poker8-v2-pixel-pass]')) {
    const v035 = document.createElement("script");
    v035.src = "/static/v035-poker8-v2-pixel-pass.js";
    v035.dataset.v035Poker8V2PixelPass = "1";
    v035.addEventListener("load", () => {
      if (!document.querySelector('script[data-v036-poker8-v2-prehand-pass]')) {
        const v036 = document.createElement("script");
        v036.src = "/static/v036-poker8-v2-prehand-pass.js";
        v036.dataset.v036Poker8V2PrehandPass = "1";
        document.body.appendChild(v036);
      }
    }, { once:true });
    document.body.appendChild(v035);
  } else if (!document.querySelector('script[data-v036-poker8-v2-prehand-pass]')) {
    const v036 = document.createElement("script");
    v036.src = "/static/v036-poker8-v2-prehand-pass.js";
    v036.dataset.v036Poker8V2PrehandPass = "1";
    document.body.appendChild(v036);
  }
})();
