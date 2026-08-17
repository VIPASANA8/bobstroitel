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
      /* The highlight lives on the avatar and the plate themselves -- their own
         edge, traced by their own shape -- not a separate ring floating around
         the seat. box-shadow can't be animated here (an earlier !important base
         rule always wins over a keyframe), so the pulse rides on drop-shadow:
         it follows each element's alpha silhouette, a circle for the avatar and
         a rounded rect for the plate, instead of a detached halo. */
      body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .player-avatar{
        border-color:#d8fff7!important;
        box-shadow:0 0 0 3px rgba(1,5,5,.93),0 0 13px hsla(var(--seat-accent),100%,70%,.94),inset 0 -10px 18px rgba(0,0,0,.50)!important;
        animation:v041AvatarPulse 1.6s ease-in-out infinite;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .seat-identity{
        border-color:#c9fff2!important;
        background:linear-gradient(120deg,hsla(var(--seat-accent),55%,16%,.97),rgba(39,3,35,.97) 54%,rgba(1,10,9,.98))!important;
        box-shadow:0 0 0 1px hsla(var(--seat-accent),100%,72%,.24),0 0 18px hsla(var(--seat-accent),100%,66%,.62)!important;
        animation:v041PlatePulse 1.6s ease-in-out infinite;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .seat-name::after{
        content:"ХОД";display:block;margin-top:3px;color:#dffffa;font-size:7px;font-weight:950;letter-spacing:.14em;text-shadow:0 0 6px currentColor;
      }
      @keyframes v041AvatarPulse{0%,100%{filter:drop-shadow(0 0 2px hsla(var(--seat-accent),100%,70%,.55))}50%{filter:drop-shadow(0 0 9px hsla(var(--seat-accent),100%,70%,1))}}
      @keyframes v041PlatePulse{0%,100%{filter:drop-shadow(0 0 1px hsla(var(--seat-accent),100%,68%,.5))}50%{filter:drop-shadow(0 0 6px hsla(var(--seat-accent),100%,68%,.95))}}
      @media (prefers-reduced-motion:reduce){
        body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .player-avatar,
        body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .seat-identity{animation:none!important;}
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
