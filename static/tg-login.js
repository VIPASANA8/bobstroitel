/* Signing in from a browser.

   Inside Telegram the Mini App hands the server `initData` and nobody sees a
   login screen. Opened at the site there is no initData, and until now that
   was the end of it: "откройте приложение внутри Telegram", on a page the
   player had just deliberately opened. This is the other door Telegram
   provides -- the login widget -- and the same identity comes through it.

   Two ways in, and the app leads. Telegram's own browser login asks for a
   phone number and a code before it will hand over an identity -- a long way
   round for somebody who has Telegram installed on the same device -- so the
   first button is a link straight into the Mini App, where initData signs the
   player in with nothing to type. The widget stays behind "войти прямо в
   браузере" for whoever wants a session on the site itself. It is an iframe
   Telegram renders, and only on a domain linked to the bot in BotFather
   (/setdomain).

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
  .tg-gate-open{display:flex;align-items:center;justify-content:center;gap:9px;
    width:100%;min-height:50px;border-radius:13px;background:#2aabee;color:#fff;
    text-decoration:none;font:800 14px Manrope,sans-serif;letter-spacing:.01em}
  .tg-gate-open:hover{filter:brightness(1.06)}
  .tg-gate-alt{border:0;background:none;color:#7e8489;font:600 12px Manrope,sans-serif;
    text-decoration:underline;cursor:pointer;padding:0}
  .tg-gate-slot{min-height:48px;display:grid;place-items:center}
  .tg-gate-slot[hidden]{display:none}
  .tg-gate-note{color:#7e8489;font-size:11px}`;

  let resolveSession = null;

  /** Telegram's own mark, drawn rather than typed: an emoji plane would be a
      different shape on every platform, and this one sits on their button. */
  const PLANE = `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
    <path d="M21.9 4.3 18.9 19c-.2 1-.8 1.3-1.7.8l-4.6-3.4-2.2 2.1c-.3.3-.5.5-1 .5l.3-4.7 8.6-7.8c.4-.3-.1-.5-.6-.2L6.9 12.9 2.4 11.5c-1-.3-1-1 .2-1.4l18-6.9c.8-.3 1.5.2 1.3 1.1z"/>
  </svg>`;

  function card(bot) {
    const gate = document.createElement("div");
    gate.className = "tg-gate";
    gate.innerHTML = `<style>${STYLE}</style>
      <section class="tg-gate-card" role="dialog" aria-modal="true" aria-label="Вход через Telegram">
        <span class="tg-gate-mark">poker<i aria-hidden="true">♠</i></span>
        <h2>Играть через Telegram</h2>
        <p>Аккаунт, баланс и стол — те же, что в мини-приложении.</p>
        <a class="tg-gate-open" href="${bot.appUrl}">${PLANE}Открыть в Telegram</a>
        <button class="tg-gate-alt" type="button" hidden>Войти прямо в браузере</button>
        <div class="tg-gate-slot" hidden></div>
        <p class="tg-gate-note">Вы войдёте как ваш аккаунт Telegram.</p>
      </section>`;

    const open = gate.querySelector(".tg-gate-open");
    const alt = gate.querySelector(".tg-gate-alt");
    const slot = gate.querySelector(".tg-gate-slot");
    if (!bot.appUrl) open.remove();
    // Staying in the browser costs a phone number and a code, which is a long
    // way round for somebody who has Telegram open on the same device. It is
    // offered, not led with -- and only when there is a widget behind it.
    if (bot.username) alt.hidden = false;
    else alt.remove();

    alt?.addEventListener("click", () => {
      alt.remove();
      slot.hidden = false;
      const script = document.createElement("script");
      script.async = true;
      script.src = "https://telegram.org/js/telegram-widget.js?22";
      script.setAttribute("data-telegram-login", bot.username);
      script.setAttribute("data-size", "large");
      script.setAttribute("data-radius", "12");
      script.setAttribute("data-userpic", "false");
      // Telegram calls this by name on the window, so it has to be reachable there.
      script.setAttribute("data-onauth", "Poker8TgLogin.onAuth(user)");
      slot.appendChild(script);
      // A browser that blocks third-party frames leaves the slot empty, and an
      // empty slot with nothing said about it is a dead end.
      window.setTimeout(() => {
        if (slot.querySelector("iframe")) return;
        slot.textContent = "Кнопка Telegram не загрузилась — откройте игру из Telegram.";
        slot.style.color = "#a2a1ac";
        slot.style.fontSize = "13px";
      }, 4000);
    });
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
    const bot = {
      username: config?.telegram_login_bot,
      appUrl: config?.telegram_app_url,
    };
    if ((!bot.username && !bot.appUrl) || document.querySelector(".tg-gate")) {
      return Promise.resolve(null);
    }
    document.body.appendChild(card(bot));
    return new Promise(resolve => { resolveSession = resolve; });
  }

  return { prompt, onAuth, get pending() { return Boolean(resolveSession); } };
})();
