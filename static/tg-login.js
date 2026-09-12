/* Signing in from a browser, and staying there.

   Inside Telegram the Mini App hands the server `initData` and nobody sees a
   login screen. Opened at the site there is no initData, and the answer used
   to be "откройте приложение внутри Telegram" -- on a page the player had just
   deliberately opened.

   So: the bot vouches, the browser plays. The page asks the server for a
   one-time code, sends the player to the bot carrying it, and waits. The bot
   shows a short code back and asks for a confirmation, and the moment the
   server has heard it, the page reloads with a session.

   The confirmation is not ceremony. A deep link is text, and text gets
   forwarded: without it, anybody could open a login here, send their own link
   to somebody else, and be handed a session as whoever pressed the button.
   The code on this card and the code in the chat only match for the person
   looking at both.

   Telegram's own login widget is the other way to do this and it is not used
   here: it asks for a phone number and a code before it will say who somebody
   is, which is a long way round to an identity the bot has in one tap.

   Styles ride along in this file: the four pages that can show this card load
   four different stylesheets, and a fifth one for a single card is a fifth
   thing to keep in step. */
window.Poker8TgLogin = (() => {
  "use strict";

  //: How often the page asks whether Start has been pressed, and for how long.
  const POLL_MS = 1500;
  const GIVE_UP_MS = 10 * 60 * 1000;

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
    width:100%;min-height:50px;border:0;border-radius:13px;background:#2aabee;color:#fff;
    text-decoration:none;font:800 14px Manrope,sans-serif;cursor:pointer}
  .tg-gate-open:hover{filter:brightness(1.06)}
  .tg-gate-open:disabled{opacity:.6;cursor:default}
  .tg-gate-alt{color:#7e8489;font:600 12px Manrope,sans-serif;text-decoration:underline}
  .tg-gate-note{color:#7e8489;font-size:11px;min-height:15px}
  .tg-gate-wait{color:#c8b3f6}
  .tg-gate-code{display:grid;gap:5px;justify-items:center;width:100%;padding:12px;
    border:1px dashed rgba(255,255,255,.14);border-radius:13px}
  .tg-gate-code[hidden]{display:none}
  .tg-gate-code span{color:#7e8489;font-size:10px;font-weight:800;letter-spacing:.14em}
  .tg-gate-code b{font:800 26px/1 Manrope,sans-serif;letter-spacing:.22em;
    color:#f1f1f4;font-variant-numeric:tabular-nums}`;

  /** Telegram's own mark, drawn rather than typed: an emoji plane is a
      different shape on every platform, and this one sits on their button. */
  const PLANE = `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
    <path d="M21.9 4.3 18.9 19c-.2 1-.8 1.3-1.7.8l-4.6-3.4-2.2 2.1c-.3.3-.5.5-1 .5l.3-4.7 8.6-7.8c.4-.3-.1-.5-.6-.2L6.9 12.9 2.4 11.5c-1-.3-1-1 .2-1.4l18-6.9c.8-.3 1.5.2 1.3 1.1z"/>
  </svg>`;

  //: An invitation in the address is kept for the login, wherever on the
  //: site the player ends up starting it from.
  const REF_KEY = "poker8.ref";
  try {
    const ref = new URLSearchParams(location.search).get("ref");
    if (ref) sessionStorage.setItem(REF_KEY, ref);
  } catch (_) { /* no storage: the invitation only survives this page */ }
  const savedRef = () => { try { return sessionStorage.getItem(REF_KEY) || undefined; } catch (_) { return undefined; } };

  const post = (path, body) => fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  function card(appUrl) {
    const gate = document.createElement("div");
    gate.className = "tg-gate";
    gate.innerHTML = `<style>${STYLE}</style>
      <section class="tg-gate-card" role="dialog" aria-modal="true" aria-label="Вход через Telegram">
        <span class="tg-gate-mark">poker<i aria-hidden="true">♠</i></span>
        <h2>Вход через Telegram</h2>
        <p>Подтвердите вход в чате с ботом — и продолжайте играть здесь, в браузере.</p>
        <button class="tg-gate-open" type="button">${PLANE}Войти через Telegram</button>
        <div class="tg-gate-code" hidden><span>КОД НА ЭКРАНЕ</span><b></b></div>
        <p class="tg-gate-note" role="status"></p>
        <a class="tg-gate-alt" hidden>Открыть мини-приложение</a>
      </section>`;
    const alt = gate.querySelector(".tg-gate-alt");
    if (appUrl) {
      alt.href = appUrl;
      alt.hidden = false;
    }
    return gate;
  }

  let polling = null;

  async function begin(gate) {
    const button = gate.querySelector(".tg-gate-open");
    const note = gate.querySelector(".tg-gate-note");
    button.disabled = true;
    note.className = "tg-gate-note";
    note.textContent = "Открываем Telegram…";

    const response = await post("/api/auth/telegram/request", { ref: savedRef() });
    if (!response.ok) {
      button.disabled = false;
      note.textContent = "Вход через Telegram сейчас недоступен.";
      return;
    }
    const { nonce, url, code } = await response.json();
    // The bot will show this back. Confirming a code you cannot see on your
    // own screen is the one thing that turns a forwarded link into somebody
    // else's session, so the two are put side by side.
    const box = gate.querySelector(".tg-gate-code");
    box.querySelector("b").textContent = code || "";
    box.hidden = !code;
    // A new tab, so the game keeps its place: the player comes back to it
    // already signed in instead of to a page that has been navigated away.
    window.open(url, "_blank", "noopener");
    note.className = "tg-gate-note tg-gate-wait";
    note.textContent = "Подтвердите вход в чате с ботом — код должен совпасть.";
    watch(nonce, gate);
  }

  function watch(nonce, gate) {
    const note = gate.querySelector(".tg-gate-note");
    const startedAt = Date.now();

    function stop(message) {
      window.clearInterval(polling);
      polling = null;
      document.removeEventListener("visibilitychange", onReturn);
      note.className = "tg-gate-note";
      note.textContent = message;
      gate.querySelector(".tg-gate-open").disabled = false;
    }

    async function ask() {
      const response = await post("/api/auth/telegram/claim", { nonce }).catch(() => null);
      if (response?.status === 410) return stop("Ссылка устарела — нажмите «Войти» ещё раз.");
      if (response?.ok) {
        const body = await response.json().catch(() => ({}));
        // Anything but "pending" is a session in a cookie, and every page
        // boots normally from there.
        if (body.status !== "pending") return window.location.reload();
      }
      if (Date.now() - startedAt > GIVE_UP_MS) stop("Вход не подтверждён. Попробуйте ещё раз.");
    }

    // Coming back to the tab is the moment it most likely just happened, so
    // ask then rather than waiting out the rest of the interval.
    function onReturn() {
      if (document.visibilityState === "visible") ask();
    }

    window.clearInterval(polling);
    polling = window.setInterval(ask, POLL_MS);
    document.addEventListener("visibilitychange", onReturn);
  }

  /**
   * Show the card and never resolve -- the page has nothing to draw until
   * somebody is signed in, and a successful login reloads it. Resolves null
   * when there is no bot to sign in with, so the caller can fall back to its
   * own message.
   */
  function prompt(config) {
    if (!config?.telegram_login_bot || document.querySelector(".tg-gate")) {
      return Promise.resolve(null);
    }
    const gate = card(config.telegram_app_url);
    gate.querySelector(".tg-gate-open").addEventListener("click", () => {
      begin(gate).catch(() => {
        gate.querySelector(".tg-gate-open").disabled = false;
        gate.querySelector(".tg-gate-note").textContent = "Не удалось начать вход.";
      });
    });
    document.body.appendChild(gate);
    return new Promise(() => {});
  }

  return { prompt };
})();
