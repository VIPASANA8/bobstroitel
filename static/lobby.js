(() => {
  const style = document.createElement("style");
  style.textContent = `
    .card-actions{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
    .card-actions .card-action{flex:1;margin-top:0;padding:0;border-top:0}
    .card-observe{padding:8px 11px;border:1px solid var(--line);border-radius:10px;background:none;color:var(--muted);font-size:15px;line-height:1;cursor:pointer}
    .card-observe:hover{border-color:var(--mint);color:var(--mint)}
  `;
  document.head.appendChild(style);

  const $ = id => document.getElementById(id);
  let tables = [];
  let selected = null;
  let activeSession = null;

  const format = units => (Number(units || 0) / 100).toFixed(2);
  const buyInRange = table => `${Math.round(table.min_buy_in_units / table.big_blind_units)}–${Math.round(table.max_buy_in_units / table.big_blind_units)} BB`;
  const requestId = () => crypto.randomUUID?.() || `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[char]));
  const openTable = id => { window.location.href = `/table?table=${encodeURIComponent(id)}`; };

  function sessionDescription(session) {
    if (session.kind === "waiting") return "Вы в очереди на место";
    if (session.seat_state === "held") return "Место сохранено · вернитесь к игре";
    if (session.seat_state === "leaving") return "Вы выходите после текущей раздачи";
    return "Вы за столом";
  }

  function renderActiveSession(session) {
    activeSession = session || null;
    const panel = $("activeSession");
    panel.hidden = !activeSession;
    if (!activeSession) return;
    $("activeTableName").textContent = activeSession.table_name;
    $("activeTableState").textContent = sessionDescription(activeSession);
    $("returnTable").disabled = activeSession.seat_state === "leaving";
    $("leaveTable").textContent = activeSession.kind === "waiting" ? "Отменить очередь" : "Покинуть стол";
  }

  function renderTables() {
    $("tableGrid").innerHTML = tables.map((table, index) => `
      <article class="table-card" style="--delay:${index * 45}ms">
        <div class="card-top"><span class="table-index">${String(index + 1).padStart(2, "0")}</span><span class="table-state">● ОТКРЫТ</span></div>
        <h3>${escape(table.name)}</h3>
        <p class="blinds">Блайнды <b>${format(table.small_blind_units)} / ${format(table.big_blind_units)}</b></p>
        <div class="card-bottom"><span>Бай-ин ${buyInRange(table)}</span><span>${table.occupied_count} / 6</span></div>
        <div class="card-actions">
          <button class="card-action" data-table="${escape(table.id)}">Выбрать стол</button>
          <button class="card-observe" data-observe-table="${escape(table.id)}" type="button" aria-label="Наблюдать за столом" title="Наблюдать">👁</button>
        </div>
      </article>`).join("");
    document.querySelectorAll("[data-table]").forEach(button => button.addEventListener("click", () => openBuyIn(tables.find(table => table.id === button.dataset.table))));
    document.querySelectorAll("[data-observe-table]").forEach(button => button.addEventListener("click", () => openTable(button.dataset.observeTable)));
  }

  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $("wallet").textContent = `${format(profile.available_units)} PLAY`;
    const [tablesResponse, sessionResponse] = await Promise.all([
      fetch("/api/lobby/tables?page=1&per_page=6"),
      fetch("/api/lobby/session"),
    ]);
    if (!tablesResponse.ok || !sessionResponse.ok) throw new Error("lobby data is unavailable");
    const tablePayload = await tablesResponse.json();
    const sessionPayload = await sessionResponse.json();
    tables = tablePayload.tables;
    renderTables();
    renderActiveSession(sessionPayload.session);
    $("loadStatus").textContent = "● В СЕТИ";
  }

  function openBuyIn(table) {
    selected = table;
    $("buyInTable").textContent = `${table.name} · ${format(table.small_blind_units)} / ${format(table.big_blind_units)} BB`;
    // Every table has its own blinds, so the limits cannot live in the markup.
    const input = $("buyInUnits");
    input.min = table.min_buy_in_units;
    input.max = table.max_buy_in_units;
    input.step = table.big_blind_units;
    input.value = table.min_buy_in_units;
    $("buyInDialog").showModal();
  }

  $("buyInForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (!selected) return;
    const response = await fetch(`/api/tables/${selected.id}/ready`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ seat_no: 2, buy_in_units: Number($("buyInUnits").value), request_id: requestId() }),
    });
    $("buyInDialog").close();
    if (response.ok) return openTable(selected.id);
    const detail = (await response.json()).detail || {};
    if (detail.code === "already_seated" && detail.seat_state !== "leaving") return openTable(detail.table_id);
    alert(detail.seat_state === "leaving" ? "Вы выходите из-за стола — подождите завершения раздачи" : detail.message || "Не удалось встать в очередь");
  });

  $("quickPlay").addEventListener("click", async () => {
    const response = await fetch("/api/lobby/quick-play", { method: "POST" });
    if (!response.ok) return alert("Быстрый вход сейчас недоступен");
    openBuyIn((await response.json()).table);
  });

  $("returnTable").addEventListener("click", () => {
    if (activeSession?.table_id) openTable(activeSession.table_id);
  });

  $("leaveTable").addEventListener("click", async () => {
    if (!activeSession?.table_id) return;
    const waiting = activeSession.kind === "waiting";
    const confirmed = window.confirm(waiting ? "Отменить очередь на этот стол?" : "Покинуть стол? Во время раздачи выход будет выполнен после её завершения.");
    if (!confirmed) return;
    const endpoint = waiting ? `/api/tables/${activeSession.table_id}/ready/cancel` : `/api/tables/${activeSession.table_id}/leave`;
    const response = await fetch(endpoint, { method: "POST" });
    if (!response.ok) return alert("Не удалось выполнить действие. Попробуйте ещё раз.");
    await load();
  });

  load().catch(error => { $("loadStatus").textContent = "● НЕДОСТУПНО"; console.error(error); });
})();
