(() => {
  "use strict";

  let aggressiveIntent = false;
  let lastTurnKey = "";

  function currentTurnKey() {
    if (!game) return "";
    return [game.hand_id, game.street, game.acting_player, game.history?.length || 0].join(":");
  }

  function syncIntentForTurn() {
    const key = currentTurnKey();
    if (key !== lastTurnKey) {
      lastTurnKey = key;
      aggressiveIntent = false;
    }
  }

  function markAggressiveIntent() {
    aggressiveIntent = true;
    queueMicrotask(() => renderPersistentActionButtons());
  }

  document.addEventListener("input", (event) => {
    if (event.target?.id === "amount" || event.target?.id === "amountSlider") {
      markAggressiveIntent();
    }
  }, true);

  document.addEventListener("click", (event) => {
    const target = event.target?.closest?.("#amountMinus, #amountPlus, [data-sizing]");
    if (target) markAggressiveIntent();
  }, true);

  const originalRenderMobileSelectedCard = renderMobileSelectedCard;
  renderMobileSelectedCard = function renderMobileSelectedCardV016() {
    originalRenderMobileSelectedCard();
    if (!pendingInvalidReason) return;
    const action = $("mobileSelectedAction");
    const amount = $("mobileSelectedAmount");
    if (action) action.textContent = "СБРОШЕНО";
    if (amount) amount.textContent = "ситуация изменилась";
  };

  renderPersistentActionButtons = function renderPersistentActionButtonsV016() {
    const buttons = $("actionButtons");
    if (!buttons) return;
    buttons.innerHTML = "";

    syncIntentForTurn();

    const player = localViewerPlayer();
    const alive = localPlayerAlive();
    const localTurn = isLocalHumanTurn();
    const legal = game?.human_legal_actions || [];
    const toCall = estimatedLocalToCall();
    const amount = Number($("amount")?.value || amountBounds().value || 0);
    const currentBet = Number(game?.current_bet || 0);
    const invested = Number(player?.street_invested || 0);
    const allInTotal = Number(player?.stack || 0) + invested;

    const leftKey = localTurn
      ? (legal.includes("check") ? "check" : "fold")
      : (toCall > 0 ? "fold" : "check");

    const canCall = localTurn ? legal.includes("call") : toCall > 0;
    const canAggressive = localTurn
      ? (legal.includes("bet") || legal.includes("raise"))
      : true;

    const useCall = toCall > 0 && canCall && (!aggressiveIntent || !canAggressive);
    const primaryKey = useCall ? "call" : "aggressive";
    const aggressiveName = currentBet > invested ? "РЕЙЗ" : "СТАВКА";
    const primaryLabel = useCall
      ? `КОЛЛ\n${formatBB(toCall)}`
      : `${aggressiveName}\n${formatBB(amount)}`;

    const defs = [
      {
        key: leftKey,
        label: leftKey === "check" ? "ЧЕК" : "ПАС",
        cls: leftKey === "fold" ? "fold" : "check",
      },
      {
        key: primaryKey,
        label: primaryLabel,
        cls: `${useCall ? "call" : "raise"} v016-primary-action`,
      },
      {
        key: "all_in",
        label: `ОЛЛ-ИН\n${formatBB(allInTotal)}`,
        cls: "all-in",
      },
    ];

    defs.forEach((def) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.actionKey = def.key;
      button.className = `action-slot ${def.cls}`;
      button.textContent = def.label;
      button.classList.toggle("queued", pendingAction?.kind === def.key);

      let enabled = Boolean(game && !game.terminal && alive);
      if (localTurn) {
        if (def.key === "check") enabled = legal.includes("check");
        else if (def.key === "fold") enabled = legal.includes("fold") || legal.includes("check");
        else if (def.key === "call") enabled = legal.includes("call");
        else if (def.key === "aggressive") enabled = legal.includes("bet") || legal.includes("raise");
        else if (def.key === "all_in") enabled = legal.includes("all_in");
      } else if (def.key === "call") {
        enabled = enabled && toCall > 0;
      }
      button.disabled = !enabled;

      button.onclick = () => {
        if (!game || game.terminal || !alive) return;

        if (!localTurn) {
          togglePendingAction(def.key);
          renderPersistentActionButtons();
          renderMobileSelectedCard();
          return;
        }

        clearPendingAction(false);
        if (def.key === "check") return sendAction("check", 0);
        if (def.key === "fold") return sendAction(legal.includes("fold") ? "fold" : "check", 0);
        if (def.key === "call") return sendAction("call", 0);
        if (def.key === "all_in") return sendAction("all_in", 0);

        aggressiveIntent = false;
        const action = legal.includes("raise") ? "raise" : "bet";
        return sendAction(action, Number($("amount")?.value || 0));
      };

      buttons.appendChild(button);
    });
  };

  const style = document.createElement("style");
  style.id = "v016-mobile-polish";
  style.textContent = `
    @media (max-width:780px){
      body.v014 .action-grid{
        grid-template-columns:minmax(0,1fr) minmax(0,2fr) minmax(0,1fr) !important;
        gap:6px !important;
      }
      body.v014 .action-grid .v016-primary-action{
        font-size:11px !important;
        letter-spacing:.015em !important;
      }

      body.v014 .seat-bot .position-chip{
        display:none !important;
      }
      body.v014 .seat-bot .seat-identity{
        transform:translateY(-6px) !important;
      }
      body.v014 .seat-bot .seat-name{
        margin-top:-1px !important;
        font-size:10px !important;
      }
      body.v014 .seat-bot .seat-stack{
        margin-top:3px !important;
      }

      body.v014 .bet-marker .chip-cluster{
        transform:scale(.94) !important;
        transform-origin:center bottom !important;
      }
      body.v014 .bet-marker span{
        margin-top:1px !important;
        padding:2.5px 6px !important;
        font-size:8.2px !important;
        font-weight:900 !important;
        line-height:1 !important;
        border-radius:7px !important;
      }

      body.v014 .mobile-selected-card.invalid{
        padding:7px 6px !important;
      }
      body.v014 .mobile-selected-card.invalid #mobileSelectedAction{
        font-size:12px !important;
        line-height:1.05 !important;
        letter-spacing:.01em !important;
      }
      body.v014 .mobile-selected-card.invalid #mobileSelectedAmount{
        max-width:82px !important;
        margin-top:5px !important;
        font-size:8px !important;
        line-height:1.15 !important;
        font-weight:650 !important;
        color:#9ba8bc !important;
        text-align:center !important;
        white-space:normal !important;
      }
    }
  `;
  document.head.appendChild(style);

  renderPersistentActionButtons();
  renderMobileSelectedCard();
})();
