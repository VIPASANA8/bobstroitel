(() => {
  "use strict";

  // The table's own instruction panel, shared by the felt and the lobby.
  // It lived in v037, which the lobby never loads -- and the lobby is where
  // somebody is most likely to want it, before they have sat down anywhere.

  const HAND_RANKINGS = [
    { name: "Роял-флеш", desc: "A, K, Q, J, 10 одной масти", cards: ["As", "Ks", "Qs", "Js", "Ts"] },
    { name: "Стрит-флеш", desc: "Пять карт подряд одной масти", cards: ["9h", "8h", "7h", "6h", "5h"] },
    { name: "Каре", desc: "Четыре карты одного достоинства", cards: ["9s", "9h", "9d", "9c"] },
    { name: "Фулл-хаус", desc: "Тройка и пара", cards: ["Ks", "Kh", "Kd", "4c", "4h"] },
    { name: "Флеш", desc: "Пять карт одной масти", cards: ["Ad", "Jd", "8d", "6d", "3d"] },
    { name: "Стрит", desc: "Пять карт подряд, масти любые", cards: ["8h", "7s", "6d", "5c", "4h"] },
    { name: "Сет", desc: "Три карты одного достоинства", cards: ["7c", "7h", "7d"] },
    { name: "Две пары", desc: "Две разные пары", cards: ["Qs", "Qh", "5d", "5c"] },
    { name: "Пара", desc: "Две карты одного достоинства", cards: ["Th", "Td"] },
    { name: "Старшая карта", desc: "Комбинации нет — решает старшая карта", cards: ["Ah"] },
  ];

  //: Everything the hint has to say, in the order a new player needs it:
  //: what beats what, how a hand runs, and what each control does.
  const TABLE_RULES = [
    ["Цель", "Собрать из своих двух карт и пяти общих лучшую комбинацию из пяти карт — или заставить остальных сбросить."],
    ["Блайнды", "Два места слева от дилера ставят малый и большой блайнд до раздачи. Кнопка дилера сдвигается на одного каждую раздачу."],
    ["Улицы", "Префлоп — по две карты в руки. Флоп — три общие карты, тёрн — четвёртая, ривер — пятая. Торговля идёт на каждой."],
    ["Вскрытие", "Если после ривера остались двое и больше, карты открываются и банк забирает старшая комбинация. Равные руки делят банк."],
  ];

  //: key doubles as the class that colours the term, so a button and its
  //: entry here cannot end up different colours.
  const ACTION_GUIDE = [
    ["FOLD", "Сбросить карты и выйти из раздачи. Всё, что уже поставлено, остаётся в банке."],
    ["CHECK", "Пропустить ход, ничего не ставя. Доступно, только когда ставки перед вами нет."],
    ["CALL", "Уравнять ставку соперника. На кнопке написано, сколько это стоит."],
    ["BET / RAISE", "Поставить первым или повысить чужую ставку. Размер выбирается ползунком над кнопками."],
    ["ALL-IN", "Поставить весь свой стек. Дальше вы не платите и не сбрасываете — ждёте вскрытия."],
  ];

  function miniCardHtml(code) {
    const rank = code[0] === "T" ? "10" : code[0];
    const suit = code[1];
    const symbol = { s: "♠", h: "♥", d: "♦", c: "♣" }[suit] || suit;
    const red = suit === "h" || suit === "d" ? " red" : "";
    return `<div class="hr-card${red}"><span>${rank}</span><b>${symbol}</b></div>`;
  }

  function ensureHandRankingsModal() {
    if (document.getElementById("handRankingsModal")) return;
    const modal = document.createElement("div");
    modal.id = "handRankingsModal";
    modal.className = "hand-rankings-modal";
    modal.hidden = true;
    const rows = HAND_RANKINGS.map((hand, i) => `
      <div class="hr-row">
        <div class="hr-rank">${i + 1}</div>
        <div class="hr-cards">${hand.cards.map(miniCardHtml).join("")}</div>
        <div class="hr-text"><strong>${hand.name}</strong><span>${hand.desc}</span></div>
      </div>
    `).join("");
    const defs = (list, colour = false) => list.map(([term, text]) => {
      const key = colour ? ` hr-act-${term.split(" ")[0].toLowerCase().replace("-", "")}` : "";
      return `<div class="hr-def${key}"><strong>${term}</strong><span>${text}</span></div>`;
    }).join("");
    modal.innerHTML = `
      <div class="hr-backdrop"></div>
      <div class="hr-panel" role="dialog" aria-modal="true" aria-label="Инструкция">
        <div class="hr-head"><strong>Инструкция</strong><button id="handRankingsClose" type="button" aria-label="Закрыть">×</button></div>
        <div class="hr-body">
          <h4 class="hr-section">Комбинации</h4>
          <div class="hr-list">${rows}</div>
          <h4 class="hr-section">Правила</h4>
          <div class="hr-defs">${defs(TABLE_RULES)}</div>
          <h4 class="hr-section">Кнопки</h4>
          <div class="hr-defs">${defs(ACTION_GUIDE, true)}</div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }


  function ensureStyle() {
    if (document.getElementById("p8-table-guide-style")) return;
    const style = document.createElement("style");
    style.id = "p8-table-guide-style";
    // --act-* live in style.css, which the lobby does not load, so each one
    // carries the same literal as its fallback.
    style.textContent = `
      .hand-rankings-modal{position:fixed;inset:0;z-index:120;}
      .hand-rankings-modal[hidden]{display:none;}
      .hand-rankings-modal .hr-backdrop{position:absolute;inset:0;background:rgba(7,16,15,.72);backdrop-filter:blur(2px);}
      .hand-rankings-modal .hr-panel{
        position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
        width:min(92vw,380px);max-height:82vh;overflow-y:auto;
        background:linear-gradient(180deg,#0a1512,#07100f);border:1px solid rgba(64,237,167,.28);
        border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.6),0 0 30px rgba(64,237,167,.1);
        padding:14px;
      }
      .hand-rankings-modal .hr-head{
        display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;
        color:#eafff6;font-size:15px;font-weight:900;letter-spacing:.02em;
      }
      .hand-rankings-modal .hr-head button{
        width:30px;height:30px;border-radius:8px;border:1px solid rgba(120,150,140,.3);
        background:rgba(255,255,255,.04);color:#c3d7cc;font-size:20px;line-height:1;cursor:pointer;
      }
      /* The card column is fixed at the widest hand rather than auto: each
         row is its own grid, so an auto column took the width of that row's
         own cards and a five-card hand pushed its text further right than a
         pair did. 72px is five 20px cards at the -7px overlap below, so
         every group centres on the same axis and every name starts on the
         same line. */
      .hand-rankings-modal .hr-row{
        display:grid;grid-template-columns:20px var(--hr-cards-w) 1fr;gap:10px;align-items:center;
        padding:8px 4px;border-top:1px solid rgba(120,150,140,.14);
      }
      .hand-rankings-modal .hr-row:first-child{border-top:0;}
      .hand-rankings-modal .hr-rank{color:#6f8b81;font-size:12px;font-weight:800;font-variant-numeric:tabular-nums;}
      .hand-rankings-modal .hr-cards{display:flex;justify-content:center;}
      /* 20px per card, less the 7px each one overlaps the last: 20 + 4*13. */
      .hand-rankings-modal{--hr-cards-w:72px;}
      .hand-rankings-modal .hr-card{
        display:grid;place-items:center;width:20px;height:28px;margin-left:-7px;
        border:1px solid rgba(255,255,255,.5);border-radius:4px;background:#ffffff;color:#1a1a1a;
        font-size:10px;font-weight:800;line-height:1;box-shadow:0 2px 4px rgba(0,0,0,.4);
      }
      .hand-rankings-modal .hr-card:first-child{margin-left:0;}
      .hand-rankings-modal .hr-card.red{color:#d0271c;}
      .hand-rankings-modal .hr-card b{font-size:10px;}
      .hand-rankings-modal .hr-text{display:flex;flex-direction:column;gap:1px;min-width:0;}
      .hand-rankings-modal .hr-section{
        margin:18px 0 2px;color:#6f8b81;font-size:10px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;
      }
      .hand-rankings-modal .hr-section:first-child{margin-top:2px;}
      .hand-rankings-modal .hr-defs{display:flex;flex-direction:column;}
      .hand-rankings-modal .hr-def{
        display:grid;grid-template-columns:var(--hr-cards-w) 1fr;gap:10px;align-items:baseline;
        padding:8px 4px;border-top:1px solid rgba(120,150,140,.14);
      }
      .hand-rankings-modal .hr-def strong{color:#eafff6;font-size:12px;}
      /* Each action wears its own button's colour. --act-* live in style.css,
         which the lobby does not load, so each carries the same literal. */
      .hand-rankings-modal .hr-act-fold strong{color:var(--act-fold,#ff4d42);}
      .hand-rankings-modal .hr-act-check strong,
      .hand-rankings-modal .hr-act-call strong{color:var(--act-check,#49caff);}
      .hand-rankings-modal .hr-act-bet strong{color:var(--act-raise,#55f16e);}
      .hand-rankings-modal .hr-act-allin strong{color:var(--act-allin,#ffc44d);}
      .hand-rankings-modal .hr-def span{color:#8ca59c;font-size:10px;line-height:1.35;}
      .hand-rankings-modal .hr-text strong{color:#eafff6;font-size:12px;}
      .hand-rankings-modal .hr-text span{color:#8ca59c;font-size:10px;line-height:1.25;}
    `;
    document.head.appendChild(style);
  }

  function ensure() {
    ensureStyle();
    ensureHandRankingsModal();
    return document.getElementById("handRankingsModal");
  }

  window.Poker8TableGuide = {
    ensure,
    toggle() {
      const modal = ensure();
      if (modal) modal.hidden = !modal.hidden;
    },
    close() {
      const modal = document.getElementById("handRankingsModal");
      if (modal) modal.hidden = true;
    },
  };
})();
