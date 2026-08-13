(() => {
  "use strict";

  const mq = window.matchMedia?.("(max-width: 780px)");
  const isV2 = () => Boolean(mq?.matches && document.body.classList.contains("poker8-v2-sixmax"));

  const ACTION_NAMES = {
    fold: "FOLD",
    check: "CHECK",
    call: "CALL",
    bet: "BET",
    raise: "RAISE",
    aggressive: "RAISE",
    all_in: "ALL-IN",
  };

  function compactNumber(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return null;
    const abs = Math.abs(n);
    if (abs < 10_000) {
      return n.toLocaleString("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: n < 100 ? 1 : 0,
      });
    }
    if (abs < 1_000_000) {
      const digits = abs < 100_000 ? 1 : 0;
      return `${(n / 1_000).toFixed(digits).replace(/\.0$/, "")}K`;
    }
    const digits = abs < 10_000_000 ? 1 : 0;
    return `${(n / 1_000_000).toFixed(digits).replace(/\.0$/, "")}M`;
  }

  function translateActionButtons() {
    if (!isV2()) return;
    document.querySelectorAll("#actionButtons button[data-action-key]").forEach((button) => {
      const key = button.dataset.actionKey || "";
      const label = ACTION_NAMES[key];
      if (!label) return;

      const raw = (button.textContent || "").trim();
      const lines = raw.split(/\n+/).map((line) => line.trim()).filter(Boolean);
      const amountLine = lines.find((line, index) => index > 0 && /\d/.test(line)) || "";
      const next = amountLine ? `${label}\n${amountLine}` : label;
      if (button.textContent !== next) button.textContent = next;
      button.dataset.v033English = "1";
    });
  }

  function compactSeatStacks() {
    if (!isV2()) return;
    document.querySelectorAll(".seat:not(.v032-hidden-seat) .seat-stack").forEach((node) => {
      if (!node.dataset.v033RawStack) node.dataset.v033RawStack = node.textContent || "";
      const source = node.dataset.v033RawStack || node.textContent || "";
      const match = source.replace(/\s/g, "").replace(",", ".").match(/-?\d+(?:\.\d+)?/);
      if (!match) return;
      const formatted = compactNumber(Number(match[0]));
      if (formatted != null) node.textContent = formatted;
    });
  }

  function syncFoldPresentation() {
    if (!isV2()) return;
    document.querySelectorAll(".seat-card").forEach((card) => {
      const folded = card.classList.contains("v032-folded") || card.classList.contains("folded");
      const status = card.querySelector(":scope > .player-status.v026-seat-status");
      if (status) status.classList.toggle("v033-fold-status-hidden", folded);
    });
  }

  function syncAll() {
    translateActionButtons();
    compactSeatStacks();
    syncFoldPresentation();
  }

  const previousSyncComponentUi = window.syncComponentUi;
  window.syncComponentUi = function syncPoker8V2Polish(gameState, tableState) {
    previousSyncComponentUi?.(gameState, tableState);
    requestAnimationFrame(syncAll);
  };

  const observer = new MutationObserver(() => {
    if (!isV2()) return;
    requestAnimationFrame(syncAll);
  });

  function startObserver() {
    const root = document.querySelector(".app-shell") || document.body;
    observer.observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["class"] });
    syncAll();
  }

  const style = document.createElement("style");
  style.id = "v033-poker8-v2-polish-style";
  style.textContent = `
    @media (max-width:780px){
      body.poker8-v2-sixmax .seat,
      body.poker8-v2-sixmax .seat-card{
        overflow:visible!important;
      }

      body.poker8-v2-sixmax .seat-card{
        isolation:isolate!important;
      }

      body.poker8-v2-sixmax .player-cards{
        z-index:0!important;
      }

      body.poker8-v2-sixmax .avatar-wrap,
      body.poker8-v2-sixmax .seat-topline,
      body.poker8-v2-sixmax .seat-stack,
      body.poker8-v2-sixmax .seat-meta,
      body.poker8-v2-sixmax .position-chip,
      body.poker8-v2-sixmax .dealer-button{
        position:relative;
        z-index:3!important;
      }

      body.poker8-v2-sixmax .seat-card::before{
        content:"";
        position:absolute;
        inset:0;
        z-index:1;
        border-radius:inherit;
        background:linear-gradient(180deg,rgba(8,8,10,.96),rgba(2,3,5,.99));
        pointer-events:none;
      }

      body.poker8-v2-sixmax .seat-card.v032-folded > .player-status.v026-seat-status,
      body.poker8-v2-sixmax .seat-card.v032-folded > .player-status.status-fold,
      body.poker8-v2-sixmax .v033-fold-status-hidden{
        opacity:0!important;
        transform:translateX(-50%) translateY(-4px)!important;
        pointer-events:none!important;
      }

      body.poker8-v2-sixmax .seat-card > .player-status.v026-seat-status{
        transition:opacity .18s ease,transform .18s ease!important;
      }

      body.poker8-v2-sixmax .seat-card.v032-folded .player-cards{
        opacity:0!important;
        transform:translateX(-50%) translateY(-10px) scale(.92)!important;
      }

      body.poker8-v2-sixmax #actionButtons button[data-v033-english="1"]{
        white-space:pre-line!important;
        letter-spacing:.025em!important;
      }

      body.poker8-v2-sixmax .seat-stack{
        font-variant-numeric:tabular-nums!important;
        white-space:nowrap!important;
      }

      body.poker8-v2-sixmax .dealer-button{
        width:22px!important;
        height:22px!important;
        border:1px solid rgba(242,242,232,.80)!important;
        background:radial-gradient(circle at 36% 28%,#fff,#d8d8cd 52%,#8b8d84 100%)!important;
        color:#151815!important;
        box-shadow:0 2px 7px rgba(0,0,0,.55),0 0 7px rgba(255,255,240,.16)!important;
        font-weight:950!important;
      }

      body.poker8-v2-sixmax .bet-marker span{
        font-size:9px!important;
        font-weight:900!important;
        color:#f5fff9!important;
        text-shadow:0 2px 5px rgba(0,0,0,.95)!important;
      }
    }
  `;
  document.head.appendChild(style);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver, { once: true });
  } else {
    startObserver();
  }
})();
