window.Poker8Auth = (() => {
  async function ensureSession() {
    const profile = await fetch('/api/profile').then(response => response.ok ? response.json() : null).catch(() => null);
    if (profile) return profile;
    const initData = window.Telegram?.WebApp?.initData;
    if (initData) {
      const response = await fetch('/api/auth/telegram', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({init_data:initData})});
      if (!response.ok) throw new Error('Telegram session rejected');
      return response.json();
    }
    const config = await fetch('/api/config').then(response => response.json());
    if (config.development_profiles?.length) {
      const chosen = config.development_profiles[0];
      const response = await fetch(`/api/auth/dev/${chosen.telegram_user_id}`, {method:'POST'});
      if (response.ok) return response.json();
    }
    throw new Error('Откройте приложение внутри Telegram');
  }
  return {ensureSession};
})();
