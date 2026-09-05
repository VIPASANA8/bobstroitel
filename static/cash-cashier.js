// The CASH cashier: deposits (TRC20 mock and ₽ P2P) and withdrawals. Lifted
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
    const waiting = order.status !== "awaiting_user";
    details.innerHTML = `
      <strong>К оплате: ${escape(order.fiat_rub)} ₽</strong><br>
      Реквизиты: ${escape(order.requisites)}<br>
      Зачисление: ${escape(order.requested_units)} CASH (${escape(order.requested_usdt)} USDT)<br>
      Комиссия пополнения: ${escape(order.fee_usdt)} USDT · всего ${escape(order.charged_usdt)} USDT<br>
      <span id="fiatCountdown">${escape(fiatCountdown(order))}</span><br>
      ${order.status === "clarifying" ? "<strong>Трейдер уточняет платёж · напишите в поддержку</strong><br>" : ""}
      ${waiting ? "<strong>Оплата отмечена · ждём подтверждения трейдера</strong>"
                : '<button type="button" id="fiatPaid">Я оплатил</button>'}
      <button type="button" id="fiatCancel">Отменить заявку</button>`;

    const act = async (path, failure) => {
      const response = await fetch(`/api/cash/fiat-orders/${encodeURIComponent(order.id)}/${path}`, { method: "POST" });
      if (!response.ok) return alert(failure);
      renderFiatOrder(await response.json());
    };
    $("fiatPaid")?.addEventListener("click", event => {
      event.currentTarget.disabled = true;
      act("paid", "Не удалось уведомить трейдера").catch(console.error);
    });
    $("fiatCancel").addEventListener("click", event => {
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

  function mount({ onSettled, testMode }) {
    settled = onSettled || (() => {});
    $("cashWithdraw").textContent = testMode ? "Вывести mock USDT" : "Вывести USDT";
    bindConversion("depositUsdt", "depositCash");
    bindConversion("fiatDepositUsdt", "fiatDepositCash");
    bindConversion("withdrawUsdt", "withdrawCash");
    $("cashDeposit").addEventListener("click", () => $("depositDialog").showModal());
    $("cashFiatDeposit").addEventListener("click", () => $("fiatDepositDialog").showModal());
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
        <strong>Отправьте ровно ${escape(payload.expected_usdt)} USDT</strong><br>
        Сеть: ${escape(payload.network)}<br>Адрес: ${escape(payload.address)}<br>
        Зачисление: ${escape(payload.expected_units)} CASH<br>
        <button type="button" data-paid="${escape(payload.id)}">Симулировать подтверждение сети</button>`;
      details.querySelector("[data-paid]").addEventListener("click", async buttonEvent => {
        const button = buttonEvent.currentTarget;
        button.disabled = true;
        const confirmed = await fetch(`/api/cash/deposits/${encodeURIComponent(button.dataset.paid)}/simulate-transfer`, { method: "POST" });
        if (!confirmed.ok) {
          button.disabled = false;
          return alert("Mock-подтверждение не прошло");
        }
        button.textContent = "Mock-перевод подтверждён";
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
