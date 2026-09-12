// Support tickets on the profile: what is open, a form to write, and the
// thread behind each one. The answer also lands in the Telegram bot, so the
// thread here is polled while it is on screen rather than pushed.
window.Poker8Support = (() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const when = iso => new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  const STATUS = {
    open: ["Ждёт ответа", "is-waiting"],
    answered: ["Есть ответ", ""],
    closed: ["Закрыто", "is-closed"],
  };

  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Не удалось выполнить запрос");
    return payload;
  }

  // The picture goes up as base64 inside the JSON: nothing else on the site
  // uploads a file, and this is one request rather than a second flow.
  const photoOf = input => new Promise((resolve, reject) => {
    const file = input.files?.[0];
    if (!file) return resolve(null);
    if (file.size > 5 * 1024 * 1024) return reject(new Error("Изображение не больше 5 МБ"));
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Не удалось прочитать файл"));
    reader.onload = () => resolve({ content_type: file.type, data: String(reader.result).split(",", 2)[1] });
    reader.readAsDataURL(file);
  });

  const row = ticket => {
    const [label, tone] = STATUS[ticket.status] || STATUS.open;
    const preview = (ticket.last_author === "operator" ? "Поддержка: " : "") + (ticket.last_text || "изображение");
    return `<button type="button" class="support-row" data-ticket="${escape(ticket.id)}">
      <span><strong>#${escape(ticket.short_id)} · ${escape(ticket.topic_label)}${ticket.reference_label ? ` · ${escape(ticket.reference_label)}` : ""}</strong>
      <small>${escape(preview)}</small></span>
      <span class="support-badge ${tone}">${label}</span></button>`;
  };

  async function refresh() {
    const { tickets } = await api("/api/support/tickets");
    $("supportList").innerHTML = tickets.length
      ? tickets.map(row).join("")
      : '<p class="history-empty">Нет активных обращений</p>';
    if (!$("supportClosed").hidden) await loadClosed();
  }

  async function loadClosed() {
    const { tickets } = await api("/api/support/tickets?closed=true");
    $("supportClosed").innerHTML = tickets.length
      ? tickets.map(row).join("")
      : '<p class="history-empty">Закрытых обращений пока нет</p>';
  }

  // --- the thread -----------------------------------------------------------

  let ticker = null;
  let openId = null;

  function renderThread(ticket) {
    $("ticketTitle").textContent = `Обращение #${ticket.short_id}`;
    const [label] = STATUS[ticket.status] || STATUS.open;
    $("ticketSub").textContent = `${ticket.topic_label}${ticket.reference_label ? ` · ${ticket.reference_label}` : ""} · ${label}`;
    $("ticketThread").innerHTML = ticket.messages.map(message => `
      <div class="support-msg ${message.author === "user" ? "is-user" : ""}">${escape(message.text) || "<i>изображение</i>"}${message.has_photo && message.text ? " 📎" : ""}<small>${message.author === "user" ? "Вы" : "Поддержка"} · ${when(message.created_at)}</small></div>`).join("");
    $("ticketThread").scrollTop = $("ticketThread").scrollHeight;
    $("ticketReply").hidden = ticket.status === "closed";
  }

  async function openTicket(id) {
    openId = id;
    renderThread(await api(`/api/support/tickets/${encodeURIComponent(id)}`));
    $("ticketFormError").hidden = true;
    $("ticketDialog").showModal();
    clearInterval(ticker);
    ticker = setInterval(async () => {
      if (!$("ticketDialog").open) return clearInterval(ticker);
      const fresh = await api(`/api/support/tickets/${encodeURIComponent(id)}`).catch(() => null);
      if (fresh) renderThread(fresh);
    }, 5000);
  }

  const fail = (id, error) => { $(id).textContent = error.message; $(id).hidden = false; };

  // --- the form -------------------------------------------------------------

  let topic = "support";
  const selectTopic = value => {
    topic = value;
    $("supportTopics").querySelectorAll("[data-topic]").forEach(pill => {
      const on = pill.dataset.topic === value;
      pill.classList.toggle("is-active", on);
      pill.setAttribute("aria-checked", String(on));
    });
    $("supportReference").hidden = $("supportReferenceLabel").hidden = value !== "finance";
  };

  async function loadReferences() {
    const { references } = await api("/api/support/references").catch(() => ({ references: [] }));
    $("supportReference").innerHTML = '<option value="">Без привязки к заявке</option>' + references.map(item =>
      `<option value="${escape(item.kind)}:${escape(item.id)}">${escape(item.label)} · ${escape(item.amount)} · ${escape(item.status)} · ID ${escape(item.partner_id || item.id.slice(0, 8))}</option>`).join("");
  }

  function mount() {
    $("supportSection").hidden = false;
    refresh().catch(error => { $("supportList").innerHTML = `<p class="history-error">${escape(error.message)}</p>`; });

    $("supportNew").addEventListener("click", () => {
      $("supportForm").reset();
      $("supportFormError").hidden = true;
      selectTopic("support");
      loadReferences().catch(console.error);
      $("supportDialog").showModal();
    });
    $("supportTopics").addEventListener("click", event => {
      const pill = event.target.closest("[data-topic]");
      if (pill) selectTopic(pill.dataset.topic);
    });
    $("supportHistory").addEventListener("click", async () => {
      const closed = $("supportClosed");
      closed.hidden = !closed.hidden;
      $("supportHistory").setAttribute("aria-expanded", String(!closed.hidden));
      $("supportHistory").classList.toggle("is-active", !closed.hidden);
      if (!closed.hidden) await loadClosed().catch(console.error);
    });
    // The file control is hidden behind its label; the chosen name is shown
    // beside the button, and a reset clears it with the form.
    document.querySelectorAll(".support-file input").forEach(input => {
      const label = input.closest(".support-file");
      const sync = () => {
        const file = input.files?.[0];
        label.querySelector(".support-file-name").textContent = file ? file.name : "";
        label.classList.toggle("has-file", Boolean(file));
      };
      input.addEventListener("change", sync);
      input.form?.addEventListener("reset", () => setTimeout(sync));
    });
    $("supportSection").addEventListener("click", event => {
      const target = event.target.closest("[data-ticket]");
      if (target) openTicket(target.dataset.ticket).catch(console.error);
    });
    document.querySelectorAll("#supportDialog .dialog-close, #ticketDialog .dialog-close").forEach(button => {
      button.addEventListener("click", () => button.closest("dialog")?.close("cancel"));
    });

    $("supportForm").addEventListener("submit", async event => {
      event.preventDefault();
      const submit = event.submitter || event.target.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const [kind, ...rest] = ($("supportReference").value || "").split(":");
        await api("/api/support/tickets", {
          topic, text: $("supportText").value,
          reference_kind: topic === "finance" && kind ? kind : null,
          reference_id: topic === "finance" && kind ? rest.join(":") : null,
          photo: await photoOf($("supportPhoto")),
        });
        $("supportDialog").close();
        await refresh();
      } catch (error) {
        fail("supportFormError", error);
      } finally {
        submit.disabled = false;
      }
    });

    $("ticketForm").addEventListener("submit", async event => {
      event.preventDefault();
      const submit = event.submitter || event.target.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        renderThread(await api(`/api/support/tickets/${encodeURIComponent(openId)}/messages`, {
          text: $("ticketText").value, photo: await photoOf($("ticketPhoto")),
        }));
        $("ticketText").value = "";
        $("ticketPhoto").value = "";
        $("ticketPhoto").dispatchEvent(new Event("change"));
        await refresh();
      } catch (error) {
        fail("ticketFormError", error);
      } finally {
        submit.disabled = false;
      }
    });
    $("ticketClose").addEventListener("click", async () => {
      if (!confirm("Закрыть обращение?")) return;
      try {
        await api(`/api/support/tickets/${encodeURIComponent(openId)}/close`, {});
        $("ticketDialog").close();
        await refresh();
      } catch (error) {
        fail("ticketFormError", error);
      }
    });
  }

  return { mount, refresh };
})();
