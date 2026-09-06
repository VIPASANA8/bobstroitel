/* Signing in from a browser.

   Inside Telegram the Mini App hands the server `initData` and nobody sees a
   login screen. Opened at the site there is no initData, and until now that
   was the end of it: "откройте приложение внутри Telegram", on a page the
   player had just deliberately opened. This is the other door Telegram
   provides -- the login widget -- and the same identity comes through it.

   The widget is an iframe Telegram renders itself, and it only renders on a
   domain linked to the bot in BotFather (/setdomain). Without that link it
   draws "Bot domain invalid" inside the button; if the browser blocks the
   frame outright, the card falls back to naming the other way in.

   Styles ride along in this file: the four pages that can show this card load
   four different stylesheets, and a fifth one for a single card is a fifth
   thing to keep in step. */
window.Poker8TgLogin = (() => {
  "use strict";

  const STYLE = `
  .tg-gate{position:fixed;inset:0;z-index:9999;display:grid;place-items:center;
    padding:20px;background:rgba(6,8,10,.92);backdrop-filter:blur(8px);
    font-family:Manrope,ui-sans-serif,system-ui,sans-serif;color:#f1f1f4}
  .tg-gate-card{width:min(360px,100%);display:grid;justify-items:center;gap:14px;
    padding:30px 24px;border:1px solid rgba(255,255,255,.09);border-radius:20px;
    background:#15171b;box-shadow:0 24px 70px rgba(0,0,0,.6);text-align:center}
  .tg-gate-mark{font:700 22px/1 'Unbounded',Manrope,sans-serif;letter-spacing:-1px}
  .tg-gate-mark>i{margin-left:4px;font:26px/1 Georgia,serif;font-style:normal;color:#c8b3f6}
  .tg-gate-card h2{margin:0;font-size:19px;letter-spacing:-.02em}
  .tg-gate-card p{margin:0;color:#a2a1ac;font-size:13px;line-height:1.5}
  .tg-gate-slot{min-height:48px;display:grid;place-items:center}
  .tg-gate-note{color:#7e8489;font-size:11px}`;

  let resolveSession = null;

  function card(bot) {
    const gate = document.createElement("div");
    gate.className = "tg-gate";
    gate.innerHTML = `<style>${STYLE}</style>
      <section class="tg-gate-card" role="dialog" aria-modal="true" aria-label="Вход через Telegram">
        <span class="tg-gate-mark">poker<i aria-hidden="true">♠</i></span>
        <h2>Вход через Telegram</h2>
        <p>Аккаунт, баланс и стол — те же, что в мини-приложении.</p>
        <div class="tg-gate-slot"></div>
        <p class="tg-gate-note">Нажимая кнопку, вы входите как ваш аккаунт Telegram.</p>
      </section>`;
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", bot);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-userpic", "false");
    // Telegram calls this by name on the window, so it has to be reachable there.
    script.setAttribute("data-onauth", "Poker8TgLogin.onAuth(user)");
    const slot = gate.querySelector(".tg-gate-slot");
    slot.appendChild(script);
    // Telegram draws the button in an iframe of its own. A browser that blocks
    // third-party frames leaves the slot empty, and an empty slot with no way
    // out is a dead end -- so the way out appears exactly when it is needed,
    // and never as a warning under a button that works.
    window.setTimeout(() => {
      if (slot.querySelector("iframe")) return;
      slot.textContent = "Кнопка Telegram не загрузилась — откройте игру из Telegram.";
      slot.style.color = "#a2a1ac";
      slot.style.fontSize = "13px";
      slot.style.lineHeight = "1.5";
    }, 4000);
    return gate;
  }

  /** Called by Telegram's iframe with the signed fields it just produced. */
  async function onAuth(user) {
    const response = await fetch("/api/auth/telegram/widget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Verbatim: every field Telegram sent is part of what it signed.
      body: JSON.stringify(user),
    });
    if (!response.ok) {
      const note = document.querySelector(".tg-gate-note");
      if (note) note.textContent = "Telegram не подтвердил вход. Попробуйте ещё раз.";
      return;
    }
    // The cookie is set; every page boots normally from here, so the shortest
    // way to a signed-in screen is the one the browser already knows.
    window.location.reload();
  }

  /**
   * Show the card and never resolve -- the page has nothing to draw until
   * somebody is signed in, and a successful login reloads it. Resolves null
   * when there is no button to show, so the caller can fall back to its own
   * message.
   */
  function prompt(config) {
    const bot = config?.telegram_login_bot;
    if (!bot || document.querySelector(".tg-gate")) return Promise.resolve(null);
    document.body.appendChild(card(bot));
    return new Promise(resolve => { resolveSession = resolve; });
  }

  return { prompt, onAuth, get pending() { return Boolean(resolveSession); } };
})();
