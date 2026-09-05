window.Poker8Auth = (() => {
  //: Marks a failure as "nobody is signed in", as opposed to "the server is
  //: not answering". The two need different words on screen: one is the
  //: player's next step, the other is ours.
  function signIn(error) {
    error.needsSignIn = true;
    return error;
  }

  function telegramProfile() {
    const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (!user || typeof user !== "object") return null;
    // First name only, never @username -- a handle reads as a login, not a
    // player, and avatarInitials() splits on whitespace, so "@handle" was
    // rendering as just "@". Avatars are level-based, not from Telegram.
    const firstName = typeof user.first_name === "string" ? user.first_name.trim() : "";
    return { displayName: firstName || "Игрок" };
  }

  function publishTelegramProfile() {
    const profile = telegramProfile();
    if (profile) window.Poker8TelegramProfile = profile;
    return profile;
  }

  async function ensureSession() {
    const initData = window.Telegram?.WebApp?.initData;
    // A Telegram identity must win over a retained dev/guest cookie, otherwise
    // an old Guest profile masks the current @username at the live table.
    if (initData) {
      // Tells Telegram the app has finished loading; it clears the native
      // splash screen it would otherwise show until this fires (or times out).
      window.Telegram.WebApp.ready?.();
      // Without this, Telegram can open the Mini App at a shorter, "compact"
      // height instead of the device's full viewport -- our layout is entirely
      // 100dvh-relative, so a compact webview leaves real content (the action
      // buttons) positioned below the visible area, clipped by overflow:hidden
      // with no way to scroll to it. Every Mini App is expected to call this.
      window.Telegram.WebApp.expand?.();
      // Swiping down over the felt is a natural drag gesture during play --
      // without this it can also be read as "pull to minimize the app".
      window.Telegram.WebApp.disableVerticalSwipes?.();
      publishTelegramProfile();
      // Ask the session cookie first, and only sign in again if it cannot
      // answer. Every move between pages inside the Mini App is a fresh page
      // load, and re-posting initData meant a POST plus a signature check
      // standing between the tap and the first pixel -- on every one of them.
      // The cookie is good for a week; this is one GET, and it is the same GET
      // the profile page was about to make anyway.
      //
      // The Telegram identity still wins, because the cookie is only accepted
      // when it belongs to the person Telegram says is looking: a retained
      // dev/guest session cannot mask the current @username at a live table.
      // It also covers the case this check was first written for -- initData
      // is captured once, when Telegram opens the app, and the server stops
      // accepting it after fifteen minutes, which used to print "войдите через
      // Telegram" at a player who had never left Telegram.
      const telegramId = window.Telegram.WebApp.initDataUnsafe?.user?.id;
      const existing = await fetch('/api/profile')
        .then(profileResponse => profileResponse.ok ? profileResponse.json() : null).catch(() => null);
      if (existing && telegramId && Number(existing.telegram_user_id) === Number(telegramId)) {
        // The page that needs the full profile can have this one rather than
        // asking for it a second time.
        window.Poker8Profile = existing;
        return existing;
      }
      const response = await fetch('/api/auth/telegram', {
        method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({init_data:initData}),
      });
      if (!response.ok) {
        // Carry the server's reason: a wrong bot token has no session behind
        // it, so there is nothing to fall back to and it must fail loudly.
        const detail = await response.json().then(body => body.detail).catch(() => null);
        throw signIn(new Error(`Telegram session rejected: ${detail || response.status}`));
      }
      return response.json();
    }
    const profile = await fetch('/api/profile').then(response => response.ok ? response.json() : null).catch(() => null);
    if (profile) { window.Poker8Profile = profile; return profile; }
    const config = await fetch('/api/config').then(response => response.json());
    if (config.development_profiles?.length) {
      const chosen = config.development_profiles[0];
      const response = await fetch(`/api/auth/dev/${chosen.telegram_user_id}`, {method:'POST'});
      if (response.ok) return response.json();
    }
    if (config.open_access) {
      const response = await fetch('/api/auth/guest', {method:'POST'});
      if (response.ok) return response.json();
    }
    throw signIn(new Error('Откройте приложение внутри Telegram'));
  }
  return {ensureSession, telegramProfile, publishTelegramProfile, needsSignIn: error => Boolean(error?.needsSignIn)};
})();
