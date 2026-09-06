(() => {
  const style = document.createElement("style");
  style.textContent = `
    .card-actions{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
    .card-actions .card-action{flex:1;margin-top:0;padding:0;border-top:0}
    .card-observe{padding:8px 11px;border:1px solid var(--line);border-radius:10px;background:none;color:var(--muted);font-size:15px;line-height:1;cursor:pointer}
    .card-observe:hover{border-color:var(--violet);color:var(--violet)}
    .card-mine{border-color:var(--violet)}
    .table-state.mine{color:var(--orange)}
    .top-left{display:flex;align-items:center;gap:7px}
    #roomDialog select{width:100%;margin:8px 0;padding:14px;border:1px solid rgba(145,232,186,.32);border-radius:12px;background:var(--panel-2);color:var(--ink);font-size:15px}
    #roomDialog select:focus{outline:none;border-color:var(--mint)}
    #roomDialog input{font-size:15px}
  `;
  document.head.appendChild(style);

  const $ = id => document.getElementById(id);
  let tables = [];
  let selected = null;
  let activeSession = null;
  let myRoom = null;
  let roomLevels = {};
  let asset = "PLAY";
  let cashWallet = null;

  const format = units => (Number(units || 0) / 100).toFixed(2);
  const decimal = (value, digits) => {
    const amount = BigInt(value || 0);
    const scale = 10n ** BigInt(digits);
    const whole = amount / scale;
    const tail = String(amount % scale).padStart(digits, "0").replace(/0+$/, "");
    return tail ? `${whole}.${tail}` : String(whole);
  };
  const cashUnitsToChips = (value, chipMicros) => {
    const match = String(value || "").trim().match(/^(\d+)(?:\.(\d{1,5}))?$/);
    if (!match) throw new Error("Введите точную сумму CASH");
    const micros = BigInt(match[1]) * 100000n + BigInt((match[2] || "").padEnd(5, "0"));
    const chip = BigInt(chipMicros);
    if (micros % chip) throw new Error("Сумма должна быть кратна фишке стола");
    return Number(micros / chip);
  };
  const buyInRange = table => `${table.min_buy_in_bb || Math.round(table.min_buy_in_units / table.big_blind_units)}–${table.max_buy_in_bb || Math.round(table.max_buy_in_units / table.big_blind_units)} BB`;
  // Buckets on the blind size itself, not the table name -- a player-created
  // room's blinds (from /api/lobby/room-levels) still lands on a real tier
  // this way instead of falling through unlabeled.
  const TIER_GLOW = { micro: "rgba(145,232,186,.16)", low: "rgba(239,173,105,.16)", mid: "rgba(255,142,128,.18)" };
  const tierFor = table => {
    const bb = Number(table.big_blind_units || 0);
    if (bb <= 100) return "micro";
    if (bb <= 200) return "low";
    return "mid";
  };
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

  const bb = value => `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(1)} BB`;

  function renderSessionReport(report) {
    const panel = $("sessionReport");
    panel.hidden = !report;
    if (!report) return;
    const minutes = Math.max(1, Math.round((new Date(report.ended_at) - new Date(report.started_at)) / 60000));
    panel.hidden = false;
    $("reportSummary").textContent = `${report.hands} ${plural(report.hands)} · ${minutes} мин`;
    const net = $("reportNet");
    net.textContent = bb(report.net_bb);
    net.className = report.net_bb >= 0 ? "up" : "down";
    $("reportPot").textContent = `${Number(report.biggest_pot_bb).toFixed(1)} BB`;
    // A losing session still earned it, which is the whole point of showing
    // the two numbers side by side.
    $("reportXp").textContent = `+${report.xp_earned} XP`;
    // Kept on its own line rather than added to the hands' XP: the card that
    // says +1 XP for a session that paid 56 is worse than no card at all.
    $("reportDailyCell").hidden = !report.daily_xp;
    $("reportDaily").textContent = `+${report.daily_xp} XP`;
  }

  function plural(hands) {
    const tail = hands % 100;
    if (tail > 10 && tail < 20) return "раздач";
    return ["раздач", "раздача", "раздачи", "раздачи", "раздачи"][Math.min(hands % 10, 4)] || "раздач";
  }

  function renderTables() {
    $("tableGrid").innerHTML = tables.map((table, index) => {
      const tier = asset === "CASH_USDT" ? "cash" : tierFor(table);
      const full = table.occupied_count >= 6;
      const seatDots = Array.from({ length: 6 }, (_, seat) => `<i class="${seat < table.occupied_count ? "on" : ""}"></i>`).join("");
      return `
      <article class="table-card" data-open-table="${escape(table.id)}" style="--delay:${index * 45}ms;--tier-glow:${TIER_GLOW[tier]}">
        <div class="card-top">
          <span class="top-left"><span class="table-index">${String(index + 1).padStart(2, "0")}</span><span class="tier-tag ${tier}">${tier}</span></span>
          <span class="table-state${table.id === myRoom?.id ? " mine" : ""}">${table.id === myRoom?.id ? "● ВАША" : "● ОТКРЫТ"}</span>
        </div>
        <h3>${table.has_password ? '<span class="lock" aria-label="Закрыта паролем" title="Закрыта паролем">🔒</span> ' : ""}${escape(table.name)}</h3>
        <p class="blinds">Блайнды <b>${asset === "CASH_USDT"
          ? `${decimal(table.small_blind_micros, 6)} / ${decimal(table.big_blind_micros, 6)} USDT`
          : `${format(table.small_blind_units)} / ${format(table.big_blind_units)}`}</b></p>
        ${asset === "CASH_USDT" ? `<p class="dialog-muted">${decimal(table.small_blind_micros, 5)} / ${decimal(table.big_blind_micros, 5)} CASH</p>` : ""}
        <div class="card-bottom">
          <span>Бай-ин ${buyInRange(table)}</span>
          <span class="seats${full ? " full" : ""}" role="img" aria-label="Занято ${table.occupied_count} из 6 мест">${seatDots}</span>
        </div>
        <div class="card-actions">
          <button class="card-action" data-observe-table="${escape(table.id)}" type="button">Войти</button>
          ${table.id === myRoom?.id ? `<button class="card-observe" data-close-room="${escape(table.id)}" type="button" aria-label="Закрыть комнату" title="Закрыть">×</button>` : ""}
        </div>
      </article>`;
    }).join("");
    document.querySelectorAll("[data-observe-table]").forEach(button => button.addEventListener("click", () => openTable(button.dataset.observeTable)));
    // The whole card opens the table. On a phone the "Войти" button is a
    // small target inside something that already looks pressable, and every
    // tap that landed beside it did nothing. The close-room "×" is the one
    // part of the card that means something else.
    document.querySelectorAll(".table-card[data-open-table]").forEach(card => card.addEventListener("click", event => {
      if (event.target?.closest?.("[data-close-room]")) return;
      openTable(card.dataset.openTable);
    }));
    document.querySelectorAll("[data-close-room]").forEach(button => button.addEventListener("click", () => closeRoom(button.dataset.closeRoom)));
  }

  function pluralRu(n, one, few, many) {
    const mod100 = n % 100;
    if (mod100 >= 11 && mod100 <= 14) return many;
    const mod10 = n % 10;
    if (mod10 === 1) return one;
    if (mod10 >= 2 && mod10 <= 4) return few;
    return many;
  }

  function renderLiveStrip() {
    const totalPlayers = tables.reduce((sum, table) => sum + Number(table.occupied_count || 0), 0);
    const activeTables = tables.filter(table => Number(table.occupied_count || 0) > 0).length;
    $("liveHeadline").textContent = `${totalPlayers} ${pluralRu(totalPlayers, "игрок", "игрока", "игроков")} сейчас`;
    $("liveSub").textContent = activeTables ? `за ${activeTables} активными столами` : "столы свободны — начните первым";
  }

  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    const query = `asset=${asset}`;
    const [tablesResponse, sessionResponse, roomResponse, walletResponse] = await Promise.all([
      fetch(`/api/lobby/tables?page=1&per_page=12&${query}`),
      fetch(`/api/lobby/session?${query}`),
      fetch(`/api/lobby/rooms/mine?${query}`),
      asset === "CASH_USDT" ? fetch("/api/cash/wallet") : Promise.resolve(null),
    ]);
    if (!tablesResponse.ok || !sessionResponse.ok) throw new Error("lobby data is unavailable");
    const tablePayload = await tablesResponse.json();
    const sessionPayload = await sessionResponse.json();
    myRoom = roomResponse?.ok ? (await roomResponse.json()).room : null;
    if (asset === "CASH_USDT") {
      if (!walletResponse?.ok) throw new Error("cash mode is unavailable");
      cashWallet = await walletResponse.json();
      $("wallet").textContent = `${cashWallet.available_units} CASH`;
      $("cashAvailable").textContent = `${cashWallet.available_units} CASH`;
      $("cashAvailableUsdt").textContent = `${cashWallet.available_usdt} USDT`;
    } else {
      $("wallet").textContent = format(profile.available_units);
    }
    tables = tablePayload.tables;
    renderTables();
    renderLiveStrip();
    renderActiveSession(sessionPayload.session);
    // Fetched on every load, not only after a departure: a player who closed
    // the tab on the way out, or who was evicted while away, has a report
    // waiting the next time they open the lobby.
    const reportResponse = asset === "PLAY" ? await fetch("/api/profile/last-session").catch(() => null) : null;
    renderSessionReport(reportResponse?.ok ? (await reportResponse.json()).session : null);
    $("loadStatus").textContent = "● В СЕТИ";
  }

  function openBuyIn(table) {
    selected = table;
    $("buyInTable").textContent = asset === "CASH_USDT"
      ? `${table.name} · ${decimal(table.small_blind_micros, 6)} / ${decimal(table.big_blind_micros, 6)} USDT`
      : `${table.name} · ${format(table.small_blind_units)} / ${format(table.big_blind_units)} BB`;
    // Every table has its own blinds, so the limits cannot live in the markup.
    const input = $("buyInUnits");
    if (asset === "CASH_USDT") {
      input.min = decimal(table.min_buy_in_micros, 5);
      input.max = decimal(table.max_buy_in_micros, 5);
      input.step = decimal(table.chip_micros, 5);
      input.value = input.min;
      input.previousElementSibling.textContent = "Единицы CASH";
    } else {
      input.min = table.min_buy_in_units; input.max = table.max_buy_in_units;
      input.step = table.big_blind_units; input.value = table.min_buy_in_units;
      input.previousElementSibling.textContent = "Фишки";
    }
    $("buyInDialog").showModal();
    // Same Telegram Desktop webview focus gap as openRoomDialog() above.
    requestAnimationFrame(() => input.focus());
  }

  $("buyInForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (!selected) return;
    let buyInUnits;
    try {
      buyInUnits = asset === "CASH_USDT"
        ? cashUnitsToChips($("buyInUnits").value, selected.chip_micros)
        : Number($("buyInUnits").value);
    } catch (error) {
      return alert(error.message);
    }
    const response = await fetch(`/api/tables/${selected.id}/ready`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({
        seat_no: 2,
        buy_in_units: buyInUnits,
        request_id: requestId(),
      }),
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
    const response = await fetch(`/api/lobby/quick-play?asset=${asset}`, { method: "POST" });
    if (response.ok) return openBuyIn((await response.json()).table);
    if (asset === "CASH_USDT") {
      if (window.confirm("Для входа нужен CASH-баланс. Открыть CASH-кассу?")) location.href = "/static/profile.html#cash";
      return;
    }
    alert("Быстрый вход сейчас недоступен");
  });

  $("dismissReport").addEventListener("click", async () => {
    // Hide first, then tell the server: the card is gone either way, and a
    // failed dismissal only means it waits for them again next visit.
    $("sessionReport").hidden = true;
    await fetch("/api/profile/last-session/seen", { method: "POST" }).catch(() => {});
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


  async function closeRoom(id) {
    if (!window.confirm("Закрыть комнату? Все, кто за столом, выйдут, а фишки вернутся на балансы.")) return;
    const response = await fetch(`/api/lobby/rooms/${encodeURIComponent(id)}/close?asset=${asset}`, { method: "POST" });
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
    if (!roomLevels[asset]) {
      const response = await fetch(`/api/lobby/room-levels?asset=${asset}`);
      if (!response.ok) return alert("Создание комнат сейчас недоступно");
      roomLevels[asset] = (await response.json()).levels;
    }
    $("roomLevel").innerHTML = roomLevels[asset]
      .map(level => `<option value="${escape(level.key)}">${asset === "CASH_USDT"
        ? `${decimal(level.small_blind_micros, 6)} / ${decimal(level.big_blind_micros, 6)} USDT`
        : `${format(level.small_blind_units)} / ${format(level.big_blind_units)}`}</option>`)
      .join("");
    $("roomName").value = "";
    $("roomPassword").value = "";
    $("roomDialog").showModal();
    // Telegram Desktop's own webview does not reliably move keyboard focus
    // into a <dialog> on showModal() -- the fields render and accept clicks
    // in a real browser, but in that webview specifically nothing was
    // focused, so typing landed nowhere until the dialog was closed and
    // reopened (reported live: "с компа не могу ничего ввести"). A regular
    // browser already autofocuses correctly, so this is a no-op there.
    requestAnimationFrame(() => $("roomName")?.focus());
  }

  $("createRoom").addEventListener("click", () => openRoomDialog().catch(error => alert(error.message)));
  // The same panel the felt shows, opened before anyone has sat down: what
  // beats what, how a hand runs, and what each action button does.
  $("lobbyGuide")?.addEventListener("click", () => window.Poker8TableGuide?.toggle());
  document.addEventListener("click", event => {
    if (event.target?.closest?.(".hr-backdrop, #handRankingsClose")) window.Poker8TableGuide?.close();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") window.Poker8TableGuide?.close();
  });

  $("roomForm").addEventListener("submit", async event => {
    event.preventDefault();
    const body = {
      name: $("roomName").value,
      level: $("roomLevel").value,
      password: $("roomPassword").value || null,
    };
    const response = await fetch(`/api/lobby/rooms?asset=${asset}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    $("roomDialog").close();
    if (response.ok) {
      const room = (await response.json()).room;
      await load();
      return openTable(room.id);
    }
    const detail = (await response.json()).detail || {};
    if (detail.code === "room_limit_reached") return openTable(detail.table_id);
    alert(detail.message || "Не удалось создать комнату");
  });

  async function selectAsset(next) {
    if (next === asset) return;
    const previous = asset;
    asset = next;
    $("cashPilot").hidden = asset !== "CASH_USDT";
    document.querySelectorAll("[data-asset]").forEach(tab => {
      const active = tab.dataset.asset === asset;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    $("loadStatus").textContent = "● ЗАГРУЗКА";
    try {
      await load();
    } catch (error) {
      if (next === "CASH_USDT") {
        asset = previous;
        $("cashPilot").hidden = true;
        document.querySelectorAll("[data-asset]").forEach(tab => {
          const active = tab.dataset.asset === asset;
          tab.classList.toggle("is-active", active);
          tab.setAttribute("aria-selected", String(active));
        });
        await load();
        alert("Раздел REAL CASH сейчас недоступен.");
      } else throw error;
    }
  }

  document.querySelectorAll("[data-asset]").forEach(tab => {
    tab.addEventListener("click", () => selectAsset(tab.dataset.asset).catch(console.error));
  });

  async function boot() {
    const configResponse = await fetch("/api/config").catch(() => null);
    const config = configResponse?.ok ? await configResponse.json() : {cash_mode: "off"};
    const cashTab = document.querySelector('[data-asset="CASH_USDT"]');
    cashTab.hidden = config.cash_mode === "off";
    await load();
    if (location.hash === "#cash" && config.cash_mode !== "off") {
      await selectAsset("CASH_USDT");
    }
  }

  boot().catch(error => {
    // "Not signed in" is the player's problem to fix and "unavailable" is
    // ours. Saying the second when it is the first sends everyone to refresh
    // a page that will never load.
    $("loadStatus").textContent = window.Poker8Auth.needsSignIn(error)
      ? "● ВОЙДИТЕ ЧЕРЕЗ TELEGRAM"
      : "● НЕДОСТУПНО";
    console.error(error);
  });
})();
