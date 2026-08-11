(() => {
  "use strict";

  const MOBILE = "(max-width: 780px)";
  const isV2 = () => window.matchMedia?.(MOBILE)?.matches && document.body.classList.contains("poker8-v2-sixmax");

  function toEnglishBb(text) {
    return String(text || "")
      .replace(/ББ/g, "BB")
      .replace(/Банк/gi, "POT")
      .replace(/МИН/gi, "MIN")
      .replace(/МАКС/gi, "MAX");
  }

  function setTextIfChanged(node, value) {
    if (!node) return false;
    const next = String(value ?? "");
    if (node.textContent === next) return false;
    node.textContent = next;
    return true;
  }

  function syncPixelPassText() {
    if (!isV2()) return;

    const heroCard = document.querySelector('.seat[data-visual-seat="0"] .seat-card.seat-human');
    if (heroCard) {
      heroCard.classList.add("v035-hero-card");
      const avatar = heroCard.querySelector(".player-avatar span");
      if (avatar && (!window.game || window.game?.terminal)) setTextIfChanged(avatar, "ВЫ");
    }

    document.querySelectorAll("#actionButtons button").forEach((button) => {
      setTextIfChanged(button, toEnglishBb(button.textContent));
    });

    document.querySelectorAll(".quick-sizes button").forEach((button) => {
      if (button.dataset.sizing === "1.00") setTextIfChanged(button, "POT");
    });

    setTextIfChanged(document.querySelector("#sizingWrap > label"), "BET SIZE");

    const minLabel = document.getElementById("sliderMinLabel");
    const maxLabel = document.getElementById("sliderMaxLabel");
    if (minLabel) setTextIfChanged(minLabel, toEnglishBb(minLabel.textContent));
    if (maxLabel) setTextIfChanged(maxLabel, toEnglishBb(maxLabel.textContent));
  }

  const previousSync = window.syncComponentUi;
  window.syncComponentUi = function syncPoker8V2PixelPass(gameState, tableState) {
    previousSync?.(gameState, tableState);
    requestAnimationFrame(syncPixelPassText);
  };

  let syncQueued = false;
  const queueSync = () => {
    if (!isV2() || syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(() => {
      syncQueued = false;
      syncPixelPassText();
    });
  };

  const observer = new MutationObserver(queueSync);

  function start() {
    observer.observe(document.querySelector(".app-shell") || document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class"],
    });
    syncPixelPassText();
  }

  const style = document.createElement("style");
  style.id = "v035-poker8-v2-pixel-pass-style";
  style.textContent = `
    @media (max-width:780px){
      body.v014.poker8-v2-sixmax{
        --table-stage-h:clamp(500px,65dvh,522px)!important;
        --seat-0-x:50%!important; --seat-0-y:86.5%!important;
        --seat-1-x:15.5%!important; --seat-1-y:65%!important;
        --seat-2-x:13%!important; --seat-2-y:31%!important;
        --seat-3-x:50%!important; --seat-3-y:15.5%!important;
        --seat-4-x:87%!important; --seat-4-y:31%!important;
        --seat-5-x:84.5%!important; --seat-5-y:65%!important;
        --pot-y:31%!important; --pot-chips-y:39.5%!important; --board-y:49%!important;
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{left:50%!important;top:86.5%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:15.5%!important;top:65%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:13%!important;top:31%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="3"]{left:50%!important;top:15.5%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:87%!important;top:31%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:84.5%!important;top:65%!important}

      body.v014.poker8-v2-sixmax .table-frame{
        height:var(--table-stage-h)!important;
        min-height:var(--table-stage-h)!important;
        padding:0 7px 1px!important;
        background:
          radial-gradient(ellipse at 50% 34%,rgba(111,60,22,.18),transparent 56%),
          linear-gradient(180deg,#100905,#070504 78%,#030303)!important;
      }

      body.v014.poker8-v2-sixmax .felt{
        border-width:11px!important;
        border-radius:47% / 34%!important;
        background:
          radial-gradient(circle at 32% 25%,rgba(45,118,76,.13),transparent 24%) padding-box,
          radial-gradient(circle at 68% 72%,rgba(0,15,9,.20),transparent 28%) padding-box,
          linear-gradient(145deg,#06462c,#033a24 58%,#022d1d) padding-box,
          linear-gradient(90deg,#231005 0,#6f3515 16%,#331506 31%,#955524 50%,#301405 68%,#74401b 84%,#241005 100%) border-box!important;
        outline:1px solid rgba(74,255,205,.58)!important;
        box-shadow:
          inset 0 0 72px rgba(0,0,0,.42),
          inset 0 0 0 2px rgba(60,255,196,.10),
          0 0 0 2px rgba(8,6,5,.92),
          0 0 12px rgba(41,242,193,.20),
          0 0 26px rgba(34,242,191,.10)!important;
      }

      body.v014.poker8-v2-sixmax .felt::before{
        inset:7px!important;
        border-color:rgba(58,255,202,.58)!important;
        box-shadow:0 0 8px rgba(44,255,205,.20),inset 0 0 8px rgba(44,255,205,.08)!important;
      }

      body.v014.poker8-v2-sixmax .seat-identity{
        position:relative!important;
        z-index:4!important;
      }
      body.v014.poker8-v2-sixmax .seat-name{
        color:#f5f7f6!important;
        font-size:10px!important;
        font-weight:900!important;
        text-shadow:0 1px 3px rgba(0,0,0,.9)!important;
      }
      body.v014.poker8-v2-sixmax .seat-stack{
        color:#54efa9!important;
        font-size:12px!important;
        font-weight:950!important;
        text-shadow:0 0 8px rgba(75,238,170,.16)!important;
      }
      body.v014.poker8-v2-sixmax .bot-level{
        color:#899690!important;
        font-size:7px!important;
        font-weight:800!important;
      }
      body.v014.poker8-v2-sixmax .position-chip{
        color:#c8d4cf!important;
        background:rgba(12,17,16,.92)!important;
        border:1px solid rgba(115,142,133,.24)!important;
      }

      body.v014.poker8-v2-sixmax .seat{width:94px!important}
      body.v014.poker8-v2-sixmax .seat-card{
        min-height:70px!important;
        padding:20px 7px 7px!important;
        border-radius:14px!important;
        background:linear-gradient(180deg,rgba(9,10,10,.96),rgba(2,4,4,.99))!important;
      }
      body.v014.poker8-v2-sixmax .player-avatar{
        width:43px!important;height:43px!important;
        color:#f2fbf7!important;
        box-shadow:0 0 0 1px rgba(255,255,255,.06),0 0 12px hsla(var(--avatar-hue),90%,58%,.28)!important;
      }
      body.v014.poker8-v2-sixmax .player-avatar span{
        position:relative;z-index:2;font-size:13px!important;font-weight:950!important;
      }

      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"]{width:132px!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-card{
        min-height:76px!important;
        padding:22px 9px 8px!important;
        border-color:rgba(49,178,255,.82)!important;
        box-shadow:0 0 0 1px rgba(49,178,255,.14),0 0 16px rgba(46,174,255,.20),0 10px 24px rgba(0,0,0,.46)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{color:#35bfff!important;font-size:14px!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .player-avatar{
        width:48px!important;height:48px!important;
        border-color:rgba(52,185,255,.90)!important;
        box-shadow:0 0 0 1px rgba(52,185,255,.18),0 0 18px rgba(43,177,255,.30)!important;
      }

      body.v014.poker8-v2-sixmax .seat-card > .v024-ready-badge.v026-seat-status{
        top:calc(100% + 3px)!important;
        min-width:42px!important;
        height:14px!important;
        padding:0 5px!important;
        font-size:6px!important;
        opacity:.72!important;
      }

      body.v014.poker8-v2-sixmax .pot-total{
        top:31%!important;
        min-width:112px!important;
        padding:5px 12px!important;
        border:1px solid rgba(67,225,170,.18)!important;
        border-radius:10px!important;
        background:rgba(2,28,18,.82)!important;
        box-shadow:0 6px 18px rgba(0,0,0,.22),inset 0 0 14px rgba(58,220,165,.025)!important;
      }
      body.v014.poker8-v2-sixmax .pot-total-label{color:#9bc5b5!important;font-size:8px!important;letter-spacing:.10em!important}
      body.v014.poker8-v2-sixmax .pot-total strong{color:#fff!important;font-size:21px!important;text-shadow:0 0 9px rgba(72,239,180,.16)!important}

      body.v014.poker8-v2-sixmax .v028-center-ready{top:56%!important;width:158px!important;gap:7px!important}
      body.v014.poker8-v2-sixmax .v028-center-status{
        min-width:105px!important;height:22px!important;padding:0 10px!important;font-size:9px!important;
        background:transparent!important;border:0!important;box-shadow:none!important;
      }
      body.v014.poker8-v2-sixmax .v028-center-status i{width:6px!important;height:6px!important;flex-basis:6px!important}
      body.v014.poker8-v2-sixmax .v028-center-ready-button{
        width:150px!important;height:42px!important;border-radius:12px!important;
        border-color:rgba(47,178,255,.72)!important;
        background:linear-gradient(180deg,rgba(5,42,67,.98),rgba(2,21,38,.99))!important;
        box-shadow:0 0 14px rgba(47,179,255,.14),inset 0 0 15px rgba(65,197,255,.04)!important;
      }

      body.v014.poker8-v2-sixmax .action-panel,
      body.v014.poker8-v2-sixmax.local-player-active .sidebar .action-panel,
      body.v014.poker8-v2-sixmax.human-turn .sidebar .action-panel{
        padding:7px 8px calc(8px + env(safe-area-inset-bottom))!important;
        border-top:1px solid rgba(65,216,205,.20)!important;
        background:linear-gradient(180deg,rgba(3,7,8,.99),rgba(1,3,4,1))!important;
        box-shadow:0 -10px 26px rgba(0,0,0,.30)!important;
      }
      body.v014.poker8-v2-sixmax .action-grid{gap:6px!important}
      body.v014.poker8-v2-sixmax .action-grid .action-slot{min-height:46px!important;border-radius:11px!important;font-size:10px!important}
      body.v014.poker8-v2-sixmax .quick-sizes{gap:6px!important}
      body.v014.poker8-v2-sixmax .quick-sizes button{min-height:38px!important;border-radius:10px!important}
      body.v014.poker8-v2-sixmax .quick-sizes button strong{font-size:11px!important}
      body.v014.poker8-v2-sixmax .amount-row{min-height:50px!important;margin-top:14px!important;padding:4px!important;border-radius:13px!important}
      body.v014.poker8-v2-sixmax .amount-step{width:40px!important;height:40px!important}
      body.v014.poker8-v2-sixmax .amount-row input[type=number]{height:40px!important;font-size:22px!important}
      body.v014.poker8-v2-sixmax .amount-row::before{content:"BET SIZE"!important;color:#6f8f89!important;font-size:6px!important;letter-spacing:.13em!important}
      body.v014.poker8-v2-sixmax .bet-slider-row{padding:0 5px!important}
      body.v014.poker8-v2-sixmax .bet-slider-row span{font-size:6px!important;color:#728680!important}
      body.v014.poker8-v2-sixmax .mobile-auto-action{display:none!important}

      body.v014.poker8-v2-sixmax .board-cards{top:49%!important;gap:4px!important}
      body.v014.poker8-v2-sixmax .board-cards .card{width:45px!important;height:64px!important;font-size:16px!important}
    }

    @media (max-width:370px){
      body.v014.poker8-v2-sixmax{
        --table-stage-h:500px!important;
        --seat-1-x:16%!important;--seat-2-x:14%!important;--seat-4-x:86%!important;--seat-5-x:84%!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="1"]{left:16%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="2"]{left:14%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="4"]{left:86%!important}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="5"]{left:84%!important}
    }
  `;
  document.head.appendChild(style);

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();