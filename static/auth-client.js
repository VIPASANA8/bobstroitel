window.Poker8Auth = (() => {
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
      publishTelegramProfile();
      const response = await fetch('/api/auth/telegram', {
        method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({init_data:initData}),
      });
      if (!response.ok) throw new Error('Telegram session rejected');
      return response.json();
    }
    const profile = await fetch('/api/profile').then(response => response.ok ? response.json() : null).catch(() => null);
    if (profile) return profile;
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
    throw new Error('Откройте приложение внутри Telegram');
  }
  return {ensureSession, telegramProfile, publishTelegramProfile};
})();
