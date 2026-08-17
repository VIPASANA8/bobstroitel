(() => {
  "use strict";

  const MOBILE = "(max-width: 780px)";
  const isMobileV2 = () => window.matchMedia?.(MOBILE)?.matches
    && document.body.classList.contains("poker8-v2-sixmax");

  const style = document.createElement("style");
  style.id = "v041-poker8-v2-turn-clarity-style";
  style.textContent = `
    @media (max-width:780px){
      body.v014.poker8-v2-sixmax.p8-turn-active .felt{
        filter:drop-shadow(0 0 8px rgba(65,255,214,.16))!important;
      }
      body.v014.poker8-v2-sixmax .seat.p8-seat-turn{
        isolation:isolate;
      }
      body.v014.poker8-v2-sixmax .seat.p8-seat-turn::after{
        content:"";position:absolute;z-index:1;inset:-18px -13px -23px;
        border-radius:50%;pointer-events:none;opacity:.94;
        background:
          conic-gradient(from 0deg at 50% 50%,transparent 0 9%,hsla(var(--seat-accent),100%,68%,.92) 15%,rgba(255,62,201,.84) 25%,transparent 38% 58%,hsla(var(--seat-accent),100%,70%,.95) 73%,transparent 86% 100%),
          radial-gradient(ellipse at 50% 46%,hsla(var(--seat-accent),100%,58%,.30),transparent 66%);
        filter:blur(4px) saturate(1.35);mix-blend-mode:screen;
        animation:v041TurnOrbit 2.7s linear infinite;
      }
      body.v014.poker8-v2-sixmax .seat-card.p8-turn-gradient .player-avatar{
        border-color:#d8fff7!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.93),0 0 13px hsla(var(--seat-accent),100%,70%,.94),0 0 30px rgba(255,58,207,.72),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.p8-turn-gradient .seat-identity{
        border-color:#c9fff2!important;
        background:linear-gradient(120deg,hsla(var(--seat-accent),55%,16%,.97),rgba(39,3,35,.97) 54%,rgba(1,10,9,.98))!important;
        box-shadow:0 0 0 1px hsla(var(--seat-accent),100%,72%,.24),0 0 18px hsla(var(--seat-accent),100%,66%,.62),0 0 25px rgba(255,61,207,.36)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card.p8-turn-gradient .seat-name::after{
        content:"ХОД";display:block;margin-top:3px;color:#dffffa;font-size:7px;font-weight:950;letter-spacing:.14em;text-shadow:0 0 6px currentColor;
      }
      @keyframes v041TurnOrbit{to{transform:rotate(360deg) scale(1.035)}}
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .seat.p8-seat-turn::after{animation:none!important;opacity:.72;}
      }
    }
  `;
  document.head.appendChild(style);

  let syncQueued = false;
  function syncTurnClarity() {
    syncQueued = false;
    if (!isMobileV2()) return;
    const activePlayerId = game && !game.terminal ? game.acting_player : null;
    let activeSeat = null;
    document.querySelectorAll(".seat[data-seat]").forEach(seat => {
      const card = seat.querySelector(".seat-card");
      if (!card) return;
      const player = Object.values(game?.players || {}).find(item => Number(item?.seat) === Number(seat.dataset.seat));
      const isActive = Boolean(activePlayerId && player?.id === activePlayerId && !player.folded && !player.all_in);
      card.classList.toggle("p8-turn-gradient", isActive);
      seat.classList.toggle("p8-seat-turn", isActive);
      if (isActive) activeSeat = seat;
    });
    document.body.classList.toggle("p8-turn-active", Boolean(activeSeat));
  }

  function queueSync() {
    if (syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(syncTurnClarity);
  }

  new MutationObserver(queueSync).observe(document.body, { childList:true, subtree:true });
  window.addEventListener("resize", queueSync, { passive:true });
  window.setInterval(queueSync, 450);
  queueSync();
})();
