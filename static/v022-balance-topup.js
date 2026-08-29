(() => {
  "use strict";

  // The trainer's own top-up, end to end: click your stack, grant yourself
  // play money. It has no place on a network table, and online it was worse
  // than useless -- the "+" it prints on your seat posts to
  // /api/profiles/{id}/top-up, which lives in app/legacy.py and production
  // does not mount. A live button with a 404 behind it.
  //
  // Wiring it to the online route instead would be wrong on purpose: that
  // one (POST /api/profiles/play-top-up) is gated on self_top_up_enabled and
  // stays off on a deployment, because money there has to arrive through a
  // payment. Online already has the dialog for that, with the seam a payment
  // flow plugs into (window.Poker8TopUp, online-table.js) -- and until
  // somebody plugs one in, a seat that offers nothing is more honest than a
  // seat that offers a 404.
  if (window.Poker8OnlineTable) return;

  function viewerProfileId() {
    const viewer = typeof localViewerPlayer === "function" ? localViewerPlayer() : null;
    return viewer?.profile_id || tableData?.profile?.id || tableData?.active_profile_id || null;
  }

  function viewerBalance() {
    const profileId = viewerProfileId();
    if (!profileId) return 0;

    const profile = tableData?.profiles?.find?.(row => row.id === profileId);
    if (profile && Number.isFinite(Number(profile.balance))) return Number(profile.balance);
    if (tableData?.profile?.id === profileId) return Number(tableData.profile.balance || tableData.profile.hero_balance || 0);

    const viewer = typeof localViewerPlayer === "function" ? localViewerPlayer() : null;
    return Number(viewer?.stack || 0);
  }

  function formatAmount(value) {
    return `${Number(value || 0).toFixed(2)} ББ`;
  }

  function modalNode() {
    let backdrop = document.getElementById("v022TopupBackdrop");
    if (backdrop) return backdrop;

    backdrop = document.createElement("div");
    backdrop.id = "v022TopupBackdrop";
    backdrop.className = "v022-topup-backdrop";
    backdrop.hidden = true;
    backdrop.innerHTML = `
      <section class="v022-topup-modal" role="dialog" aria-modal="true" aria-labelledby="v022TopupTitle">
        <button id="v022TopupClose" class="v022-topup-close" type="button" aria-label="Закрыть">×</button>
        <div class="v022-topup-kicker">БАЛАНС</div>
        <h3 id="v022TopupTitle">Пополнить баланс</h3>
        <div class="v022-topup-current">Сейчас <strong id="v022TopupCurrent">0.00 ББ</strong></div>
        <div class="v022-topup-presets">
          <button type="button" data-v022-amount="100">+100</button>
          <button type="button" data-v022-amount="500">+500</button>
          <button type="button" data-v022-amount="1000">+1000</button>
        </div>
        <label class="v022-topup-field">
          <span>Сумма пополнения</span>
          <div><input id="v022TopupAmount" type="number" min="0.5" max="1000000" step="0.5" inputmode="decimal" value="100" /><b>ББ</b></div>
        </label>
        <div class="v022-topup-preview">После пополнения <strong id="v022TopupPreview">0.00 ББ</strong></div>
        <div id="v022TopupError" class="v022-topup-error" hidden></div>
        <button id="v022TopupSubmit" class="v022-topup-submit" type="button">Пополнить</button>
      </section>
    `;
    document.body.appendChild(backdrop);

    const close = () => {
      backdrop.hidden = true;
      document.body.classList.remove("v022-topup-open");
    };

    backdrop.addEventListener("click", event => {
      if (event.target === backdrop) close();
    });
    backdrop.querySelector("#v022TopupClose")?.addEventListener("click", close);

    const input = backdrop.querySelector("#v022TopupAmount");
    const updatePreview = () => {
      const current = viewerBalance();
      const amount = Math.max(0, Number(input?.value || 0));
      const currentEl = backdrop.querySelector("#v022TopupCurrent");
      const previewEl = backdrop.querySelector("#v022TopupPreview");
      if (currentEl) currentEl.textContent = formatAmount(current);
      if (previewEl) previewEl.textContent = formatAmount(current + amount);
    };

    input?.addEventListener("input", updatePreview);
    backdrop.querySelectorAll("[data-v022-amount]").forEach(button => {
      button.addEventListener("click", () => {
        if (input) input.value = button.dataset.v022Amount || "100";
        updatePreview();
      });
    });

    backdrop.querySelector("#v022TopupSubmit")?.addEventListener("click", async () => {
      const profileId = viewerProfileId();
      const amount = Number(input?.value || 0);
      const errorEl = backdrop.querySelector("#v022TopupError");
      const submit = backdrop.querySelector("#v022TopupSubmit");

      if (!profileId) {
        if (errorEl) {
          errorEl.hidden = false;
          errorEl.textContent = "Не удалось определить профиль игрока.";
        }
        return;
      }
      if (!(amount > 0) || amount > 1000000) {
        if (errorEl) {
          errorEl.hidden = false;
          errorEl.textContent = "Введите корректную сумму пополнения.";
        }
        return;
      }

      if (errorEl) errorEl.hidden = true;
      if (submit) {
        submit.disabled = true;
        submit.textContent = "Пополняем…";
      }

      try {
        const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}/top-up`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ amount }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Не удалось пополнить баланс");

        if (tableData) {
          tableData.seats = data.table || tableData.seats;
          tableData.profile = data.profile || tableData.profile;
          if (Array.isArray(tableData.profiles) && data.profile) {
            tableData.profiles = tableData.profiles.map(row =>
              row.id === data.profile.id ? { ...row, balance: data.profile.balance } : row
            );
          }
        }

        if (game?.terminal && data.profile) {
          const viewer = typeof localViewerPlayer === "function" ? localViewerPlayer() : null;
          if (viewer?.profile_id === data.profile.id) viewer.stack = Number(data.profile.balance || 0);
          game.training_profile = data.profile;
        }

        if (data.profile && typeof renderProfile === "function") renderProfile(data.profile);
        if (typeof renderSeats === "function") renderSeats();
        if (typeof renderMobileHud === "function") renderMobileHud();

        close();
      } catch (error) {
        if (errorEl) {
          errorEl.hidden = false;
          errorEl.textContent = error?.message || "Не удалось пополнить баланс";
        }
      } finally {
        if (submit) {
          submit.disabled = false;
          submit.textContent = "Пополнить";
        }
      }
    });

    backdrop._v022UpdatePreview = updatePreview;
    return backdrop;
  }

  function openTopup() {
    if (game && !game.terminal) {
      alert("Пополнять баланс можно после завершения текущей раздачи.");
      return;
    }

    const backdrop = modalNode();
    const input = backdrop.querySelector("#v022TopupAmount");
    const errorEl = backdrop.querySelector("#v022TopupError");
    if (input) input.value = "100";
    if (errorEl) errorEl.hidden = true;
    backdrop._v022UpdatePreview?.();
    backdrop.hidden = false;
    document.body.classList.add("v022-topup-open");
    setTimeout(() => input?.focus(), 40);
  }

  document.addEventListener("click", event => {
    const stack = event.target?.closest?.('.seat[data-visual-seat="0"] .seat-card.viewer-seat .seat-stack');
    if (!stack) return;
    event.preventDefault();
    event.stopPropagation();
    openTopup();
  }, true);

  const style = document.createElement("style");
  style.id = "v022-balance-topup-style";
  style.textContent = `
    body.v014 .seat[data-visual-seat="0"] .seat-card.viewer-seat .seat-stack{
      position:relative !important;
      display:inline-flex !important;
      align-items:center !important;
      justify-content:center !important;
      gap:5px !important;
      min-width:84px !important;
      padding:4px 18px 4px 8px !important;
      border-radius:9px !important;
      cursor:pointer !important;
      pointer-events:auto !important;
      user-select:none !important;
      transition:background .16s ease, transform .16s ease !important;
    }
    body.v014 .seat[data-visual-seat="0"] .seat-card.viewer-seat .seat-stack::after{
      content:"+";
      position:absolute;
      right:5px;
      top:50%;
      transform:translateY(-50%);
      width:13px;
      height:13px;
      display:grid;
      place-items:center;
      border-radius:50%;
      background:rgba(53,198,255,.16);
      color:#6edcff;
      font-size:12px;
      font-weight:950;
      line-height:1;
    }
    body.v014 .seat[data-visual-seat="0"] .seat-card.viewer-seat .seat-stack:active{
      transform:scale(.97) !important;
      background:rgba(56,169,255,.08) !important;
    }

    .v022-topup-backdrop{
      position:fixed;
      inset:0;
      z-index:5000;
      display:flex;
      align-items:flex-end;
      justify-content:center;
      padding:14px;
      background:rgba(1,3,10,.72);
      backdrop-filter:blur(8px);
    }
    .v022-topup-backdrop[hidden]{display:none !important}
    .v022-topup-modal{
      position:relative;
      width:min(100%,390px);
      box-sizing:border-box;
      padding:18px 16px calc(18px + env(safe-area-inset-bottom));
      border:1px solid rgba(70,164,255,.34);
      border-radius:22px;
      background:linear-gradient(180deg,rgba(4,12,31,.99),rgba(2,6,18,.995));
      box-shadow:0 20px 70px rgba(0,0,0,.55),inset 0 0 28px rgba(48,116,255,.05);
      color:#f2f6ff;
    }
    .v022-topup-close{
      position:absolute;
      top:10px;
      right:11px;
      width:34px;
      height:34px;
      border:0;
      border-radius:10px;
      background:rgba(255,255,255,.055);
      color:#9aa9c1;
      font-size:27px;
    }
    .v022-topup-kicker{font-size:10px;font-weight:900;letter-spacing:.15em;color:#60d8ff}
    .v022-topup-modal h3{margin:4px 0 7px;font-size:20px;line-height:1.1}
    .v022-topup-current,.v022-topup-preview{font-size:12px;color:#7e91ab}
    .v022-topup-current strong,.v022-topup-preview strong{color:#ffffff}
    .v022-topup-presets{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:14px 0 12px}
    .v022-topup-presets button{
      min-height:42px;
      border:1px solid rgba(82,141,230,.34);
      border-radius:11px;
      background:rgba(4,20,42,.88);
      color:#dceaff;
      font-weight:900;
      font-size:12px;
    }
    .v022-topup-field{display:block;margin-top:5px}
    .v022-topup-field>span{display:block;margin:0 0 6px;font-size:10px;color:#8e9bb1}
    .v022-topup-field>div{
      display:grid;
      grid-template-columns:1fr auto;
      align-items:center;
      min-height:48px;
      padding:0 12px;
      border:1px solid rgba(84,155,255,.42);
      border-radius:12px;
      background:rgba(2,6,18,.94);
    }
    .v022-topup-field input{
      width:100%;
      border:0;
      outline:0;
      background:transparent;
      color:#ffffff;
      font-size:20px;
      font-weight:950;
    }
    .v022-topup-field b{font-size:12px;color:#75cfff}
    .v022-topup-preview{margin:8px 2px 0}
    .v022-topup-error{margin-top:8px;color:#ff91a8;font-size:10px;line-height:1.3}
    .v022-topup-submit{
      width:100%;
      min-height:48px;
      margin-top:14px;
      border:1px solid rgba(79,223,186,.48);
      border-radius:13px;
      background:linear-gradient(180deg,rgba(20,88,71,.88),rgba(9,51,42,.96));
      color:#b7ffe7;
      font-size:15px;
      font-weight:950;
    }
    .v022-topup-submit:disabled{opacity:.55}

    @media (min-width:781px){
      .v022-topup-backdrop{align-items:center}
    }
  `;
  document.head.appendChild(style);
})();
