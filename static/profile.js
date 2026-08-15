(() => {
  const $ = id => document.getElementById(id);
  const units = value => (Number(value || 0) / 100).toFixed(2);

  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $('profileName').textContent = profile.display_name;
    $('telegramId').textContent = `Telegram ID · ${profile.telegram_user_id}`;
    $('levelBadge').textContent = `LEVEL ${profile.level}`;
    $('wins').textContent = profile.wins;
    $('hands').textContent = profile.hands_played;
    $('walletBalance').textContent = `${units(profile.available_units)} PLAY`;
    $('tableStack').textContent = `${units(profile.active_table_stack_units)} PLAY`;
    $('levelProgress').textContent = `${profile.wins} побед`;

    const returnLink = $('returnToTable');
    if (profile.active_table_id && returnLink) {
      returnLink.href = `/table?table=${encodeURIComponent(profile.active_table_id)}`;
      returnLink.hidden = false;
    }

    const history = await fetch('/api/profile/hands?limit=20').then(response => response.json());
    $('handHistory').innerHTML = (history.hands || [])
      .map(hand => `<article class="history-row"><strong>${hand.hand_id}</strong><span>${hand.players.length} игроков</span></article>`)
      .join('') || '<p class="dialog-muted">История появится после первой раздачи.</p>';

    const ledger = await fetch('/api/profile/play-journal?limit=20').then(response => response.json());
    $('ledger').innerHTML = (ledger.entries || [])
      .map(row => `<article class="history-row"><strong>${row.kind}</strong><span>${row.amount_units > 0 ? '+' : ''}${units(row.amount_units)} PLAY</span></article>`)
      .join('') || '<p class="dialog-muted">Операций пока нет.</p>';
  }

  load().catch(console.error);
})();
