(() => {
  "use strict";

  function actorForMobileTimer() {
    if (!game || game.terminal) return null;
    const id = game.acting_player || game.acting_human_player_id;
    return (id && game.players?.[id]) || null;
  }

  function syncMobileTurnLabel() {
    const card = $("mobileTimerCard");
    const label = card?.querySelector(":scope > span");
    if (!label) return;

    if (!game || game.terminal) {
      label.textContent = "ВАШ ХОД";
      label.removeAttribute("title");
      return;
    }

    if (isLocalHumanTurn()) {
      label.textContent = "ВАШ ХОД";
      label.removeAttribute("title");
      return;
    }

    const actor = actorForMobileTimer();
    const name = actor?.name || game.acting_human_name || "ИГРОК";
    label.textContent = `ХОД ${name}`;
    label.title = `Ход: ${name}`;
  }

  const originalRenderMobileHud = renderMobileHud;
  renderMobileHud = function renderMobileHudV020() {
    originalRenderMobileHud();
    syncMobileTurnLabel();
  };

  function latestHistoryPot() {
    const rows = Array.isArray(game?.history) ? game.history : [];
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const value = Number(rows[i]?.pot_after);
      if (Number.isFinite(value) && value >= 0) return value;
    }
    return 0;
  }

  function visualPotAmount(value) {
    const direct = Math.max(0, Number(value || 0));
    if (!game || game.terminal) return direct;
    return Math.max(direct, latestHistoryPot());
  }

  function growingPotStackHtml(value) {
    const n = Math.max(0, Number(value || 0));
    if (!(n > 0)) return "";

    // Make the pot visibly grow as chips arrive. The old renderer kept almost
    // the same 4–8 visible chips for many different pot sizes, so additions
    // were easy to miss on a phone screen.
    const visibleTotal = Math.min(30, Math.max(4, Math.ceil(Math.log2(n + 1) * 6)));
    const stackCount = Math.min(5, Math.max(1, Math.ceil(visibleTotal / 6)));
    const palette = chipsForAmount(n, 20);
    const fallback = ["chip-1", "chip-25", "chip-5", "chip-100", "chip-05"];
    const columns = [];
    let remaining = visibleTotal;

    for (let col = 0; col < stackCount; col += 1) {
      const colsLeft = stackCount - col;
      const chipCount = Math.min(7, Math.max(1, Math.ceil(remaining / colsLeft)));
      remaining -= chipCount;
      const cls = palette[col % Math.max(1, palette.length)] || fallback[col % fallback.length];
      const chips = Array.from({ length: chipCount }, (_, i) =>
        `<i class="poker-chip ${cls}" style="--i:${i}"></i>`
      ).join("");
      columns.push(`<span class="chip-column" style="--col:${col};--cols:${stackCount}">${chips}</span>`);
    }

    return `<div class="chip-cluster pot-cluster v020-growing-pot">${columns.join("")}</div>`;
  }

  renderPotChips = function renderPotChipsV020(value) {
    const target = $("potChips");
    if (!target) return;
    const visualValue = visualPotAmount(value);
    target.innerHTML = growingPotStackHtml(visualValue);
    target.dataset.visualPot = String(visualValue);
    target.classList.toggle("has-chips", visualValue > 0);
  };

  const style = document.createElement("style");
  style.id = "v020-mobile-fixes";
  style.textContent = `
    @media (max-width:780px){
      /* When it is somebody else's turn, the timer HUD names that player. */
      body.v014 .mobile-timer-card > span{
        display:block !important;
        width:82px !important;
        max-width:82px !important;
        overflow:hidden !important;
        text-overflow:ellipsis !important;
        white-space:nowrap !important;
        text-align:center !important;
      }

      /* The viewer seat should not have a permanent cyan frame. It can still
         receive the normal active-turn highlight when it is actually your turn. */
      body.v014 .seat[data-visual-seat="0"] .seat-card.viewer-seat:not(.active-turn){
        border-color:rgba(75,126,205,.26) !important;
        box-shadow:0 10px 28px rgba(0,0,0,.30) !important;
      }

      /* Keep the growing pot itself completely plate-less. */
      body.v014 .pot-chips .v020-growing-pot,
      body.v014 .pot-chips .v020-growing-pot .chip-column{
        background:transparent !important;
        border:0 !important;
        outline:0 !important;
        box-shadow:none !important;
      }
    }
  `;
  document.head.appendChild(style);

  syncMobileTurnLabel();
  if (game) renderPotChips(game.pot);
})();
