(() => {
  "use strict";

  function applyPoker8Brand() {
    document.title = "Poker8";

    const mark = document.querySelector(".brand-mark");
    if (mark) mark.textContent = "P8";

    const title = document.querySelector(".brand-wrap h1");
    if (title) title.textContent = "[P8] Poker8";
  }

  let marking = false;
  function markPrimaryHumanSeat() {
    if (marking) return;
    marking = true;

    requestAnimationFrame(() => {
      try {
        const seat = document.querySelector('.seat[data-visual-seat="0"]');
        const card = seat?.querySelector('.seat-card.seat-human');
        if (!card) return;

        // v0.22 originally made only `.viewer-seat .seat-stack` clickable.
        // Between hands `seatHtml()` has no game viewer id and therefore did
        // not add viewer-seat. Keep the primary visual human marked explicitly
        // so the balance remains clickable both during and between hands.
        if (!card.classList.contains("viewer-seat")) {
          card.classList.add("viewer-seat");
          card.dataset.v023Viewer = "1";
        }

        const stack = card.querySelector(".seat-stack");
        if (stack) {
          stack.setAttribute("role", "button");
          stack.setAttribute("tabindex", "0");
          stack.setAttribute("aria-label", "Пополнить баланс");
          stack.title = "Пополнить баланс";
        }
      } finally {
        marking = false;
      }
    });
  }

  document.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const stack = event.target?.closest?.('.seat[data-visual-seat="0"] .seat-card.seat-human .seat-stack');
    if (!stack) return;
    event.preventDefault();
    stack.click();
  });

  const style = document.createElement("style");
  style.id = "v023-brand-balance-fix-style";
  style.textContent = `
    body.v014 .seat[data-visual-seat="0"],
    body.v014 .seat[data-visual-seat="0"] .seat-card.seat-human,
    body.v014 .seat[data-visual-seat="0"] .seat-card.seat-human .seat-stack{
      pointer-events:auto !important;
    }

    body.v014 .seat[data-visual-seat="0"] .seat-card.seat-human .seat-stack{
      cursor:pointer !important;
      touch-action:manipulation !important;
      -webkit-tap-highlight-color:transparent !important;
    }
  `;
  document.head.appendChild(style);

  applyPoker8Brand();
  markPrimaryHumanSeat();

  const felt = document.querySelector(".felt") || document.body;
  const observer = new MutationObserver(() => markPrimaryHumanSeat());
  observer.observe(felt, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-visual-seat"] });
})();
