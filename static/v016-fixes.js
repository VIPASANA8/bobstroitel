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
        label: `ALL-IN\n${formatBB(allInTotal)}`,
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

  function latestWagerPlayerId() {
    const rows = Array.isArray(game?.history) ? game.history : [];
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const row = rows[i];
      if (row?.street !== game?.street) continue;
      if (Number(row?.amount || 0) > 0 && row?.player_id) return row.player_id;
    }
    return null;
  }

  renderWagerMarkers = function renderWagerMarkersV016() {
    const layer = $("wagerLayer");
    if (!layer) return;
    layer.innerHTML = "";
    if (!game || game.terminal) return;

    const latest = latestWagerPlayerId();
    for (const player of Object.values(game.players || {})) {
      const wager = Number(player.street_invested || 0);
      if (!(wager > 0)) continue;
      const point = wagerPointForPlayer(game, player.id);
      if (!point) continue;

      const marker = document.createElement("div");
      marker.className = `bet-marker${player.id === latest ? " v016-latest-wager" : ""}`;
      marker.dataset.playerId = player.id;
      marker.style.left = `${point.x}px`;
      marker.style.top = `${point.y}px`;
      marker.innerHTML = `${chipStackHtml(wager, true)}<span>${formatBB(wager)}</span>`;
      layer.appendChild(marker);
    }
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

      body.v014 .wager-layer .bet-marker{
        display:flex !important;
        flex-direction:column !important;
        align-items:center !important;
        justify-content:flex-end !important;
        gap:2px !important;
        min-width:50px !important;
        padding:0 !important;
        background:transparent !important;
        border:0 !important;
        box-shadow:none !important;
        pointer-events:none !important;
      }
      body.v014 .wager-layer .bet-marker .chip-cluster{
        transform:scale(1.08) !important;
        transform-origin:center bottom !important;
        margin-bottom:4px !important;
        padding:0 !important;
        background:transparent !important;
        border:0 !important;
        outline:0 !important;
        box-shadow:none !important;
        filter:drop-shadow(0 3px 5px rgba(0,0,0,.72)) !important;
      }
      body.v014 .wager-layer .bet-marker span{
        display:block !important;
        min-width:48px !important;
        margin:0 !important;
        padding:4px 7px !important;
        border:1px solid rgba(123,194,255,.46) !important;
        border-radius:8px !important;
        background:rgba(1,7,18,.94) !important;
        box-shadow:0 3px 10px rgba(0,0,0,.62), inset 0 0 10px rgba(73,145,255,.08) !important;
        color:#ffffff !important;
        font-size:10.5px !important;
        font-weight:950 !important;
        line-height:1 !important;
        letter-spacing:-.02em !important;
        text-align:center !important;
        text-shadow:0 1px 3px #000 !important;
        white-space:nowrap !important;
      }
      body.v014 .wager-layer .bet-marker.v016-latest-wager .chip-cluster{
        transform:scale(1.10) !important;
        background:transparent !important;
        border:0 !important;
        outline:0 !important;
        box-shadow:none !important;
        filter:drop-shadow(0 0 3px rgba(77,210,255,.35)) drop-shadow(0 3px 5px rgba(0,0,0,.72)) !important;
      }
      body.v014 .wager-layer .bet-marker.v016-latest-wager span{
        border-color:rgba(75,218,255,.54) !important;
        background:rgba(1,9,20,.95) !important;
        box-shadow:0 3px 10px rgba(0,0,0,.62), 0 0 5px rgba(51,202,255,.12) !important;
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
  renderWagerMarkers();
})();
