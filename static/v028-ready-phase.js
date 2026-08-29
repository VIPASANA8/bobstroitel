/* The ready phase, in one file.

   Three layers used to do this, appended one after another with nothing
   between them: v028 (the control and the state), v029 (its look on a
   phone), v030 (the other seats' badges, the side-seat columns, and the
   script tag that loads v031). Merged 2026-08-29; see docs/layer-cleanup.md.

   They are still three IIFEs, in the order they used to load, and each still
   appends its own <style>. That is deliberate: the cascade among them is
   decided by that order, and folding them into one block by hand is how a
   merge like this changes what it claims not to. Nothing here is rewritten
   -- only the three round trips became one.

   Two contracts inside are relied on from outside, so mind them if this is
   ever pulled apart again:

     * the body class "v028-prehand-center-ready" -- v038 styles the hero's
       avatar and everybody's ready check off it;
     * the <script> for v031 at the very bottom, which is the only thing
       that loads the wager geometry every chip flies by.
*/

/* ---- v028-center-ready.js: The centre ready control, and the body class the rest of the stack reads ---- */

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

  onRendered("seats", syncCenterReadyUi);
  onRendered("mobileHeader", syncCenterReadyUi);

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
        border:1px solid rgba(255,171,67,.48) !important;
        border-radius:999px !important;
        background:linear-gradient(180deg,rgba(56,30,5,.96),rgba(31,16,3,.98)) !important;
        box-shadow:0 7px 18px rgba(0,0,0,.28),inset 0 0 15px rgba(255,163,65,.035) !important;
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
        background:#ff9e31 !important;
        box-shadow:0 0 10px rgba(255,153,48,.72) !important;
      }

      body.v014 .v028-center-status.ready{
        border-color:rgba(61,239,176,.56) !important;
        background:linear-gradient(180deg,rgba(7,53,37,.97),rgba(4,31,20,.99)) !important;
        color:#cffff0 !important;
      }

      body.v014 .v028-center-status.ready i{
        background:#5fedaa !important;
        box-shadow:0 0 11px rgba(61,239,176,.76) !important;
      }

      body.v014 .v028-center-ready-button{
        pointer-events:auto !important;
        width:154px !important;
        height:43px !important;
        border:1px solid rgba(66,226,171,.68) !important;
        border-radius:13px !important;
        background:linear-gradient(180deg,rgba(7,79,56,.98),rgba(4,48,35,.99)) !important;
        box-shadow:0 0 18px rgba(66,226,171,.14),0 8px 22px rgba(0,0,0,.30),inset 0 0 18px rgba(103,255,204,.055) !important;
        color:#d7ffef !important;
        font-size:12px !important;
        font-weight:950 !important;
        letter-spacing:.055em !important;
        cursor:pointer !important;
        transition:transform .14s ease,border-color .16s ease,box-shadow .16s ease,background .16s ease !important;
      }

      body.v014 .v028-center-ready-button.start{
        border-color:rgba(47,203,255,.76) !important;
        background:linear-gradient(180deg,rgba(7,65,100,.98),rgba(3,36,66,.99)) !important;
        color:#e7faff !important;
        box-shadow:0 0 19px rgba(47,203,255,.17),0 8px 22px rgba(0,0,0,.30),inset 0 0 18px rgba(96,216,255,.06) !important;
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
        border-color:rgba(66,226,171,.62) !important;
        background:linear-gradient(180deg,rgba(7,65,47,.94),rgba(4,38,29,.97)) !important;
        color:#d7ffef !important;
        font-weight:950 !important;
        letter-spacing:.045em !important;
        box-shadow:0 0 15px rgba(66,226,171,.10),inset 0 0 15px rgba(103,255,204,.04) !important;
      }

      body.v014 .mobile-primary-action.v024-ready-button.v024-all-ready{
        border-color:rgba(85,207,255,.67) !important;
        background:linear-gradient(180deg,rgba(7,56,87,.96),rgba(4,31,56,.98)) !important;
        color:#e7faff !important;
      }
    }
  `;
  document.head.appendChild(style);

  syncCenterReadyUi();
})();

/* ---- v029-ready-style.js: How that control looks on a phone ---- */

(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v029-ready-style";
  style.textContent = `
    @media (max-width:780px){
      /* Cleaner status: indicator, not a second button. */
      body.v014 .v028-center-ready{
        width:190px !important;
        gap:12px !important;
      }

      body.v014 .v028-center-status{
        position:relative !important;
        min-width:0 !important;
        width:auto !important;
        height:25px !important;
        padding:0 6px 0 20px !important;
        border:0 !important;
        border-radius:0 !important;
        background:transparent !important;
        box-shadow:none !important;
        color:#ffbd65 !important;
        font-size:10px !important;
        font-weight:950 !important;
        letter-spacing:.08em !important;
        text-shadow:0 0 10px rgba(255,163,65,.18) !important;
      }

      body.v014 .v028-center-status::after{
        content:"";
        position:absolute;
        left:20px;
        right:6px;
        bottom:0;
        height:1px;
        background:linear-gradient(90deg,rgba(255,163,65,.75),rgba(255,163,65,0));
        opacity:.75;
      }

      body.v014 .v028-center-status i{
        position:absolute !important;
        left:4px !important;
        top:50% !important;
        width:7px !important;
        height:7px !important;
        transform:translateY(-50%) !important;
        background:#ffab43 !important;
        box-shadow:0 0 11px rgba(255,171,67,.72) !important;
      }

      body.v014 .v028-center-status.ready{
        background:transparent !important;
        border:0 !important;
        color:#78ffc8 !important;
        box-shadow:none !important;
        text-shadow:0 0 10px rgba(81,239,174,.18) !important;
      }

      body.v014 .v028-center-status.ready::after{
        background:linear-gradient(90deg,rgba(71,230,168,.72),rgba(71,230,168,0));
      }

      body.v014 .v028-center-status.ready i{
        background:#5fedaa !important;
        box-shadow:0 0 11px rgba(95,237,170,.72) !important;
      }

      /* Main control: dark glass with a bright edge, more Poker8-like. */
      body.v014 .v028-center-ready-button{
        position:relative !important;
        width:172px !important;
        height:46px !important;
        overflow:hidden !important;
        border:1px solid rgba(47,207,255,.50) !important;
        border-radius:14px !important;
        background:linear-gradient(180deg,rgba(12,20,39,.96),rgba(8,13,26,.99)) !important;
        color:#eef4f8 !important;
        font-size:12px !important;
        font-weight:950 !important;
        letter-spacing:.075em !important;
        text-shadow:0 1px 3px rgba(0,0,0,.8) !important;
        box-shadow:0 9px 24px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.055),inset 0 0 20px rgba(42,154,255,.045) !important;
      }

      body.v014 .v028-center-ready-button::before{
        content:"";
        position:absolute;
        left:13px;
        right:13px;
        bottom:0;
        height:2px;
        border-radius:99px 99px 0 0;
        background:linear-gradient(90deg,#2fcfff,#8b62ff);
        box-shadow:0 0 10px rgba(75,191,255,.48);
      }

      body.v014 .v028-center-ready-button::after{
        content:"→";
        position:absolute;
        right:15px;
        top:50%;
        transform:translateY(-52%);
        color:#7bdcff;
        font-size:15px;
        font-weight:800;
        opacity:.9;
      }

      body.v014 .v028-center-ready-button.start{
        border-color:rgba(72,239,180,.55) !important;
        background:linear-gradient(180deg,rgba(7,39,35,.97),rgba(2,19,18,.99)) !important;
        color:#eafff6 !important;
        box-shadow:0 9px 24px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.055),inset 0 0 20px rgba(55,220,162,.045) !important;
      }

      body.v014 .v028-center-ready-button.start::before{
        background:linear-gradient(90deg,#3defb0,#34d6ff);
        box-shadow:0 0 10px rgba(61,235,190,.45);
      }

      body.v014 .v028-center-ready-button.start::after{
        content:"▶";
        color:#7ff0bf;
        font-size:12px;
      }

      body.v014 .v028-center-ready-button:not(:disabled):hover{
        border-color:rgba(85,219,255,.78) !important;
        box-shadow:0 0 17px rgba(53,191,255,.12),0 9px 24px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.065) !important;
      }

      body.v014 .v028-center-ready-button:not(:disabled):active{
        transform:translateY(1px) scale(.985) !important;
      }
    }
  `;
  document.head.appendChild(style);
})();

/* ---- v030-seat-ready-fix.js: Everyone else's ready badge, the two side seats, and v031's loader ---- */

(() => {
  "use strict";

  const style = document.createElement("style");
  style.id = "v030-seat-ready-fix-style";
  style.textContent = `
    @media (max-width:780px){
      /* Pull the two side seats away from the viewport edges. */
      body.v014{
        --seat-2-x:13% !important;
        --seat-5-x:87% !important;
      }
    }
  `;
  document.head.appendChild(style);

  function tableIsReady() {
    const centerStatus = document.querySelector(".v028-center-status");
    if (centerStatus?.classList.contains("ready")) return true;

    const primary = document.getElementById("mobilePrimaryAction");
    const text = String(primary?.textContent || "").trim().toUpperCase();
    return /НАЧАТЬ/.test(text);
  }

  function syncAllReadyBadges() {
    if (game && !game.terminal) return;

    const ready = tableIsReady();
    document.querySelectorAll(".seat-card > .v024-ready-badge").forEach(badge => {
      badge.classList.toggle("ready", ready);
      badge.classList.toggle("waiting", !ready);

      const text = badge.querySelector("span");
      const wanted = ready ? "ГОТОВ" : "НЕ ГОТОВ";
      if (text && text.textContent !== wanted) text.textContent = wanted;
      badge.setAttribute("aria-label", ready ? "Игрок готов" : "Игрок не готов");

      const card = badge.closest(".seat-card");
      card?.classList.toggle("v024-seat-ready", ready);
      card?.classList.toggle("v024-seat-not-ready", !ready);
    });
  }

  let syncQueued = false;
  function queueReadySync() {
    if (syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(() => {
      syncQueued = false;
      syncAllReadyBadges();
    });
  }

  const observer = new MutationObserver(queueReadySync);
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["class"]
  });

  document.addEventListener("click", event => {
    if (!event.target?.closest?.(".v028-center-ready-button, #mobilePrimaryAction, #newHand")) return;
    setTimeout(syncAllReadyBadges, 0);
    setTimeout(syncAllReadyBadges, 40);
  }, true);

  if (!document.querySelector('script[data-v031-pot-cluster-mobile-fix]')) {
    const v031 = document.createElement("script");
    v031.src = "/static/v031-pot-cluster-mobile-fix.js?v=pot-wings-1";
    v031.dataset.v031PotClusterMobileFix = "1";
    document.body.appendChild(v031);
  }

  queueReadySync();
})();

