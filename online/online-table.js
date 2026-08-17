(() => {
  const tableId = new URLSearchParams(location.search).get("table");
  if (!tableId) return;

  window.Poker8OnlineTable = true;

  const tablePageStyle = document.createElement("style");
  tablePageStyle.textContent = `
    .poker8-online .online-state-panel{display:flex;align-items:center;gap:14px;margin:0 0 12px;padding:12px 14px;border:1px solid rgba(64,237,167,.28);border-radius:14px;background:rgba(2,29,17,.82)}
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
    @media(max-width:780px){
      .poker8-online .online-state-panel{position:fixed;left:10px;right:10px;bottom:calc(94px + env(safe-area-inset-bottom));z-index:120;box-shadow:0 10px 30px rgba(0,0,0,.42)}
      .poker8-online .online-state-panel button{white-space:nowrap}
      .poker8-online .online-chat-panel{display:none!important;position:fixed;left:10px;right:10px;bottom:calc(92px + env(safe-area-inset-bottom));z-index:130;margin:0}
      .poker8-online .online-chat-panel.is-open{display:block!important}
      .poker8-online .online-connection-status{right:10px;bottom:8px}
    }
  `;
  document.head.appendChild(tablePageStyle);
  document.body.classList.add("poker8-online");

  const $ = id => document.getElementById(id);
  const units = value => Math.round(Number(value || 0));
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[char]));
  let table = null;
  let viewerState = "spectator";
  let latestState = null;
  let pollTimer = null;

  function setText(id, value) {
    const node = $(id);
    if (node) node.textContent = String(value ?? "");
  }

  function firstOpenSeat(state) {
    const occupied = new Set(Object.values(state?.players || {}).map(player => Number(player.seat)));
    return [0, 1, 2, 3, 4, 5].find(seat => !occupied.has(seat)) ?? 0;
  }

  function phaseLabel(state) {
    const phase = state?.phase || "waiting";
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
    const phase = state?.phase || "waiting";
    setText("mobileStreetLabel", phaseLabel(state));
    setText("newHandCountdown", countdownText(state));
    const countdown = $("newHandCountdown");
    if (countdown) countdown.hidden = !countdownText(state);

    const ready = $("readyPanel");
    const waiting = phase === "waiting";
    if (ready) {
      ready.hidden = !waiting;
      setText("queueStatus", viewerState === "waiting" ? "Место занято — ждём свободный вход между раздачами" : "Выберите свободное место и бай-ин от 40 BB");
      const button = $("readyButton");
      if (button) {
        button.disabled = viewerState === "waiting";
        button.textContent = viewerState === "waiting" ? "В очереди…" : "Готов";
      }
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

  function renderSnapshot(state) {
    latestState = state;
    renderOnlineChrome(state);
    window.Poker8LegacyView?.renderSnapshot({ table, state, viewerState });
  }

  async function refreshState() {
    const response = await fetch(`/api/tables/${encodeURIComponent(tableId)}`);
    if (!response.ok) throw new Error("Не удалось загрузить состояние стола");
    const payload = await response.json();
    table = payload.table;
    viewerState = payload.viewer_state || viewerState;
    renderSnapshot(payload.state);
  }

  async function ready() {
    const buyInUnits = units(table?.big_blind_units) * 40;
    const result = await window.Poker8Transport.ready(firstOpenSeat(latestState), buyInUnits);
    viewerState = result.queue_state === "waiting" ? "waiting" : viewerState;
    await refreshState();
  }

  async function loadChat() {
    const payload = await window.Poker8Transport.loadChat().catch(() => ({ messages: [] }));
    const target = $("chatMessages");
    if (!target) return;
    target.innerHTML = (payload.messages || []).map(row => `<div><b>${escapeHtml(row.user_id || "Игрок")}</b> ${escapeHtml(row.text || "")}</div>`).join("");
  }

  function bindControls() {
    $("mobileMenuButton")?.addEventListener("click", () => { location.href = "/"; });
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
      const sent = await window.Poker8Transport.sendChat(text);
      $("chatMessages")?.insertAdjacentHTML("beforeend", `<div><b>${escapeHtml(sent.user_id || "Игрок")}</b> ${escapeHtml(sent.text || "")}</div>`);
      input.value = "";
    });
  }

  async function boot() {
    bindControls();
    await refreshState();
    clearInterval(pollTimer);
    pollTimer = setInterval(() => refreshState().catch(() => {}), 1000);
    window.Poker8Transport.connect(tableId, {
      onStatus: status => setText("connectionStatus", status),
      onMessage: message => { if (message.state) renderSnapshot(message.state); },
    });
    await loadChat();
  }

  boot().catch(error => {
    setText("connectionStatus", "ошибка");
    const target = $("result");
    if (target) target.textContent = error.message;
  });
})();
