// The CASH cashier: deposits (TRC20 and ₽ P2P) and withdrawals. Lifted
// out of the lobby when the money moved into the profile -- the lobby is for
// picking a table, and a balance shown in two places gives two answers.
window.Poker8Cashier = (() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const requestId = () => crypto.randomUUID?.() || `cashier-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const decimal = (value, digits) => {
    const amount = BigInt(value || 0);
    const scale = 10n ** BigInt(digits);
    const whole = amount / scale;
    const tail = String(amount % scale).padStart(digits, "0").replace(/0+$/, "");
    return tail ? `${whole}.${tail}` : String(whole);
  };
  const cashFromUsdt = value => {
    const match = String(value || "").trim().match(/^(\d+)(?:\.(\d{1,6}))?$/);
    if (!match) return "—";
    const micros = BigInt(match[1]) * 1000000n + BigInt((match[2] || "").padEnd(6, "0"));
    return decimal(micros, 5);
  };

  async function copyText(value, button) {
    try {
      await navigator.clipboard.writeText(value);
    } catch (_) {
      const scratch = document.createElement("textarea");
      scratch.value = value;
      scratch.setAttribute("readonly", "");
      scratch.style.cssText = "position:fixed;top:-1000px";
      document.body.appendChild(scratch);
      scratch.select();
      try { document.execCommand("copy"); } finally { scratch.remove(); }
    }
    const was = button.textContent;
    button.textContent = "Скопировано";
    setTimeout(() => { button.textContent = was; }, 1400);
  }

  // One row of the payment panel: what it is, what to type, and a way to take
  // it without retyping. Copying a card number by eye off a phone screen is
  // where a transfer goes to the wrong account.
  const payRow = (label, value, copyValue = value) => `
    <div class="pay-row"><span>${escape(label)}</span><b>${escape(value)}</b>
    <button type="button" class="pay-copy" data-copy="${escape(copyValue)}">Копировать</button></div>`;

  function bindCopy(root) {
    root.querySelectorAll("[data-copy]").forEach(button => {
      button.addEventListener("click", () => copyText(button.dataset.copy, button).catch(console.error));
    });
  }

  // Whatever the host page uses to redraw the balance once money has moved.
  let settled = () => {};
  const load = async () => { await settled(); };

  function bindConversion(inputId, outputId) {
    const update = () => { $(outputId).textContent = cashFromUsdt($(inputId).value); };
    $(inputId).addEventListener("input", update);
    update();
  }

  const FIAT_CLOSED = {
    unavailable: "Свободный трейдер не найден · попробуйте позже",
    credited: "Трейдер подтвердил · CASH зачислен",
    expired: "Срок заявки истёк · CASH не зачислен",
    cancelled: "Заявка отменена · CASH не зачислен",
    review_required: "Заявка на разборе у оператора · ждите ответа поддержки",
  };

  //: The states an order passes through on the way there. `pay` says whether
  //: the trader's requisites are on screen to be paid; `cancel` says whether
  //: dropping the order is still safe -- once the player has told the trader
  //: they paid, cancelling is how money goes missing, so it stops being offered
  //: and support takes over.
  const FIAT_OPEN = {
    requesting: {title: "Ищем трейдера…", note: "Реквизиты появятся, как только заявку примут.", pay: false, cancel: true},
    awaiting_user: {title: "Переведите точную сумму", note: "После перевода нажмите «Я оплатил».", pay: true, cancel: true},
    waiting_trader: {title: "Оплата отмечена · ждём подтверждения трейдера", note: "Обычно это несколько минут.", pay: true, cancel: false},
    clarifying: {title: "Трейдер уточняет платёж", note: "Напишите в поддержку, если ответа нет.", pay: true, cancel: false},
  };
  let fiatTicker = null;

  function fiatCountdown(order) {
    if (!order.expires_at) return "";
    const left = Math.round((new Date(order.expires_at).getTime() - Date.now()) / 1000);
    if (left <= 0) return "Время оплаты истекло, подтверждение зависит от трейдера";
    return `Осталось ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  }

  function renderFiatOrder(order) {
    const details = $("fiatDepositDetails");
    if (fiatTicker) { clearInterval(fiatTicker); fiatTicker = null; }
    if (!order) { details.hidden = true; details.innerHTML = ""; return; }
    details.hidden = false;
    if (FIAT_CLOSED[order.status]) {
      details.innerHTML = `<strong>${escape(FIAT_CLOSED[order.status])}</strong>` +
        (order.detail ? `<br>${escape(order.detail)}` : "");
      load().catch(console.error);
      return;
    }
    const stage = FIAT_OPEN[order.status] || FIAT_OPEN.requesting;
    details.innerHTML = `
      <strong>${escape(stage.title)}</strong>
      ${stage.pay && order.requisites ? `
        ${payRow("К оплате", `${order.fiat_rub} ₽`, order.fiat_rub)}
        ${payRow("Реквизиты", order.requisites, String(order.requisites).split(" · ")[0])}
      ` : ""}
      <p class="pay-note">${escape(stage.note)}</p>
      <p class="pay-note">Зачисление: ${escape(order.requested_units)} CASH (${escape(order.requested_usdt)} USDT)<br>
      Комиссия пополнения: ${escape(order.fee_usdt)} USDT · всего ${escape(order.charged_usdt)} USDT<br>
      <span id="fiatCountdown">${escape(fiatCountdown(order))}</span></p>
      ${order.status === "awaiting_user" ? '<button type="button" id="fiatPaid">Я оплатил</button>' : ""}
      ${stage.cancel ? '<button type="button" id="fiatCancel">Отменить заявку</button>' : ""}`;
    bindCopy(details);

    const act = async (path, failure) => {
      const response = await fetch(`/api/cash/fiat-orders/${encodeURIComponent(order.id)}/${path}`, { method: "POST" });
      if (!response.ok) return alert(failure);
      renderFiatOrder(await response.json());
    };
    $("fiatPaid")?.addEventListener("click", event => {
      event.currentTarget.disabled = true;
      act("paid", "Не удалось уведомить трейдера").catch(console.error);
    });
    $("fiatCancel")?.addEventListener("click", event => {
      event.currentTarget.disabled = true;
      act("cancel", "Не удалось отменить заявку").catch(console.error);
    });

    // The trader answers through the partner poller, so the page asks the
    // server rather than guessing that a notification means money.
    let ticks = 0;
    fiatTicker = setInterval(async () => {
      const countdown = $("fiatCountdown");
      if (countdown) countdown.textContent = fiatCountdown(order);
      if (++ticks % 3) return;
      const response = await fetch(`/api/cash/fiat-orders/${encodeURIComponent(order.id)}`);
      if (!response.ok) return;
      const fresh = await response.json();
      if (fresh.status !== order.status) renderFiatOrder(fresh);
    }, 1000);
  }

  // An order outlives the page it was opened from: reopen it rather than let
  // the player start a second one against the same money.
  async function restore() {
    const response = await fetch("/api/cash/fiat-orders/active");
    if (!response.ok) return;
    const order = await response.json();
    if (!order) return;
    renderFiatOrder(order);
    $("fiatDepositDialog").showModal();
  }

  function mount({ onSettled }) {
    settled = onSettled || (() => {});
    bindConversion("depositUsdt", "depositCash");
    bindConversion("fiatDepositUsdt", "fiatDepositCash");
    bindConversion("withdrawUsdt", "withdrawCash");
    // Two flows, one per screen. On a phone the rail is a step of its own --
    // one "Пополнить" opens a sheet that asks how, the way CASE8 does it,
    // because two buttons of equal weight is a decision nobody wants to make
    // on a wallet screen. On a desktop there is room to just show both, and
    // an extra modal in the way is only an extra click.
    const phone = window.matchMedia("(max-width: 640px)");
    const syncDepositFlow = () => {
      $("cashDeposit").textContent = phone.matches ? "Пополнить" : "Пополнить TRC20";
      $("cashFiatDeposit").hidden = phone.matches;
      // A sheet left open across a resize would be a centred dialog pinned to
      // the bottom edge, or the reverse.
      if ($("depositMethodDialog").open && !phone.matches) $("depositMethodDialog").close("cancel");
    };
    syncDepositFlow();
    phone.addEventListener("change", syncDepositFlow);

    $("cashDeposit").addEventListener("click", () => {
      $(phone.matches ? "depositMethodDialog" : "depositDialog").showModal();
    });
    $("cashFiatDeposit").addEventListener("click", () => $("fiatDepositDialog").showModal());
    $("depositMethodForm").addEventListener("click", event => {
      const chosen = event.target.closest("[data-method]");
      if (!chosen) return;
      $("depositMethodDialog").close("cancel");
      $(chosen.dataset.method === "fiat" ? "fiatDepositDialog" : "depositDialog").showModal();
    });
    $("cashWithdraw").addEventListener("click", () => $("withdrawDialog").showModal());
    // A button with no type inside a form is a submit button, so the dialog
    // cross would submit the form it was meant to abandon.
    document.querySelectorAll(".cash-dialog .dialog-close").forEach(button => {
      button.addEventListener("click", () => button.closest("dialog")?.close("cancel"));
    });

    $("depositForm").addEventListener("submit", async event => {
      event.preventDefault();
      const response = await fetch("/api/cash/deposits", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ amount_usdt: $("depositUsdt").value, request_id: requestId() }),
      });
      const payload = await response.json();
      if (!response.ok) return alert(payload.detail || "Не удалось создать заявку");
      const details = $("depositDetails");
      details.hidden = false;
      details.innerHTML = `
        <strong>Отправьте ровно эту сумму на этот адрес</strong>
        ${payRow("Сумма", `${payload.expected_usdt} USDT`, payload.expected_usdt)}
        ${payRow("Адрес", payload.address)}
        <p class="pay-note">Сеть: ${escape(payload.network)} · зачисление ${escape(payload.expected_units)} CASH</p>
        <button type="button" data-paid="${escape(payload.id)}">Подтвердить перевод</button>`;
      bindCopy(details);
      details.querySelector("[data-paid]").addEventListener("click", async buttonEvent => {
        const button = buttonEvent.currentTarget;
        button.disabled = true;
        const confirmed = await fetch(`/api/cash/deposits/${encodeURIComponent(button.dataset.paid)}/simulate-transfer`, { method: "POST" });
        if (!confirmed.ok) {
          button.disabled = false;
          return alert("Подтверждение не прошло");
        }
        button.textContent = "Перевод подтверждён";
        await load();
      });
    });

    $("fiatDepositForm").addEventListener("submit", async event => {
      event.preventDefault();
      const response = await fetch("/api/cash/fiat-orders", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ amount_usdt: $("fiatDepositUsdt").value, request_id: requestId() }),
      });
      const payload = await response.json();
      if (response.status === 409) return restore();
      if (!response.ok) return alert(payload.detail || "Не удалось получить реквизиты");
      renderFiatOrder(payload);
    });

    $("withdrawForm").addEventListener("submit", async event => {
      event.preventDefault();
      const response = await fetch("/api/cash/withdrawals", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          amount_usdt: $("withdrawUsdt").value,
          address: $("withdrawAddress").value,
          request_id: requestId(),
        }),
      });
      const payload = await response.json();
      if (!response.ok) return alert(payload.detail || "Не удалось создать вывод");
      const details = $("withdrawDetails");
      details.hidden = false;
      details.innerHTML = `<strong>${escape(payload.amount_units)} CASH зарезервировано</strong><br>
        К выплате: ${escape(payload.payout_usdt)} USDT<br>Комиссия: ${escape(payload.fee_usdt)} USDT<br>
        Статус: ${escape(payload.status)} · ${escape(payload.network)}`;
      await load();
    });

    restore().catch(console.error);
  }

  return { mount };
})();
