(() => {
  "use strict";

  function preHandPhase() {
    return !game || Boolean(game.terminal);
  }

  function heroReadyBadge() {
    return document.querySelector('.seat[data-visual-seat="0"] .v024-ready-badge');
  }

  function ensureCenterReady() {
    const felt = document.querySelector(".felt");
    if (!felt) return null;

    let wrap = document.getElementById("v028CenterReady");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "v028CenterReady";
      wrap.className = "v028-center-ready";
      wrap.innerHTML = `
        <div class="v028-center-status"><i></i><strong>НЕ ГОТОВ</strong></div>
        <button class="v028-center-ready-button" type="button">ГОТОВ</button>
      `;
      felt.appendChild(wrap);

      wrap.querySelector(".v028-center-ready-button")?.addEventListener("click", () => {
        const source = $("mobilePrimaryAction") || $("newHand");
        if (!source || source.disabled) return;
        source.click();
        setTimeout(syncCenterReadyUi, 0);
      });
    }
    return wrap;
  }

  function syncCenterReadyUi() {
    const wrap = ensureCenterReady();
    if (!wrap) return;

    const preHand = preHandPhase();
    wrap.hidden = !preHand;
    document.body.classList.toggle("v028-prehand-center-ready", preHand);
    if (!preHand) return;

    const badge = heroReadyBadge();
    const ready = Boolean(badge?.classList.contains("ready"));
    const status = wrap.querySelector(".v028-center-status");
    const statusText = status?.querySelector("strong");
    const button = wrap.querySelector(".v028-center-ready-button");
    const source = $("mobilePrimaryAction") || $("newHand");

    status?.classList.toggle("ready", ready);
    status?.classList.toggle("waiting", !ready);
    if (statusText) statusText.textContent = ready ? "ГОТОВ" : "НЕ ГОТОВ";

    if (button) {
      const sourceText = String(source?.textContent || "").trim().toUpperCase();
      const startReady = ready && /НАЧАТЬ/.test(sourceText);
      button.textContent = startReady ? "НАЧАТЬ" : "ГОТОВ";
      button.disabled = Boolean(source?.disabled);
      button.classList.toggle("start", startReady);
    }
  }

  const previousRenderSeats = renderSeats;
  renderSeats = function renderSeatsV028() {
    previousRenderSeats();
    syncCenterReadyUi();
  };

  const previousRenderMobileHeader = renderMobileHeader;
  renderMobileHeader = function renderMobileHeaderV028() {
    previousRenderMobileHeader();
    syncCenterReadyUi();
  };

  const previousSyncComponentUi = window.syncComponentUi;
  window.syncComponentUi = function syncComponentUiV028(gameState, tableState) {
    previousSyncComponentUi?.(gameState, tableState);
    syncCenterReadyUi();
  };

  const style = document.createElement("style");
  style.id = "v028-center-ready-style";
  style.textContent = `
    @media (max-width:780px){
      /* The viewer readiness no longer lives under the hero card. */
      body.v014.v028-prehand-center-ready .seat[data-visual-seat="0"] .v024-ready-badge{
        display:none !important;
      }

      body.v014 .v028-center-ready{
        position:absolute !important;
        left:50% !important;
        top:56.5% !important;
        z-index:72 !important;
        width:176px !important;
        transform:translate(-50%,-50%) !important;
        display:flex !important;
        flex-direction:column !important;
        align-items:center !important;
        gap:10px !important;
        pointer-events:none !important;
      }

      body.v014 .v028-center-ready[hidden]{
        display:none !important;
      }

      body.v014 .v028-center-status{
        display:inline-flex !important;
        align-items:center !important;
        justify-content:center !important;
        gap:7px !important;
        min-width:126px !important;
        height:31px !important;
        padding:0 16px !important;
        border:1px solid rgba(255,169,67,.48) !important;
        border-radius:999px !important;
        background:linear-gradient(180deg,rgba(56,30,5,.96),rgba(31,16,3,.98)) !important;
        box-shadow:0 7px 18px rgba(0,0,0,.28),inset 0 0 15px rgba(255,166,64,.035) !important;
        color:#ffd79d !important;
        font-size:12px !important;
        font-weight:950 !important;
        line-height:1 !important;
        letter-spacing:.055em !important;
        text-shadow:0 1px 3px rgba(0,0,0,.75) !important;
        white-space:nowrap !important;
      }

      body.v014 .v028-center-status i{
        width:8px !important;
        height:8px !important;
        flex:0 0 8px !important;
        border-radius:50% !important;
        background:#ff9f38 !important;
        box-shadow:0 0 10px rgba(255,153,48,.72) !important;
      }

      body.v014 .v028-center-status.ready{
        border-color:rgba(75,239,178,.56) !important;
        background:linear-gradient(180deg,rgba(7,53,37,.97),rgba(4,31,22,.99)) !important;
        color:#cffff0 !important;
      }

      body.v014 .v028-center-status.ready i{
        background:#56efad !important;
        box-shadow:0 0 11px rgba(76,239,176,.76) !important;
      }

      body.v014 .v028-center-ready-button{
        pointer-events:auto !important;
        width:154px !important;
        height:43px !important;
        border:1px solid rgba(66,226,171,.68) !important;
        border-radius:13px !important;
        background:linear-gradient(180deg,rgba(7,79,56,.98),rgba(4,48,35,.99)) !important;
        box-shadow:0 0 18px rgba(69,231,174,.14),0 8px 22px rgba(0,0,0,.30),inset 0 0 18px rgba(103,255,204,.055) !important;
        color:#dcfff1 !important;
        font-size:12px !important;
        font-weight:950 !important;
        letter-spacing:.055em !important;
        cursor:pointer !important;
        transition:transform .14s ease,border-color .16s ease,box-shadow .16s ease,background .16s ease !important;
      }

      body.v014 .v028-center-ready-button.start{
        border-color:rgba(70,203,255,.76) !important;
        background:linear-gradient(180deg,rgba(7,65,100,.98),rgba(3,36,66,.99)) !important;
        color:#e9fbff !important;
        box-shadow:0 0 19px rgba(64,202,255,.17),0 8px 22px rgba(0,0,0,.30),inset 0 0 18px rgba(101,215,255,.06) !important;
      }

      body.v014 .v028-center-ready-button:not(:disabled):active{
        transform:scale(.97) !important;
      }

      body.v014 .v028-center-ready-button:disabled{
        opacity:.42 !important;
        cursor:default !important;
      }

      /* Keep the existing header action as a compact secondary control. */
      body.v014 .mobile-primary-action.v024-ready-button{
        border-color:rgba(70,230,174,.62) !important;
        background:linear-gradient(180deg,rgba(7,65,47,.94),rgba(4,38,29,.97)) !important;
        color:#d7ffef !important;
        font-weight:950 !important;
        letter-spacing:.045em !important;
        box-shadow:0 0 15px rgba(70,225,170,.10),inset 0 0 15px rgba(104,255,205,.04) !important;
      }

      body.v014 .mobile-primary-action.v024-ready-button.v024-all-ready{
        border-color:rgba(73,205,255,.67) !important;
        background:linear-gradient(180deg,rgba(7,56,87,.96),rgba(4,31,56,.98)) !important;
        color:#e7faff !important;
      }
    }
  `;
  document.head.appendChild(style);

  syncCenterReadyUi();
})();
