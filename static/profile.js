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

  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $("profileName").textContent = profile.display_name;
    $("telegramId").textContent = `Telegram ID · ${profile.telegram_user_id}`;
    $("levelBadge").textContent = `LEVEL ${profile.level}`;
    $("wins").textContent = profile.wins;
    $("hands").textContent = profile.hands_played;
    $("walletBalance").textContent = units(profile.available_units);
    $("tableStack").textContent = units(profile.active_table_stack_units);
    // The label under this reads "до следующего уровня", and the number used
    // to be the total wins so far -- which is not that number.
    const left = profile.wins_to_next_level;
    $("levelProgress").textContent = left == null ? "Максимальный уровень" : `Ещё ${left} побед`;
    $("levelProgress").nextElementSibling?.toggleAttribute("hidden", left == null);

    const returnLink = $("returnToTable");
    if (profile.active_table_id && returnLink) {
      returnLink.href = `/table?table=${encodeURIComponent(profile.active_table_id)}`;
      returnLink.hidden = false;
    }

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
