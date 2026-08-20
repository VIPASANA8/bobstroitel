(() => {
  "use strict";

  function actorForMobileTimer() {
    if (!game || game.terminal) return null;
    const id = game.acting_player || game.acting_human_player_id;
    return (id && game.players?.[id]) || null;
  }

  function syncMobileTurnHud() {
    const card = $("mobileTimerCard");
    const label = card?.querySelector(":scope > span");
    const timer = $("mobileActionTimer");
    const track = card?.querySelector(".mobile-timer-track");
    if (!card || !label) return;

    const localTurn = Boolean(game && !game.terminal && isLocalHumanTurn());
    const opponentTurn = Boolean(game && !game.terminal && !localTurn);

    card.classList.toggle("opponent-turn", opponentTurn);

    if (!game || game.terminal) {
      label.textContent = "ВАШ ХОД";
      label.removeAttribute("title");
      if (timer) timer.style.display = "";
      if (track) track.style.display = "";
      return;
    }

    if (localTurn) {
      label.textContent = "ВАШ ХОД";
      label.removeAttribute("title");
      if (timer) timer.style.display = "";
      if (track) track.style.display = "";
      return;
    }

    const actor = actorForMobileTimer();
    const name = actor?.name || game.acting_human_name || "ИГРОК";
    label.textContent = `ХОД ${name}`;
    label.title = `Ход: ${name}`;

    // On somebody else's turn we keep only the actor label.
    // The 01:00 countdown belongs exclusively to the local human turn.
    if (timer) timer.style.display = "none";
    if (track) track.style.display = "none";
  }

  const originalRenderMobileHud = renderMobileHud;
  renderMobileHud = function renderMobileHudV021() {
    originalRenderMobileHud();
    syncMobileTurnHud();
  };

  // The pot renderer that lived here -- latestHistoryPot, visualPotAmount,
  // growingPotStackHtml and a renderPotChips override -- was replaced outright
  // by v031 and had not drawn a chip since. It is in app.js now, once.

  const style = document.createElement("style");
  style.id = "v021-mobile-fixes";
  style.textContent = `
    @media (max-width:780px){
      body.v014 .mobile-timer-card > span{
        display:block !important;
        width:82px !important;
        max-width:82px !important;
        overflow:hidden !important;
        text-overflow:ellipsis !important;
        white-space:nowrap !important;
        text-align:center !important;
      }

      /* Opponent turn: actor name only, no fake 01:00 and no progress bar. */
      body.v014 .mobile-timer-card.opponent-turn{
        min-height:42px !important;
        height:42px !important;
        padding:6px 5px !important;
      }
      body.v014 .mobile-timer-card.opponent-turn #mobileActionTimer,
      body.v014 .mobile-timer-card.opponent-turn .mobile-timer-track{
        display:none !important;
      }

      /* No permanent outline around the viewer seat when it is not the active turn. */
      body.v014 .seat[data-visual-seat="0"] .seat-card.viewer-seat:not(.active-turn){
        border-color:transparent !important;
        outline:0 !important;
        box-shadow:none !important;
      }

      /* Pot chips stay plate-less while the pile grows. */
      body.v014 .pot-chips,
      body.v014 .pot-chips .v021-growing-pot,
      body.v014 .pot-chips .v021-growing-pot .chip-column{
        background:transparent !important;
        border:0 !important;
        outline:0 !important;
        box-shadow:none !important;
        filter:none !important;
      }
      body.v014 .pot-chips .v021-growing-pot{
        transform-origin:center bottom !important;
      }
    }
  `;
  document.head.appendChild(style);

  syncMobileTurnHud();
  if (game) renderPotChips(game.pot);
})();
