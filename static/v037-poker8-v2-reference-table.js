(() => {
  "use strict";

  // The class is the switch now: it is added at every width, so the media
  // half of this test only kept desktop out of everything below.
  const isMobileV2 = () => document.body.classList.contains("poker8-v2-sixmax");

  // Highest to lowest -- the same order shown on the felt's own showdown
  // comparison, so a player checking this mid-hand and then seeing the
  // result modal reads the same list twice, not two different ones.
  //
  // Only the cards that actually define each category -- same rule as the
  // live highlight on the felt (see app.js's coreComboCards): a pair shows
  // two cards, not a pair plus three kickers. Straight/flush/full-house/
  // straight-flush have no separate kicker, so those keep all five.
  // The panel itself lives in table-guide.js: the lobby shows the same one
  // and never loads this file.

  // Purely decorative, like the chat button beside it -- online-table.js
  // owns the click (and Escape) handling, delegated off document since it
  // runs before this file creates either element.
  function ensureHintButton() {
    const utility = document.getElementById("mobileHeaderUtility");
    if (!utility || document.getElementById("mobileHintButton")) return;
    window.Poker8TableGuide?.ensure();
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
        display:grid;place-items:center;width:42px;height:42px;padding:0;overflow:hidden;
        border:1px solid rgba(66,226,255,.72);border-radius:12px;
        background:rgba(3,16,20,.78);box-shadow:0 0 14px rgba(52,214,255,.18),inset 0 0 12px rgba(78,234,255,.08);
        color:#89efff;
      }
      body.v014.poker8-v2-sixmax .mobile-chat-button svg{
        width:21px;height:21px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;
      }
      body.v014.poker8-v2-sixmax .mobile-chat-button .chat-bubble{fill:rgba(91,229,255,.20);}
      body.v014.poker8-v2-sixmax .mobile-chat-button circle{fill:currentColor;stroke:none;}
      body.v014.poker8-v2-sixmax .mobile-hint-button{font:800 20px/1 Inter,ui-sans-serif,system-ui;font-style:italic;}

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
    v041.src = "/static/v041-poker8-v2-turn-clarity.js?v=desktop-oval-30";
    v041.setAttribute("data-v041-poker8-v2-turn-clarity", "");
    document.body.appendChild(v041);
  }

  function ensureDynamicSeatLayout() {
    if (document.querySelector("script[data-v040-poker8-v2-dynamic-seats]")) {
      ensureTurnClarityPatch();
      return;
    }
    const v040 = document.createElement("script");
    v040.src = "/static/v040-poker8-v2-dynamic-seats.js?v=desktop-oval-30";
    v040.setAttribute("data-v040-poker8-v2-dynamic-seats", "");
    v040.addEventListener("load", ensureTurnClarityPatch, { once:true });
    document.body.appendChild(v040);
  }

  if (!document.querySelector('script[data-v038-poker8-v2-cinematic-table]')) {
    const v038 = document.createElement("script");
    v038.src = "/static/v038-poker8-v2-cinematic-table.js?v=desktop-oval-30";
    v038.setAttribute("data-v038-poker8-v2-cinematic-table", "");
    v038.addEventListener("load", ensureDynamicSeatLayout, { once: true });
    document.body.appendChild(v038);
  } else {
    ensureDynamicSeatLayout();
  }
})();
