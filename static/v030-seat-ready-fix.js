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
    v031.src = "/static/v031-pot-cluster-mobile-fix.js?v=chip-layers-1";
    v031.dataset.v031PotClusterMobileFix = "1";
    document.body.appendChild(v031);
  }

  queueReadySync();
})();
