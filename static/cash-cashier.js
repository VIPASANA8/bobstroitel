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

  // What the copy button puts on the clipboard: the number alone. A real
  // trader_info is a card or a phone wrapped in instructions ("‼️ СТРОГО
  // Альфа … перевод на другой банк = потеря средств"); pasting all of that
  // into a bank app is how the transfer does not happen. The text itself
  // stays on screen, line breaks and all, because those instructions matter.
  const requisiteNumber = text => {
    const match = String(text || "").match(/\+?\d[\d ]{8,}\d/);
    return match ? match[0].trim() : String(text || "");
  };

  // No button on this one: one tap selects the whole id and the phone's own
  // copy handle comes up, which is the gesture people already use on anything
  // that looks like a reference number.
  const idRow = (label, value) => `
    <div class="pay-row"><span>${escape(label)}</span><b class="pay-id">${escape(value)}</b></div>`;

  function bindCopy(root) {
    root.querySelectorAll("[data-copy]").forEach(button => {
      button.addEventListener("click", () => copyText(button.dataset.copy, button).catch(console.error));
    });
  }

  // Whatever the host page uses to redraw the balance once money has moved.
  let settled = () => {};
  const load = async () => { await settled(); };
  // The last wallet payload the page fetched: the ₽ rate and the payout fee
  // ride on it, and the withdrawal form quotes from them.
  let wallet = {};
  let onWallet = () => {};
  const setWallet = payload => { wallet = payload || {}; onWallet(); };

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
        ${payRow("Реквизиты", order.requisites, requisiteNumber(order.requisites))}
      ` : ""}
      ${order.partner_order_id ? idRow("ID заявки", order.partner_order_id) : ""}
      <p class="pay-note">${escape(stage.note)}</p>
      <p class="pay-note">Зачисление: ${escape(order.requested_units)} CASH (${escape(order.requested_usdt)} USDT)<br>
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
      // Not only the status: the amount or the requisites can be corrected
      // under the same status, and a card number nobody sees is not paid.
      if (JSON.stringify(fresh) !== JSON.stringify(order)) renderFiatOrder(fresh);
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

  function mount({ onSettled, trc20 = true }) {
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
    // With one rail there is nothing to choose: the ₽ button is the deposit.
    $("cashDeposit").hidden = !trc20;
    document.querySelector('[data-method="crypto"]').hidden = !trc20;
    const syncDepositFlow = () => {
      $("cashDeposit").textContent = phone.matches ? "Пополнить" : "Пополнить TRC20";
      $("cashFiatDeposit").hidden = phone.matches && trc20;
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
      // Scanning beats copying on a phone, where the wallet is the app the
      // player is about to switch to anyway. Null when the address somehow
      // will not fit a code, and then the rows below still carry it.
      const code = window.Poker8QR?.svg(payload.address, {label: "QR-код адреса пополнения"});
      details.innerHTML = `
        <strong>Отправьте ровно эту сумму на этот адрес</strong>
        ${code ? `<div class="pay-qr">${code}</div>` : ""}
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

    // Where the money goes out: USDT to a TRC20 address, or roubles to a
    // card at the rate an operator set. The ₽ pill only appears once there
    // is a rate -- without one nothing can be promised, so nothing is asked.
    let withdrawRail = "TRC20";
    const rails = { TRC20: { label: "Адрес TRC20", placeholder: "T..." },
                    P2P_RUB: { label: "Номер карты или телефон СБП", placeholder: "2200 0000 0000 0000" } };
    const quoteRub = () => {
      const quote = $("withdrawQuote");
      if (withdrawRail !== "P2P_RUB" || !wallet.rub_rate) return (quote.textContent = "");
      const fee = Number(String(wallet.rub_withdrawal_fee_usdt ?? "0").replace(",", "."));
      const net = Number($("withdrawUsdt").value || 0) - fee;
      const rate = Number(String(wallet.rub_rate).replace(",", "."));
      const rub = Math.max(0, net) * rate;
      const min = Number(String(wallet.rub_min_payout || "0").replace(",", "."));
      const money = value => value.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      // Under the floor the number is not a quote, it is what would be refused.
      quote.textContent = rub < min
        ? ` · минимум ${money(min)} ₽ — это от ${money(Math.ceil((min / rate + fee) * 100) / 100)} USDT`
        : ` · ≈ ${money(rub)} ₽ по курсу ${wallet.rub_rate} ₽/USDT`;
    };
    const selectRail = rail => {
      withdrawRail = rail;
      $("withdrawRails").querySelectorAll("[data-rail]").forEach(pill => {
        const on = pill.dataset.rail === rail;
        pill.classList.toggle("is-active", on);
        pill.setAttribute("aria-checked", String(on));
      });
      $("withdrawAddressLabel").textContent = rails[rail].label;
      $("withdrawAddress").placeholder = rails[rail].placeholder;
      quoteRub();
    };
    $("withdrawRails").addEventListener("click", event => {
      const pill = event.target.closest("[data-rail]");
      if (pill) selectRail(pill.dataset.rail);
    });
    $("withdrawUsdt").addEventListener("input", quoteRub);
    onWallet = () => {
      const rub = $("withdrawRails").querySelector('[data-rail="P2P_RUB"]');
      rub.hidden = !wallet.rub_rate;
      if (rub.hidden && withdrawRail === "P2P_RUB") selectRail("TRC20");
      quoteRub();
    };
    onWallet();

    $("withdrawForm").addEventListener("submit", async event => {
      event.preventDefault();
      const response = await fetch("/api/cash/withdrawals", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({
          amount_usdt: $("withdrawUsdt").value,
          address: $("withdrawAddress").value,
          rail: withdrawRail,
          request_id: requestId(),
        }),
      });
      const payload = await response.json();
      if (!response.ok) return alert(payload.detail || "Не удалось создать вывод");
      const details = $("withdrawDetails");
      details.hidden = false;
      // "К выплате" is already the net amount; itemising what was taken off
      // it only invites the arithmetic to be checked.
      details.innerHTML = `<strong>${escape(payload.amount_units)} CASH зарезервировано</strong><br>
        К выплате: ${payload.quote_rub ? `${escape(payload.quote_rub)} ₽ на карту` : `${escape(payload.payout_usdt)} USDT`}<br>
        Статус: ${escape(payload.status)} · ${escape(payload.network)}`;
      await load();
    });

    restore().catch(console.error);
  }

  return { mount, wallet: setWallet };
})();
