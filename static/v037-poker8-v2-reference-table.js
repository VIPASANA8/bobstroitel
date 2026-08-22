(() => {
  "use strict";

  // The class is the switch now: it is added at every width, so the media
  // half of this test only kept desktop out of everything below.
  const isMobileV2 = () => document.body.classList.contains("poker8-v2-sixmax");

  // Highest to lowest -- the same order shown on the felt's own showdown
  // comparison, so a player checking this mid-hand and then seeing the
  // result modal reads the same list twice, not two different ones.
  const HAND_RANKINGS = [
    { name: "Роял-флеш", desc: "A, K, Q, J, 10 одной масти", cards: ["As", "Ks", "Qs", "Js", "Ts"] },
    { name: "Стрит-флеш", desc: "Пять карт подряд одной масти", cards: ["9h", "8h", "7h", "6h", "5h"] },
    { name: "Каре", desc: "Четыре карты одного достоинства", cards: ["9s", "9h", "9d", "9c", "2c"] },
    { name: "Фулл-хаус", desc: "Тройка и пара", cards: ["Ks", "Kh", "Kd", "4c", "4h"] },
    { name: "Флеш", desc: "Пять карт одной масти", cards: ["Ad", "Jd", "8d", "6d", "3d"] },
    { name: "Стрит", desc: "Пять карт подряд, масти любые", cards: ["8h", "7s", "6d", "5c", "4h"] },
    { name: "Сет", desc: "Три карты одного достоинства", cards: ["7c", "7h", "7d", "Ks", "2c"] },
    { name: "Две пары", desc: "Две разные пары", cards: ["Qs", "Qh", "5d", "5c", "9h"] },
    { name: "Пара", desc: "Две карты одного достоинства", cards: ["Th", "Td", "8s", "5h", "2c"] },
    { name: "Старшая карта", desc: "Комбинации нет — решает старшая карта", cards: ["Ah", "Jd", "8s", "5h", "2c"] },
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
    modal.innerHTML = `
      <div class="hr-backdrop"></div>
      <div class="hr-panel" role="dialog" aria-modal="true" aria-label="Комбинации покера">
        <div class="hr-head"><strong>Комбинации рук</strong><button id="handRankingsClose" type="button" aria-label="Закрыть">×</button></div>
        <div class="hr-list">${rows}</div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // Purely decorative, like the chat button beside it -- online-table.js
  // owns the click (and Escape) handling, delegated off document since it
  // runs before this file creates either element.
  function ensureHintButton() {
    const utility = document.getElementById("mobileHeaderUtility");
    if (!utility || document.getElementById("mobileHintButton")) return;
    ensureHandRankingsModal();
    const hint = document.createElement("button");
    hint.id = "mobileHintButton";
    hint.className = "mobile-hint-button";
    hint.type = "button";
    hint.setAttribute("aria-label", "Комбинации покера");
    hint.textContent = "?";
    utility.appendChild(hint);
  }

  function ensureChatButton() {
    const header = document.getElementById("mobileGameHeader");
    if (!header) return;
    // Chat and the rankings hint sit as one group so header's own
    // space-between spreads [menu] / [this group] / [seat actions] apart
    // instead of spacing every button out individually.
    let utility = document.getElementById("mobileHeaderUtility");
    if (!utility) {
      utility = document.createElement("div");
      utility.id = "mobileHeaderUtility";
      utility.className = "mobile-header-utility";
      header.appendChild(utility);
    }
    if (!document.getElementById("mobileChatButton")) {
      const chat = document.createElement("button");
      chat.id = "mobileChatButton";
      chat.className = "mobile-chat-button";
      chat.type = "button";
      chat.setAttribute("aria-label", "Чат");
      chat.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path class="chat-bubble" d="M4.5 5.5h15v10h-9l-4.5 3v-3H4.5z"/><circle cx="9" cy="10.5" r="1"/><circle cx="12" cy="10.5" r="1"/><circle cx="15" cy="10.5" r="1"/></svg>';
      utility.appendChild(chat);
    }
    ensureHintButton();
  }

  const style = document.createElement("style");
  style.id = "v037-poker8-v2-reference-table-style";
  style.textContent = `
    /* Was @media (max-width:780px). The v2 table is the table now, at every
       width; desktop geometry is tuned in v039. */
    @media all{
      body.v014.poker8-v2-sixmax .mobile-game-header{
        justify-content:space-between!important;
        padding:12px 13px 4px!important;
      }
      body.v014.poker8-v2-sixmax .mobile-street-pill,
      body.v014.poker8-v2-sixmax .mobile-primary-action{display:none!important;}
      body.v014.poker8-v2-sixmax .mobile-header-utility{display:flex;gap:8px;align-items:center;}
      body.v014.poker8-v2-sixmax .mobile-chat-button,
      body.v014.poker8-v2-sixmax .mobile-hint-button{
        display:grid;place-items:center;width:42px;height:42px;padding:0;
        border:1px solid rgba(66,226,255,.72);border-radius:12px;
        background:rgba(3,16,20,.78);box-shadow:0 0 14px rgba(52,214,255,.18),inset 0 0 12px rgba(78,234,255,.08);
        color:#89efff;
      }
      body.v014.poker8-v2-sixmax .mobile-chat-button svg{
        width:21px;height:21px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;
        filter:drop-shadow(0 0 3px rgba(100,236,255,.85));
      }
      body.v014.poker8-v2-sixmax .mobile-chat-button .chat-bubble{fill:rgba(91,229,255,.20);}
      body.v014.poker8-v2-sixmax .mobile-chat-button circle{fill:currentColor;stroke:none;}
      body.v014.poker8-v2-sixmax .mobile-hint-button{font:800 20px/1 Inter,ui-sans-serif,system-ui;font-style:italic;}

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
      .hand-rankings-modal .hr-row{
        display:grid;grid-template-columns:20px auto 1fr;gap:10px;align-items:center;
        padding:8px 4px;border-top:1px solid rgba(120,150,140,.14);
      }
      .hand-rankings-modal .hr-row:first-child{border-top:0;}
      .hand-rankings-modal .hr-rank{color:#6f8b81;font-size:12px;font-weight:800;font-variant-numeric:tabular-nums;}
      .hand-rankings-modal .hr-cards{display:flex;}
      .hand-rankings-modal .hr-card{
        display:grid;place-items:center;width:20px;height:28px;margin-left:-7px;
        border:1px solid rgba(255,255,255,.5);border-radius:4px;background:#ffffff;color:#1a1a1a;
        font-size:10px;font-weight:800;line-height:1;box-shadow:0 2px 4px rgba(0,0,0,.4);
      }
      .hand-rankings-modal .hr-card:first-child{margin-left:0;}
      .hand-rankings-modal .hr-card.red{color:#d0271c;}
      .hand-rankings-modal .hr-card b{font-size:10px;}
      .hand-rankings-modal .hr-text{display:flex;flex-direction:column;gap:1px;min-width:0;}
      .hand-rankings-modal .hr-text strong{color:#eafff6;font-size:12px;}
      .hand-rankings-modal .hr-text span{color:#8ca59c;font-size:10px;line-height:1.25;}
      body.v014.poker8-v2-sixmax .table-frame{
        background:radial-gradient(ellipse at 50% 10%,rgba(96,57,22,.28),transparent 48%),linear-gradient(180deg,#0c0503,#000000 82%,#000000)!important;
      }
      body.v014.poker8-v2-sixmax .felt{
        border-width:13px!important;border-radius:49% / 35%!important;
        background:
          radial-gradient(ellipse at 50% 46%,rgba(0,74,43,.05),rgba(6,22,17,.38) 70%) padding-box,
          linear-gradient(145deg,#075234,#003b24 56%,#002316) padding-box,
          linear-gradient(90deg,#231005,#794016 18%,#301405 34%,#8d4c1c 50%,#301405 66%,#6f3c16 82%,#231005) border-box!important;
        outline:1px solid rgba(29,255,192,.56)!important;
        box-shadow:inset 0 0 72px rgba(0,0,0,.45),inset 0 0 0 2px rgba(29,255,192,.1),0 0 0 2px rgba(0,0,0,.95),0 0 22px rgba(40,255,183,.16)!important;
      }
      body.v014.poker8-v2-sixmax .felt::before{
        inset:7px!important;border-color:rgba(29,255,192,.58)!important;
        box-shadow:0 0 9px rgba(44,255,198,.22),inset 0 0 8px rgba(44,255,198,.08)!important;
      }
      body.v014.poker8-v2-sixmax .seat-card{
        background:linear-gradient(180deg,rgba(0,8,5,.97),rgba(0,0,0,.99))!important;
        border-color:hsla(var(--avatar-hue),88%,62%,.56)!important;
        box-shadow:0 0 13px hsla(var(--avatar-hue),88%,58%,.18),0 9px 22px rgba(0,0,0,.48)!important;
      }
      body.v014.poker8-v2-sixmax .seat-stack{color:hsl(var(--avatar-hue),92%,68%)!important;}
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-card{
        border-color:rgba(53,191,255,.9)!important;
        box-shadow:0 0 18px rgba(47,179,255,.28),0 10px 24px rgba(0,0,0,.52)!important;
      }
      body.v014.poker8-v2-sixmax .seat[data-visual-seat="0"] .seat-stack{color:#35c6ff!important;}
      body.v014.poker8-v2-sixmax .pot-total{
        background:rgba(4,31,20,.86)!important;border-color:rgba(64,237,167,.26)!important;
      }
    }
  `;
  document.head.appendChild(style);

  const start = () => {
    if (isMobileV2()) ensureChatButton();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
  window.addEventListener("resize", start);

  function ensureTurnClarityPatch() {
    if (document.querySelector("script[data-v041-poker8-v2-turn-clarity]")) return;
    const v041 = document.createElement("script");
    v041.src = "/static/v041-poker8-v2-turn-clarity.js?v=desktop-parity-1";
    v041.setAttribute("data-v041-poker8-v2-turn-clarity", "");
    document.body.appendChild(v041);
  }

  function ensureDynamicSeatLayout() {
    if (document.querySelector("script[data-v040-poker8-v2-dynamic-seats]")) {
      ensureTurnClarityPatch();
      return;
    }
    const v040 = document.createElement("script");
    v040.src = "/static/v040-poker8-v2-dynamic-seats.js?v=empty-seats-1";
    v040.setAttribute("data-v040-poker8-v2-dynamic-seats", "");
    v040.addEventListener("load", ensureTurnClarityPatch, { once:true });
    document.body.appendChild(v040);
  }

  if (!document.querySelector('script[data-v038-poker8-v2-cinematic-table]')) {
    const v038 = document.createElement("script");
    v038.src = "/static/v038-poker8-v2-cinematic-table.js?v=hand-combo-1";
    v038.setAttribute("data-v038-poker8-v2-cinematic-table", "");
    v038.addEventListener("load", ensureDynamicSeatLayout, { once: true });
    document.body.appendChild(v038);
  } else {
    ensureDynamicSeatLayout();
  }
})();
