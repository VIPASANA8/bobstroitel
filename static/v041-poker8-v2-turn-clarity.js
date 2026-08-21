(() => {
  "use strict";

  // The class is the switch now: it is added at every width, so the media
  // half of this test only kept desktop out of everything below.
  const isMobileV2 = () => document.body.classList.contains("poker8-v2-sixmax");

  const style = document.createElement("style");
  style.id = "v041-poker8-v2-turn-clarity-style";
  style.textContent = `
    /* Was @media (max-width:780px). The v2 table is the table now, at every
       width; desktop geometry is tuned in v039. */
    @media all{
      body.v014.poker8-v2-sixmax.p8-turn-active .felt{
        filter:drop-shadow(0 0 10px color-mix(in srgb,var(--turn) 20%,transparent))!important;
      }
      /* No pulse. It rode on the avatar and the plate, and those elements are
         rebuilt on every render -- twice in five seconds on a live table --
         so the animation restarted from frame zero each time and the glow
         visibly jumped. A steady ring says the same thing and holds still,
         and with the felt down from 66 glowing elements to three it does not
         need motion to be found.

         One colour for the turn, the same on every seat. It used to be
         --seat-accent, so the signal was cyan on seat 0 and violet on seat 5 --
         a cue you cannot learn because it never looks the same twice. It is
         --turn now, matching the timer ring, and it is the only magenta left
         on the felt.

         The highlight lives on the avatar and the plate themselves -- their own
         edge, traced by their own shape -- not a separate ring floating around
         the seat. box-shadow can't be animated here (an earlier !important base
         rule always wins over a keyframe), so the pulse rides on drop-shadow:
         it follows each element's alpha silhouette, a circle for the avatar and
         a rounded rect for the plate, instead of a detached halo. */
      body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .player-avatar{
        border-color:var(--turn-ring)!important;
        box-shadow:0 0 0 3px rgba(0,0,0,.93),0 0 14px color-mix(in srgb,var(--turn-ring) 82%,transparent),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat .seat-card.p8-turn-gradient .seat-identity{
        border-color:var(--turn)!important;
        background:linear-gradient(120deg,color-mix(in srgb,var(--turn) 26%,#07100f),rgba(1,3,10,.98))!important;
        box-shadow:0 0 0 1px color-mix(in srgb,var(--turn) 40%,transparent),0 0 18px color-mix(in srgb,var(--turn) 62%,transparent)!important;
      }
      /* Glow is an accent, and an accent that is everywhere is decoration.
         Measured with nobody to act: 66 elements were glowing -- every chip,
         every card, every avatar, every seat plate. So when the turn glow
         arrived it was the sixty-seventh, and it read as more of the same.
         At rest these keep their edge and their shadow and lose the halo;
         the acting seat, the timer and the winner keep theirs. */
      body.v014.poker8-v2-sixmax .poker-chip,
      body.v014.poker8-v2-sixmax .chip-column,
      body.v014.poker8-v2-sixmax .chip-cluster,
      body.v014.poker8-v2-sixmax .seat-card:not(.p8-turn-gradient) .player-avatar,
      body.v014.poker8-v2-sixmax .seat-card:not(.p8-turn-gradient) .seat-identity{
        filter:none!important;
      }
      body.v014.poker8-v2-sixmax .seat-card:not(.p8-turn-gradient) .seat-identity{
        box-shadow:0 2px 6px rgba(0,0,0,.45)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card:not(.p8-turn-gradient) .player-avatar{
        box-shadow:0 0 0 3px rgba(0,0,0,.93),inset 0 -10px 18px rgba(0,0,0,.50)!important;
      }
      body.v014.poker8-v2-sixmax .seat-name,
      body.v014.poker8-v2-sixmax .seat-stack,
      body.v014.poker8-v2-sixmax .bet-marker span{text-shadow:none!important;}

      /* The rest was a cyan haze at alpha .05 to .28 -- too faint to read as
         a signal, just enough to soften every edge it touched. Cards keep
         their depth shadow, which is what actually makes them look like
         cards; the pot keeps the black one it needs to stay legible. */
      body.v014.poker8-v2-sixmax .player-avatar span{text-shadow:none!important;}
      body.v014.poker8-v2-sixmax .empty-avatar,
      body.v014.poker8-v2-sixmax .mobile-menu-button,
      body.v014.poker8-v2-sixmax .mobile-chat-button,
      body.v014.poker8-v2-sixmax .brand-mark,
      body.v014.poker8-v2-sixmax .v028-center-ready-button{box-shadow:none!important;}
      body.v014.poker8-v2-sixmax .mobile-chat-button svg{filter:none!important;}
      body.v014.poker8-v2-sixmax .pot-total,
      body.v014.poker8-v2-sixmax .pot-total-label{text-shadow:0 2px 4px rgba(0,0,0,.65)!important;}

      /* Three "primary" buttons glowed at once, which is one call to action
         too many twice over. A button is legible from its fill and its edge. */
      body.v014.poker8-v2-sixmax .btn.primary,
      body.v014.poker8-v2-sixmax .stats-panel span,
      body.v014.poker8-v2-sixmax .modal-card{box-shadow:0 6px 18px rgba(0,0,0,.42)!important;}

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

  // v041 is the last mobile v2 layer to load -- its style being in place
  // means the table can finally paint without the boot cloak in index.html.
  document.body.classList.add("p8-boot-ready");
})();
