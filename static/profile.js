(() => {
  const $ = id => document.getElementById(id);
  const units = value => (Number(value || 0) / 100).toFixed(2);
  const signed = value => `${Number(value) > 0 ? "+" : ""}${units(value)}`;
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));

  // The ledger stores what the engine calls things. Nobody outside the code
  // knows what "add_on" or "faucet_grant" is, and the journal printed them raw.
  const LEDGER_KINDS = {
    buy_in: "Бай-ин",
    add_on: "Докупка",
    return: "Возврат со стола",
    settlement: "Расчёт раздачи",
    faucet_grant: "Начисление",
  };

  const dateText = value => {
    const stamp = value ? new Date(value) : null;
    if (!stamp || Number.isNaN(stamp.getTime())) return "";
    return stamp.toLocaleString("ru-RU", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  };

  function handRow(hand) {
    // last_hands marks the viewer's own row; without it the only things a row
    // could say were the hand id and how many people were in it.
    const mine = (hand.players || []).find(player => player.you);
    const net = Number(mine?.net_units || 0);
    const outcome = net > 0 ? "win" : net < 0 ? "loss" : "flat";
    const verdict = net > 0 ? "Выигрыш" : net < 0 ? "Проигрыш" : "Без изменений";
    const when = dateText(hand.completed_at || hand.started_at);
    return `<article class="history-row ${outcome}">
      <div class="history-what"><strong>${verdict}</strong><small>${escapeHtml(when)} · ${(hand.players || []).length} игроков</small></div>
      <span class="history-amount">${signed(net)}</span>
    </article>`;
  }

  function ledgerRow(row) {
    const amount = Number(row.amount_units || 0);
    const outcome = amount > 0 ? "win" : amount < 0 ? "loss" : "flat";
    return `<article class="history-row ${outcome}">
      <div class="history-what"><strong>${escapeHtml(LEDGER_KINDS[row.kind] || row.kind)}</strong><small>${escapeHtml(dateText(row.created_at))}</small></div>
      <span class="history-amount">${signed(amount)}</span>
    </article>`;
  }

  // A failed fetch used to reach console.error and nothing else, so the page
  // sat there as a column of em dashes with no way to tell it apart from a
  // player who had never played a hand.
  const fill = (id, rows, empty) => {
    const host = $(id);
    if (host) host.innerHTML = rows.length ? rows.join("") : `<p class="history-empty">${empty}</p>`;
  };

  async function json(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url} → ${response.status}`);
    return response.json();
  }

  // /api/profile/play-top-up is 404 on a deployment on purpose -- money there
  // has to arrive through a payment. Asking the config first is the difference
  // between a panel that says so and a button that fails when pressed.
  function renderTopUp(enabled) {
    const note = $("topupNote");
    const submit = $("topupSubmit");
    const amount = $("topupAmount");
    const presets = [...($("topupPresets")?.querySelectorAll("button") || [])];
    for (const control of [submit, amount, ...presets]) {
      if (control) control.disabled = !enabled;
    }
    if (note) {
      note.textContent = enabled
        ? "Игровые фишки, без реальных денег."
        : "Оплата в USDT скоро будет доступна.";
      note.classList.toggle("is-off", !enabled);
    }
  }

  async function topUp(displayAmount) {
    const value = Number(displayAmount);
    if (!Number.isFinite(value) || value <= 0) return;
    const note = $("topupNote");
    const submit = $("topupSubmit");
    if (submit) submit.disabled = true;
    try {
      const response = await fetch("/api/profile/play-top-up", {
        method: "POST",
        headers: { "content-type": "application/json" },
        // The input is in the same currency the page prints; the endpoint
        // counts in units, which are hundredths of it.
        body: JSON.stringify({
          amount_units: Math.round(value * 100),
          // The caller picks this, and the ledger dedups on it -- a fresh one
          // per press, or a double-click would be swallowed as a repeat.
          request_id: `profile-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json();
      $("walletBalance").textContent = units(result.available_units);
      if (note) {
        note.textContent = `Зачислено ${units(Math.round(value * 100))}.`;
        note.classList.remove("is-off");
      }
      const ledger = await json("/api/profile/play-journal?limit=20");
      fill("ledger", (ledger.entries || []).map(ledgerRow), "Операций пока нет.");
    } catch (error) {
      console.error(error);
      if (note) {
        note.textContent = "Пополнение не прошло. Попробуйте ещё раз.";
        note.classList.add("is-off");
      }
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  function bindTopUp() {
    $("topupPresets")?.addEventListener("click", event => {
      const button = event.target.closest("button[data-amount]");
      if (!button) return;
      topUp(Number(button.dataset.amount) / 100);
    });
    $("topupSubmit")?.addEventListener("click", () => topUp($("topupAmount")?.value));
    $("topupAmount")?.addEventListener("keydown", event => {
      if (event.key === "Enter") topUp($("topupAmount").value);
    });
  }

  const CONFIDENCE = { low: "МАЛАЯ ВЫБОРКА", medium: "СРЕДНЯЯ ВЫБОРКА", high: "БОЛЬШАЯ ВЫБОРКА" };
  const bb = value => `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(1)} BB`;

  function renderStats(stats) {
    if (!stats) return;
    $("statsConfidence").textContent = CONFIDENCE[stats.confidence] || "—";
    $("statHands").textContent = stats.hands;
    $("statHandsWon").textContent = stats.hands_won;
    $("statSessions").textContent = stats.sessions;
    $("statDays").textContent = stats.days_played;
    // Null until a single hand has counted for a result -- a rate over no
    // hands is not zero, it is unknown, and printing 0.0 says the wrong thing.
    setSigned($("statBbPer100"), stats.bb_per_100, value => value.toFixed(1));
    setSigned($("statNetBb"), stats.net_bb, bb);
    $("statBiggestPot").textContent = `${Number(stats.biggest_pot_bb).toFixed(1)} BB`;
    $("statLongest").textContent = `${stats.longest_session_minutes} мин`;
    renderDay($("statBestDay"), stats.best_day);
    renderDay($("statWorstDay"), stats.worst_day);
  }

  function setSigned(element, value, format) {
    element.textContent = value == null ? "—" : format(value);
    // Break-even is not a win. Painting a flat zero green was the page
    // congratulating somebody for having played to a standstill.
    element.className = !value ? "" : value > 0 ? "up" : "down";
  }

  function renderDay(element, day) {
    if (!day) return void (element.textContent = "—");
    element.textContent = `${bb(day.net_bb)} · ${day.day.slice(5)}`;
    element.className = !day.net_bb ? "" : day.net_bb > 0 ? "up" : "down";
  }

  const countdown = seconds => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  };

  function renderMissions(payload) {
    if (!payload) return;
    const total = payload.missions.length;
    $("missionsHeading").textContent = `Сегодня ${payload.completed} / ${total}`;
    // A daily nobody can see the end of is a daily people forget exists.
    $("missionsReset").textContent = `ЧЕРЕЗ ${countdown(payload.resets_in_seconds)}`;
    $("missionsNote").textContent = payload.completed === total
      ? `Все задания выполнены · +${payload.completion_xp} XP`
      : payload.reroll_available
        ? "Одно задание в день можно заменить."
        : "Замена на сегодня использована.";
    $("missionList").innerHTML = payload.missions.map(item => {
      const share = Math.min(100, (item.progress / item.target) * 100);
      const swap = !item.done && payload.reroll_available
        ? `<button class="mission-reroll" type="button" data-reroll="${escapeHtml(item.slot)}">Заменить</button>`
        : "";
      return `
      <div class="mission ${item.done ? "done" : ""}">
        <div class="mission-copy">
          <b>${escapeHtml(item.title)}</b>
          <div class="mission-bar"><i style="width:${share}%"></i></div>
        </div>
        <span class="at">${item.done ? "✓" : `${item.progress} / ${item.target}`}</span>
        <span class="gain">+${item.xp} XP</span>
        ${swap}
      </div>`;
    }).join("");
    document.querySelectorAll("[data-reroll]").forEach(button => {
      button.addEventListener("click", () => rerollMission(button.dataset.reroll));
    });
  }

  async function rerollMission(slot) {
    const response = await fetch(`/api/profile/missions/${slot}/reroll`, { method: "POST" });
    if (!response.ok) return alert("Замена сейчас недоступна.");
    renderMissions(await json("/api/profile/missions").catch(() => null));
  }

  const RARITY = { common: "COMMON", rare: "RARE", epic: "EPIC", legendary: "LEGENDARY" };

  function renderAchievements(payload) {
    if (!payload) return;
    $("achievementPoints").textContent = `${payload.achievement_points} AP`;
    $("achievementsHeading").textContent = `Коллекция ${payload.completed} / ${payload.total}`;
    $("achievementList").innerHTML = payload.achievements.map(item => {
      const done = item.tier === item.tiers;
      // A tiered achievement shows the climb; a one-shot has nothing to show
      // but whether it happened.
      const share = item.next_threshold ? Math.min(100, (item.progress / item.next_threshold) * 100) : 100;
      const at = done
        ? "✓"
        : item.tiers > 1
          ? `${item.progress} / ${item.next_threshold}`
          : "—";
      return `
      <div class="achievement ${done ? "done" : "locked"}">
        <div class="achievement-copy">
          <b>${escapeHtml(item.title)}${item.tiers > 1 && item.tier ? ` · тир ${item.tier}` : ""}</b>
          ${item.tiers > 1 ? `<div class="achievement-bar"><i style="width:${share}%"></i></div>` : ""}
        </div>
        <span class="rarity">${RARITY[item.rarity] || ""}</span>
        <span class="at">${at}</span>
      </div>`;
    }).join("");
  }

  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $("profileName").textContent = profile.display_name;
    $("telegramId").textContent = `Telegram ID · ${profile.telegram_user_id}`;
    $("levelBadge").textContent = `LEVEL ${profile.level}`;
    $("rankBadge").textContent = profile.rank;
    $("xp").textContent = profile.xp;
    $("wins").textContent = profile.wins;
    $("hands").textContent = profile.hands_played;
    $("walletBalance").textContent = units(profile.available_units);
    $("tableStack").textContent = units(profile.active_table_stack_units);
    // The label under this reads "до следующего уровня", and the number used
    // to be the total wins so far -- which is not that number.
    const left = profile.xp_to_next_level;
    $("levelProgress").textContent = left == null ? "Максимальный уровень" : `Ещё ${left} XP`;
    $("levelProgress").nextElementSibling?.toggleAttribute("hidden", left == null);

    const returnLink = $("returnToTable");
    if (profile.active_table_id && returnLink) {
      returnLink.href = `/table?table=${encodeURIComponent(profile.active_table_id)}`;
      returnLink.hidden = false;
    }

    renderMissions(await json("/api/profile/missions").catch(() => null));
    renderStats(await json("/api/profile/stats").catch(() => null));
    renderAchievements(await json("/api/profile/achievements").catch(() => null));

    const [history, ledger, config] = await Promise.all([
      json("/api/profile/hands?limit=20"),
      json("/api/profile/play-journal?limit=20"),
      json("/api/config"),
    ]);
    fill("handHistory", (history.hands || []).map(handRow), "История появится после первой раздачи.");
    fill("ledger", (ledger.entries || []).map(ledgerRow), "Операций пока нет.");
    renderTopUp(Boolean(config.self_top_up_enabled));
    bindTopUp();
  }

  load().catch(error => {
    console.error(error);
    fill("handHistory", [], "Не удалось загрузить историю.");
    fill("ledger", [], "Не удалось загрузить журнал.");
    renderTopUp(false);
    const hero = document.querySelector(".profile-hero");
    if (hero && !hero.querySelector(".profile-error")) {
      const note = document.createElement("p");
      note.className = "profile-error";
      note.textContent = "Профиль не загрузился. Обновите страницу.";
      hero.appendChild(note);
    }
  });
})();
