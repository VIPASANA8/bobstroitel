window.Poker8Auth = (() => {
  function telegramProfile() {
    const user = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (!user || typeof user !== "object") return null;
    const username = typeof user.username === "string" && user.username.trim()
      ? `@${user.username.trim().replace(/^@+/, "")}`
      : "";
    const name = [user.first_name, user.last_name]
      .filter(value => typeof value === "string" && value.trim())
      .map(value => value.trim())
      .join(" ");
    const rawPhotoUrl = typeof user.photo_url === "string" ? user.photo_url.trim() : "";
    let photoUrl = "";
    try {
      const url = new URL(rawPhotoUrl);
      if (url.protocol === "https:") photoUrl = url.href;
    } catch (_) {}
    return { displayName: username || name || "Игрок", photoUrl };
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
