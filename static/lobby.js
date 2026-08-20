(() => {
  const style = document.createElement("style");
  style.textContent = `
    .card-actions{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
    .card-actions .card-action{flex:1;margin-top:0;padding:0;border-top:0}
    .card-observe{padding:8px 11px;border:1px solid var(--line);border-radius:10px;background:none;color:var(--muted);font-size:15px;line-height:1;cursor:pointer}
    .card-observe:hover{border-color:var(--mint);color:var(--mint)}
    .card-mine{border-color:var(--mint)}
    .table-state.mine{color:var(--orange)}
    #roomDialog select{width:100%;margin:8px 0;padding:14px;border:1px solid var(--line);border-radius:12px;background:#07100f;color:var(--ink);font-size:15px}
    #roomDialog input{font-size:17px}
  `;
  document.head.appendChild(style);

  const $ = id => document.getElementById(id);
  let tables = [];
  let selected = null;
  let activeSession = null;
  let myRoom = null;
  let roomLevels = [];

  const format = units => (Number(units || 0) / 100).toFixed(2);
  const buyInRange = table => `${Math.round(table.min_buy_in_units / table.big_blind_units)}–${Math.round(table.max_buy_in_units / table.big_blind_units)} BB`;
  const requestId = () => crypto.randomUUID?.() || `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[char]));
  const openTable = id => { window.location.href = `/table?table=${encodeURIComponent(id)}`; };

  function sessionDescription(session) {
    if (session.kind === "waiting") return "Вы в очереди на место";
    // HOLD_WINDOW is thirty seconds, after which the seat goes back to the
    // table at the next boundary. "Место сохранено" on its own read as a
    // promise that it would be waiting whenever they got back.
    if (session.seat_state === "held") return "Место держим ещё полминуты · вернитесь к игре";
    if (session.seat_state === "leaving") return "Вы выходите после текущей раздачи";
    return "Вы за столом";
  }

  const LEAVE_POLL_MS = 4000;
  let leaveWatch = null;

  function renderActiveSession(session) {
    activeSession = session || null;
    const panel = $("activeSession");
    panel.hidden = !activeSession;
    const leaving = activeSession?.seat_state === "leaving";
    const spinner = $("leaveSpinner");
    if (spinner) spinner.hidden = !leaving;
    if (leaving) watchLeaving(); else stopWatchingLeaving();
    if (!activeSession) return;
    $("activeTableName").textContent = activeSession.table_name;
    $("activeTableState").textContent = sessionDescription(activeSession);
    $("returnTable").disabled = leaving;
    $("leaveTable").disabled = leaving;
    $("leaveTable").textContent = leaving
      ? "Выходим…"
      : activeSession.kind === "waiting" ? "Отменить очередь" : "Покинуть стол";
  }

  // A seat marked "leaving" is released at the next hand boundary, which can be
  // a minute away. The card used to sit there unchanged until the player
  // reloaded by hand, so the wait was indistinguishable from a stuck page.
  function watchLeaving() {
    if (leaveWatch) return;
    let ticks = 0;
    leaveWatch = setInterval(async () => {
      ticks += 1;
      // Re-send now and then: the request that started this could have been
      // lost on a flaky connection, and asking to leave a seat that is already
      // leaving changes nothing.
      if (ticks % 4 === 0 && activeSession?.table_id) {
        await fetch(`/api/tables/${activeSession.table_id}/leave`, {method: "POST"}).catch(() => {});
      }
      await load().catch(() => {});
    }, LEAVE_POLL_MS);
  }

  function stopWatchingLeaving() {
    clearInterval(leaveWatch);
    leaveWatch = null;
  }

  function renderTables() {
    $("tableGrid").innerHTML = tables.map((table, index) => `
      <article class="table-card" style="--delay:${index * 45}ms">
        <div class="card-top"><span class="table-index">${String(index + 1).padStart(2, "0")}</span><span class="table-state${table.id === myRoom?.id ? " mine" : ""}">${table.id === myRoom?.id ? (table.visibility === "link" ? "● ПО ССЫЛКЕ" : "● ВАША") : "● ОТКРЫТ"}</span></div>
        <h3>${escape(table.name)}</h3>
        <p class="blinds">Блайнды <b>${format(table.small_blind_units)} / ${format(table.big_blind_units)}</b></p>
        <div class="card-bottom"><span>Бай-ин ${buyInRange(table)}</span><span>${table.occupied_count} / 6</span></div>
        <div class="card-actions">
          <button class="card-action" data-table="${escape(table.id)}">Выбрать стол</button>
          <button class="card-observe" data-observe-table="${escape(table.id)}" type="button" aria-label="Наблюдать за столом" title="Наблюдать">👁</button>
          ${table.id === myRoom?.id ? `<button class="card-observe card-mine" data-copy-room="${escape(table.id)}" type="button" aria-label="Скопировать ссылку" title="Ссылка">🔗</button><button class="card-observe" data-close-room="${escape(table.id)}" type="button" aria-label="Закрыть комнату" title="Закрыть">×</button>` : ""}
        </div>
      </article>`).join("");
    document.querySelectorAll("[data-table]").forEach(button => button.addEventListener("click", () => openBuyIn(tables.find(table => table.id === button.dataset.table))));
    document.querySelectorAll("[data-observe-table]").forEach(button => button.addEventListener("click", () => openTable(button.dataset.observeTable)));
    document.querySelectorAll("[data-copy-room]").forEach(button => button.addEventListener("click", () => copyRoomLink(button.dataset.copyRoom)));
    document.querySelectorAll("[data-close-room]").forEach(button => button.addEventListener("click", () => closeRoom(button.dataset.closeRoom)));
  }

  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $("wallet").textContent = `${format(profile.available_units)} PLAY`;
    const [tablesResponse, sessionResponse, roomResponse] = await Promise.all([
      fetch("/api/lobby/tables?page=1&per_page=12"),
      fetch("/api/lobby/session"),
      fetch("/api/lobby/rooms/mine"),
    ]);
    if (!tablesResponse.ok || !sessionResponse.ok) throw new Error("lobby data is unavailable");
    const tablePayload = await tablesResponse.json();
    const sessionPayload = await sessionResponse.json();
    myRoom = roomResponse.ok ? (await roomResponse.json()).room : null;
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

  // A button with no type inside a form is a submit button, so both dialog
  // crosses submitted the form they were meant to abandon: closing the buy-in
  // seated you, and closing the room form opened a room.
  document.querySelectorAll(".dialog-close").forEach(button => {
    button.addEventListener("click", () => button.closest("dialog")?.close("cancel"));
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


  const roomUrl = id => `${location.origin}/table?table=${encodeURIComponent(id)}`;

  async function copyRoomLink(id) {
    const url = roomUrl(id);
    try {
      await navigator.clipboard.writeText(url);
      alert("Ссылка скопирована — отправьте её тем, кого зовёте.");
    } catch {
      // Clipboard access is refused in some in-app browsers; showing the link
      // still lets the player copy it by hand.
      window.prompt("Скопируйте ссылку на комнату:", url);
    }
  }

  async function closeRoom(id) {
    if (!window.confirm("Закрыть комнату? Все, кто за столом, выйдут, а фишки вернутся на балансы.")) return;
    const response = await fetch(`/api/lobby/rooms/${encodeURIComponent(id)}/close`, { method: "POST" });
    if (!response.ok) return alert("Не удалось закрыть комнату. Попробуйте ещё раз.");
    await load();
  }

  async function openRoomDialog() {
    if (myRoom) {
      // One room at a time, so there is nothing to fill in -- offer the one
      // they already have instead of a form that would be refused.
      if (window.confirm(`У вас уже открыта комната «${myRoom.name}». Перейти к ней?`)) openTable(myRoom.id);
      return;
    }
    if (!roomLevels.length) {
      const response = await fetch("/api/lobby/room-levels");
      if (!response.ok) return alert("Создание комнат сейчас недоступно");
      roomLevels = (await response.json()).levels;
    }
    $("roomLevel").innerHTML = roomLevels
      .map(level => `<option value="${escape(level.key)}">${format(level.small_blind_units)} / ${format(level.big_blind_units)}</option>`)
      .join("");
    $("roomName").value = "";
    $("roomDialog").showModal();
  }

  $("createRoom").addEventListener("click", () => openRoomDialog().catch(error => alert(error.message)));

  $("roomForm").addEventListener("submit", async event => {
    event.preventDefault();
    const body = {
      name: $("roomName").value,
      level: $("roomLevel").value,
      visibility: $("roomVisibility").value,
    };
    const response = await fetch("/api/lobby/rooms", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    $("roomDialog").close();
    if (response.ok) {
      const room = (await response.json()).room;
      await load();
      if (room.visibility === "link") await copyRoomLink(room.id);
      return openTable(room.id);
    }
    const detail = (await response.json()).detail || {};
    if (detail.code === "room_limit_reached") return openTable(detail.table_id);
    alert(detail.message || "Не удалось создать комнату");
  });

  load().catch(error => { $("loadStatus").textContent = "● НЕДОСТУПНО"; console.error(error); });
})();
