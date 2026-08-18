(() => {
  const tableId = new URLSearchParams(location.search).get("table");
  if (!tableId) return;

  window.Poker8OnlineTable = true;

  const tablePageStyle = document.createElement("style");
  tablePageStyle.textContent = `
    .poker8-online .online-state-panel{display:flex;align-items:center;gap:14px;margin:0 0 12px;padding:12px 14px;border:1px solid rgba(64,237,167,.28);border-radius:14px;background:rgba(2,29,17,.82)}
    .poker8-online .online-state-panel[hidden]{display:none!important}
    .poker8-online .online-state-panel strong{color:#8ff2c0;font-size:13px}
    .poker8-online .online-state-panel span{flex:1;color:#9aada3;font-size:12px}
    .poker8-online .online-state-panel button{padding:10px 14px;border:1px solid rgba(64,237,167,.5);border-radius:10px;background:#0a3b2b;color:#b8ffda;font-weight:850;cursor:pointer}
    .poker8-online .online-connection-status{position:fixed;right:14px;bottom:12px;z-index:1000;padding:5px 9px;border:1px solid rgba(64,237,167,.28);border-radius:999px;background:rgba(3,13,10,.82);color:#91e8ba;font:700 10px monospace}
    .poker8-online .online-chat-panel{display:block;grid-column:2;align-self:start;margin-top:0;padding:16px;border:1px solid rgba(64,237,167,.28);border-radius:18px;background:rgba(6,25,18,.86)}
    .poker8-online .online-chat-panel h2{margin:0 0 12px;color:#91e8ba;font-size:15px}
    .poker8-online #chatMessages{max-height:240px;overflow:auto;color:#c3d7cc;font-size:12px;line-height:1.6}
    .poker8-online #chatForm{display:flex;gap:8px;margin-top:12px}
    .poker8-online #chatInput{min-width:0;flex:1;padding:11px;border:1px solid #294d3e;border-radius:10px;background:#07100f;color:#f4f5ee}
    .poker8-online #chatForm button{padding:0 15px;border:0;border-radius:10px;background:#91e8ba;color:#082018;font-weight:900}
    .poker8-online .local-only-control,.poker8-online .solver-panel,.poker8-online .stats-panel,.poker8-online .saved-tables-panel,.poker8-online .format-panel{display:none!important}
    .poker8-online .mobile-drawer-divider{height:1px;margin:8px 0;border:0;background:rgba(126,202,165,.20)}
    .poker8-online .mobile-drawer .network-table-action{display:block;width:100%;margin:6px 0;padding:12px;border:1px solid rgba(95,237,170,.34);border-radius:10px;background:rgba(4,31,20,.84);color:#c9ffe3;text-align:left;font-weight:850}
    .poker8-online .mobile-drawer .network-table-action.danger{border-color:rgba(255,125,111,.34);color:#ffc1b6;background:rgba(52,14,12,.58)}
    .poker8-online.p8-observer-mode #actionButtons,.poker8-online.p8-observer-mode #sizingWrap,.poker8-online.p8-observer-mode .mobile-turn-tools,.poker8-online.p8-observer-mode #mobileAutoActionBar,.poker8-online.p8-observer-mode .v038-hud-summary{display:none!important}
    .poker8-online.p8-observer-mode #mobileTimerCard,.poker8-online.p8-observer-mode #mobileSelectedCard{display:none!important}
    .poker8-online.p8-observer-mode .action-panel{border-color:rgba(64,237,167,.34)}
    .poker8-online.p8-action-pending #actionButtons{opacity:.62;pointer-events:none;filter:saturate(.72)}
    .poker8-online.p8-action-pending #actionButtons::after{content:'Отправляем действие…';display:block;grid-column:1 / -1;text-align:center;color:#a8ffd4;font-size:11px;font-weight:800;padding:5px}
    @media(max-width:780px){
      .poker8-online .felt > .online-state-panel{position:absolute;left:50%;top:59%;right:auto;bottom:auto;z-index:76;width:min(84vw,348px);margin:0;padding:10px 12px;transform:translate(-50%,-50%);display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 12px;border-color:rgba(64,237,167,.48);background:linear-gradient(135deg,rgba(1,29,18,.94),rgba(2,14,11,.96));box-shadow:0 12px 28px rgba(0,0,0,.42),0 0 20px rgba(44,247,169,.10);transition:width 180ms ease,padding 180ms ease,top 180ms ease}
      .poker8-online .felt > .online-state-panel strong{grid-column:1;color:#a8ffd4;font-size:14px;line-height:1.1}
      .poker8-online .felt > .online-state-panel span{grid-column:1;color:#c3d7cc;font-size:11px;line-height:1.25}
      .poker8-online .felt > .online-state-panel button{grid-column:2;grid-row:1 / span 2;align-self:center;min-height:42px;padding:9px 12px;white-space:nowrap}
      /* Nothing to press while the seat is only pending: a full card sitting over
         the felt just to say "please wait" hides the table for no reason. Collapse
         it to a slim strip near the rail and hand the middle back to the game. */
      .poker8-online .felt > .online-state-panel.is-pending{top:8px;transform:translateX(-50%);width:min(78vw,300px);padding:6px 10px;grid-template-columns:1fr;box-shadow:0 6px 16px rgba(0,0,0,.36)}
      .poker8-online .felt > .online-state-panel.is-pending strong{font-size:11px}
      .poker8-online .felt > .online-state-panel.is-pending span{font-size:10px}
      .poker8-online .felt > .online-state-panel.is-pending button{display:none}
      .poker8-online .online-chat-panel{display:none!important;position:fixed;left:10px;right:10px;bottom:calc(92px + env(safe-area-inset-bottom));z-index:130;margin:0}
      .poker8-online .online-chat-panel.is-open{display:block!important}
      .poker8-online .online-connection-status{right:10px;bottom:8px}
      /* v038 derives --table-stage-h from these two vars, so zeroing them here
         (custom-property !important still beats v038's later non-important
         declaration) expands the felt into the space the hidden action panel
         would otherwise still reserve for nothing but an empty black slab. */
      body.v014.poker8-v2-sixmax.p8-observer-mode{--p8-hud-h:0px!important;--p8-bottom-reserve:0px!important}
      body.v014.poker8-v2-sixmax.p8-observer-mode .sidebar,
      body.v014.poker8-v2-sixmax.p8-observer-mode .action-panel{display:none!important}
    }
  `;
  document.head.appendChild(tablePageStyle);
  document.body.classList.add("poker8-online");

  const $ = id => document.getElementById(id);
  const mobileQuery = window.matchMedia?.("(max-width: 780px)");
  function placeReadyPanel() {
    const panel = $("readyPanel");
    const felt = document.querySelector(".felt");
    const layout = document.querySelector(".layout");
    if (!panel || !felt || !layout) return;
    if (mobileQuery?.matches) {
      if (panel.parentElement !== felt) felt.append(panel);
    } else if (panel.parentElement !== layout) {
      layout.prepend(panel);
    }
  }
  placeReadyPanel();
  mobileQuery?.addEventListener?.("change", placeReadyPanel);

  const units = value => Math.round(Number(value || 0));
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
  let table = null;
  let viewerState = "spectator";
  let latestState = null;
  let pollTimer = null;
  let lastRenderKey = null;
  let readyInFlight = false;

  window.addEventListener("poker8:action-pending", event => {
    document.body.classList.toggle("p8-action-pending", Boolean(event.detail?.pending));
  });

  function setText(id, value) {
    const node = $(id);
    if (node) node.textContent = String(value ?? "");
  }

  function firstOpenSeat(state) {
    const occupied = new Set(Object.values(state?.players || {}).map(player => Number(player.seat)));
    return [0, 1, 2, 3, 4, 5].find(seat => !occupied.has(seat)) ?? 0;
  }

  function phaseLabel(state) {
    let phase = state?.phase || "waiting";
    // The runtime drops to "waiting" for the instant between clearing a hand and
    // dealing the next one. Showing it makes the label flicker mid-countdown.
    if (phase === "waiting" && state?.next_hand_at && Date.parse(state.next_hand_at) > Date.now()) phase = "countdown";
    return { waiting: "ОЖИДАНИЕ", countdown: "COUNTDOWN", active: "РАЗДАЧА", result: "ВСКРЫТИЕ", paused: "ПАУЗА" }[phase] || phase.toUpperCase();
  }

  function countdownText(state) {
    const phase = state?.phase;
    const target = phase === "result" ? state.result_clear_at : phase === "countdown" ? state.next_hand_at : null;
    if (!target) return "";
    const seconds = Math.max(0, Math.ceil((Date.parse(target) - Date.now()) / 1000));
    return phase === "result" ? `Следующая раздача через ${seconds} сек.` : `Новая раздача через ${seconds} сек.`;
  }

  function renderOnlineChrome(state) {
    setText("mobileStreetLabel", phaseLabel(state));
    setText("newHandCountdown", countdownText(state));
    const countdown = $("newHandCountdown");
    if (countdown) countdown.hidden = !countdownText(state);

    const observerMode = ["spectator", "waiting"].includes(viewerState);
    document.body.classList.toggle("p8-observer-mode", observerMode);
    const ready = $("readyPanel");
    if (ready) {
      // The queue seats players at the next hand boundary, so the panel stays
      // available while a hand is running.
      ready.hidden = !["spectator", "waiting"].includes(viewerState);
      const occupiedSeats = new Set(Object.values(state?.players || {}).map(player => Number(player.seat)));
      const totalSeats = Number(table?.max_seats || 6);
      const hasFreeSeat = occupiedSeats.size < totalSeats;
      const waitingText = hasFreeSeat
        ? "Место забронировано — вход после текущей раздачи"
        : "Все места заняты — ждём освобождение между раздачами";
      const title = ready.querySelector("strong");
      if (title) title.textContent = viewerState === "waiting" ? "Место забронировано" : hasFreeSeat ? "Займите место" : "Встаньте в очередь";
      setText("queueStatus", viewerState === "waiting" ? waitingText : hasFreeSeat
        ? "Первое свободное место · бай-ин 40 BB"
        : "Свободных мест нет — забронируйте вход после раздачи");
      const button = $("readyButton");
      if (button) {
        button.disabled = viewerState === "waiting";
        button.textContent = viewerState === "waiting" ? "Бронь принята" : hasFreeSeat ? "Занять место" : "Встать в очередь";
      }
      // Pending has nothing to click, so the full card only blocks the table.
      ready.classList.toggle("is-pending", viewerState === "waiting");
    }
    const chat = $("chatPanel");
    if (chat) {
      const mobile = window.matchMedia?.("(max-width:780px)")?.matches;
      chat.hidden = Boolean(mobile && !chat.classList.contains("is-open"));
    }
    ["infiniteMode", "spectatorPause", "abortHand", "newHand", "mobilePrimaryAction"].forEach(id => {
      if ($(id)) $(id).classList.add("local-only-control");
    });
  }

  function snapshotRenderKey(state) {
    const players = Object.values(state?.players || {})
      .map(player => [player.id, player.seat, player.stack, player.folded, player.street_invested]);
    return JSON.stringify([
      viewerState,
      state?.hand_id,
      state?.phase,
      state?.revision,
      state?.street,
      state?.acting_player,
      state?.pot,
      state?.action_deadline,
      state?.result_clear_at,
      state?.next_hand_at,
      players,
    ]);
  }

  function renderObserverCopy(state) {
    if (!["spectator", "waiting"].includes(viewerState)) return;
    const actor = state?.players?.[state?.acting_player];
    setText("actionPanelKicker", viewerState === "waiting" ? "МЕСТО ЗАБРОНИРОВАНО" : "НАБЛЮДЕНИЕ");
    setText("turnTitle", actor ? `Ход: ${actor.name || "игрок"}` : "Смотрите раздачу");
    setText("hint", viewerState === "waiting"
      ? "Вход за стол произойдёт после текущей раздачи."
      : "Смотрите раздачу. Чтобы играть, займите свободное место.");
    if ($("actionTimer")) $("actionTimer").hidden = true;
  }

  function renderSnapshot(state) {
    latestState = state;
    renderOnlineChrome(state);
    const key = snapshotRenderKey(state);
    if (key === lastRenderKey) return;
    lastRenderKey = key;
    window.Poker8LegacyView?.renderSnapshot({ table, state, viewerState });
    renderObserverCopy(state);
  }

  async function refreshState() {
    const response = await fetch(`/api/tables/${encodeURIComponent(tableId)}`);
    if (!response.ok) throw new Error("Не удалось загрузить состояние стола");
    const payload = await response.json();
    table = payload.table;
    viewerState = payload.viewer_state || viewerState;
    window.Poker8Transport?.setRevision?.(payload.state?.revision);
    renderSnapshot(payload.state);
  }

  async function ready() {
    if (readyInFlight || viewerState === "seated" || viewerState === "held" || viewerState === "leaving") return;
    readyInFlight = true;
    const button = $("readyButton");
    if (button) button.disabled = true;
    const buyInUnits = units(table?.big_blind_units) * 40;
    try {
      const result = await window.Poker8Transport.ready(firstOpenSeat(latestState), buyInUnits);
      viewerState = result.queue_state === "waiting" ? "waiting" : viewerState;
      await refreshState();
    } catch (error) {
      if (String(error.message || "").includes("already has a network seat")) {
        await refreshState();
        return;
      }
      throw error;
    } finally {
      readyInFlight = false;
    }
  }

  const chatRow = row => `<div><b>${escapeHtml(row.user_id || "Игрок")}</b> ${escapeHtml(row.text || "")}</div>`;

  function appendChat(row) {
    $("chatMessages")?.insertAdjacentHTML("beforeend", chatRow(row));
  }

  async function loadChat() {
    const payload = await window.Poker8Transport.loadChat().catch(() => ({ messages: [] }));
    const target = $("chatMessages");
    if (!target) return;
    target.innerHTML = (payload.messages || []).map(chatRow).join("");
  }

  function showRejection(reason) {
    const target = $("connectionStatus");
    if (target) target.textContent = `отклонено: ${reason || "неизвестно"}`;
    // The snapshot the action was based on is stale by definition here.
    window.Poker8Transport.resync();
  }

  async function returnToLobby() {
    // Do not call /leave here: closing the socket changes a seated player to
    // held, which preserves the place for a short reconnect window.
    if (viewerState === "waiting") await window.Poker8Transport.cancelReady();
    window.Poker8Transport.disconnect();
    location.href = "/";
  }

  async function leaveTable() {
    if (viewerState === "waiting") {
      await window.Poker8Transport.cancelReady();
    } else if (["seated", "held"].includes(viewerState)) {
      await window.Poker8Transport.leave();
    }
    window.Poker8Transport.disconnect();
    location.href = "/";
  }

  function bindControls() {
    $("mobileDrawerLobby")?.addEventListener("click", () => returnToLobby().catch(error => alert(error.message)));
    $("mobileDrawerLeave")?.addEventListener("click", async () => {
      const waiting = viewerState === "waiting";
      const message = waiting ? "Отменить очередь на место?" : "Покинуть стол? Во время раздачи выход будет выполнен после её завершения.";
      if (window.confirm(message)) await leaveTable().catch(error => alert(error.message));
    });
    $("mobileChatButton")?.addEventListener("click", () => {
      const chat = $("chatPanel");
      const button = $("mobileChatButton");
      if (!chat) return;
      const open = !chat.classList.contains("is-open");
      chat.classList.toggle("is-open", open);
      chat.hidden = !open;
      button?.setAttribute("aria-expanded", String(open));
    });
    $("readyButton")?.addEventListener("click", () => ready().catch(error => { alert(error.message); }));
    $("chatForm")?.addEventListener("submit", async event => {
      event.preventDefault();
      const input = $("chatInput");
      const text = input?.value.trim();
      if (!text) return;
      await window.Poker8Transport.sendChat(text);
      input.value = "";
    });
  }

  async function boot() {
    bindControls();
    // Table pages must authenticate the Telegram Mini App before the first
    // snapshot; otherwise a retained guest cookie masks the real @username.
    await window.Poker8Auth?.ensureSession?.();
    await refreshState();
    clearInterval(pollTimer);
    // The socket now carries coordinator-driven changes too, so this is only a
    // safety net for a dropped connection.
    pollTimer = setInterval(() => refreshState().catch(() => {}), 3000);
    window.Poker8Transport.connect(tableId, {
      onStatus: status => setText("connectionStatus", status),
      onMessage: message => {
        if (message.state) renderSnapshot(message.state);
        if (message.type === "chat") appendChat(message.message || {});
        if (message.type === "command_rejected") showRejection(message.reason);
      },
    });
    await loadChat();
  }

  boot().catch(error => {
    setText("connectionStatus", "ошибка");
    const target = $("result");
    if (target) target.textContent = error.message;
  });
})();
