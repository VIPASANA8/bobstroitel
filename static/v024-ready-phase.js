(() => {
  "use strict";

  const READY_KEY = "poker8:v024:viewer-ready";
  const TABLE_KEY = "poker8:v024:ready-table";

  let viewerReady = sessionStorage.getItem(READY_KEY) === "1";

  function preHand() {
    return !game || Boolean(game.terminal);
  }

  function activeSeats() {
    return Array.isArray(tableData?.seats) ? tableData.seats.filter(seat => seat?.active) : [];
  }

  function activeHumanSeats() {
    return activeSeats().filter(seat => seat?.occupant_type === "human");
  }

  function tableSignature() {
    return activeSeats()
      .map(seat => `${seat.seat}:${seat.occupant_type}:${seat.profile_id || seat.id || ""}`)
      .sort()
      .join("|");
  }

  function syncReadyTable() {
    const signature = tableSignature();
    if (!signature) return;
    const previous = sessionStorage.getItem(TABLE_KEY) || "";
    if (previous && previous !== signature) {
      viewerReady = false;
      sessionStorage.setItem(READY_KEY, "0");
    }
    sessionStorage.setItem(TABLE_KEY, signature);
  }

  function setViewerReady(value) {
    viewerReady = Boolean(value);
    sessionStorage.setItem(READY_KEY, viewerReady ? "1" : "0");
  }

  function enoughPlayers() {
    return activeSeats().length >= 2;
  }

  function allReady() {
    if (!enoughPlayers()) return false;
    if (!activeHumanSeats().length) return true;
    return viewerReady;
  }

  function clearReadyBadges() {
    document.querySelectorAll(".v024-ready-badge").forEach(node => node.remove());
    document.querySelectorAll(".seat-card.v024-seat-ready, .seat-card.v024-seat-not-ready").forEach(card => {
      card.classList.remove("v024-seat-ready", "v024-seat-not-ready");
    });
  }

  function renderSeatReadiness() {
    clearReadyBadges();
    if (!preHand()) return;

    syncReadyTable();

    for (const config of activeSeats()) {
      const seat = document.querySelector(`.seat[data-seat="${config.seat}"]`);
      const card = seat?.querySelector(".seat-card");
      if (!card) continue;

      const isViewerHuman = seat.dataset.visualSeat === "0" && config.occupant_type === "human";
      const ready = isViewerHuman ? viewerReady : true;

      card.classList.toggle("v024-seat-ready", ready);
      card.classList.toggle("v024-seat-not-ready", !ready);

      const badge = document.createElement("div");
      badge.className = `v024-ready-badge ${ready ? "ready" : "waiting"}`;
      badge.innerHTML = `<i></i><span>${ready ? "ГОТОВ" : "НЕ ГОТОВ"}</span>`;
      badge.setAttribute("aria-label", ready ? "Игрок готов" : "Игрок не готов");
      card.appendChild(badge);
    }
  }

  function mobileReadyText() {
    if (!enoughPlayers()) return "НУЖНО 2";
    if (!activeHumanSeats().length) return "НАЧАТЬ";
    return viewerReady && allReady() ? "НАЧАТЬ" : "ГОТОВ";
  }

  function desktopReadyText() {
    if (!enoughPlayers()) return "Нужно 2 игрока";
    if (!activeHumanSeats().length) return "Начать раздачу";
    return viewerReady && allReady() ? "Начать раздачу" : "Готов";
  }

  function renderReadyControls() {
    syncReadyTable();

    const mobile = $("mobilePrimaryAction");
    const desktop = $("newHand");
    const drawer = $("mobileDrawerNewHand");

    if (!preHand()) {
      mobile?.classList.remove("v024-ready-button", "v024-all-ready");
      desktop?.classList.remove("v024-ready-button", "v024-all-ready");
      return;
    }

    const disabled = !enoughPlayers();
    const isAllReady = allReady();

    if (mobile) {
      mobile.textContent = mobileReadyText();
      mobile.disabled = disabled;
      mobile.classList.add("v024-ready-button");
      mobile.classList.toggle("v024-all-ready", isAllReady);
    }

    if (desktop) {
      desktop.textContent = desktopReadyText();
      desktop.disabled = disabled;
      desktop.classList.add("v024-ready-button");
      desktop.classList.toggle("v024-all-ready", isAllReady);
    }

    if (drawer) {
      drawer.textContent = desktopReadyText();
      drawer.disabled = disabled;
    }
  }

  function renderReadyUi() {
    renderSeatReadiness();
    renderReadyControls();
  }

  const startNewHand = newHand;
  newHand = async function newHandWithReadyPhase(fromAutomation = false) {
    if (!preHand()) return startNewHand(fromAutomation);

    syncReadyTable();
    if (!enoughPlayers()) {
      renderReadyUi();
      return;
    }

    // Bot-only tables do not need a local confirmation step.
    if (!activeHumanSeats().length) {
      const result = await startNewHand(fromAutomation);
      setViewerReady(false);
      return result;
    }

    // First press is READY. Second press starts after the table shows everyone ready.
    if (!viewerReady) {
      setViewerReady(true);
      renderReadyUi();
      return;
    }

    if (!allReady()) {
      renderReadyUi();
      return;
    }

    const result = await startNewHand(fromAutomation);
    if (game && !game.terminal) {
      setViewerReady(false);
      clearReadyBadges();
    }
    return result;
  };

  const originalRenderSeats = renderSeats;
  renderSeats = function renderSeatsWithReadyState() {
    originalRenderSeats();
    renderSeatReadiness();
  };

  const originalRenderMobileHeader = renderMobileHeader;
  renderMobileHeader = function renderMobileHeaderWithReadyState() {
    originalRenderMobileHeader();
    renderReadyControls();
  };

  const style = document.createElement("style");
  style.id = "v024-ready-phase-style";
  style.textContent = `
    body.v014 .seat-card .v024-ready-badge{
      position:absolute;
      left:50%;
      bottom:6px;
      z-index:9;
      transform:translateX(-50%);
      display:inline-flex;
      align-items:center;
      justify-content:center;
      gap:4px;
      min-width:43px;
      height:16px;
      padding:0 6px;
      box-sizing:border-box;
      border-radius:999px;
      font-size:7px;
      font-weight:950;
      line-height:1;
      letter-spacing:.035em;
      white-space:nowrap;
      pointer-events:none;
      backdrop-filter:blur(5px);
    }

    body.v014 .seat-card .v024-ready-badge i{
      width:5px;
      height:5px;
      flex:0 0 5px;
      border-radius:50%;
    }

    body.v014 .seat-card .v024-ready-badge.ready{
      color:#aaffdc;
      border:1px solid rgba(81,234,174,.38);
      background:rgba(5,39,31,.82);
      box-shadow:0 0 10px rgba(64,231,171,.10);
    }
    body.v014 .seat-card .v024-ready-badge.ready i{
      background:#66f0b4;
      box-shadow:0 0 7px rgba(70,240,180,.72);
    }

    body.v014 .seat-card .v024-ready-badge.waiting{
      color:#ffd1a2;
      border:1px solid rgba(255,174,91,.34);
      background:rgba(45,24,8,.82);
    }
    body.v014 .seat-card .v024-ready-badge.waiting i{
      background:#ffad5b;
      box-shadow:0 0 7px rgba(255,154,72,.62);
    }

    body.v014 .mobile-primary-action.v024-ready-button,
    body.v014 #newHand.v024-ready-button{
      border-color:rgba(72,222,161,.58) !important;
      background:linear-gradient(180deg,rgba(8,65,50,.96),rgba(5,42,34,.98)) !important;
      color:#b9ffe2 !important;
      box-shadow:inset 0 0 16px rgba(74,235,176,.06) !important;
    }

    body.v014 .mobile-primary-action.v024-ready-button.v024-all-ready,
    body.v014 #newHand.v024-ready-button.v024-all-ready{
      border-color:rgba(89,246,184,.82) !important;
      background:linear-gradient(180deg,rgba(10,91,67,.98),rgba(5,54,42,.99)) !important;
      box-shadow:0 0 16px rgba(65,233,170,.16), inset 0 0 18px rgba(91,255,194,.08) !important;
    }

    @media (max-width:780px){
      body.v014 .mobile-primary-action.v024-ready-button{
        font-size:9px !important;
        letter-spacing:.01em !important;
        padding-left:9px !important;
        padding-right:9px !important;
      }

      body.v014 .seat[data-visual-seat="0"] .seat-card .v024-ready-badge{
        bottom:5px;
      }
    }
  `;
  document.head.appendChild(style);

  // Existing handlers call the global `newHand`, so replacing it above is enough
  // to insert the readiness step without duplicating button listeners.
  renderReadyUi();
})();
