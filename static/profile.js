(() => {
  const $ = id => document.getElementById(id);
  const number = (value, digits = 0) => Number(value || 0).toLocaleString('ru-RU', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
  const units = value => number(Number(value || 0) / 100, 2);
  const bb = value => `${Number(value) > 0 ? '+' : ''}${number(value, 1)} BB`;
  const product = new URLSearchParams(location.search).get('app') === 'cube' ? 'cube' : 'poker';
  const plural = new Intl.PluralRules('ru-RU');
  const noun = (value, one, few, many) => ({one, few, many})[plural.select(Number(value))] || many;
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
  const dateText = value => {
    const stamp = value ? new Date(value) : null;
    return !stamp || Number.isNaN(stamp.getTime()) ? '' : stamp.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  };
  const RANKS = {ROOKIE: 'Новичок', PLAYER: 'Игрок', REGULAR: 'Регуляр', GRINDER: 'Гриндер', SHARK: 'Акула', ELITE: 'Элита', VETERAN: 'Ветеран'};
  const ACHIEVEMENTS = {
    grind: ['Дистанция', '♠'], big_pot: ['Большой банк', '◆'], social: ['Знакомые лица', '♣'],
    straight: ['Стрит', '↗'], flush: ['Флеш', '♥'], full_house: ['Фулл-хаус', '▰'],
    quads: ['Каре', '♦'], straight_flush: ['Стрит-флеш', '♠'], royal_flush: ['Роял-флеш', '♛'],
    seven_deuce: ['Семь-два', '7'], still_alive: ['Всё ещё в игре', '↟'], back_from_the_dead: ['Возвращение', '↺'],
  };
  const RARITY = {common: 'Обычное', rare: 'Редкое', epic: 'Эпическое', legendary: 'Легендарное'};

  async function json(url, options = {}) {
    const response = await fetch(url, {signal: AbortSignal.timeout(15000), ...options});
    if (!response.ok) throw new Error(`${url} → ${response.status}`);
    return response.json();
  }

  function showError(id, message) {
    $(id).textContent = message;
    $(id).hidden = !message;
  }

  function fill(id, rows, empty) {
    $(id).innerHTML = rows.length ? rows.join('') : `<p class="history-empty">${escapeHtml(empty)}</p>`;
  }

  // Each block settles on its own; a failed history request must not erase
  // the balance, achievements, or a successfully loaded journal.
  async function loadBlock(url, id, render, message, errorId) {
    try {
      render(await json(url));
    } catch (error) {
      console.error(error);
      if (errorId) {
        $(id).querySelectorAll('.profile-message').forEach(node => node.remove());
        showError(errorId, message);
      } else fill(id, [], message);
    } finally {
      $(id).closest('[aria-busy]')?.setAttribute('aria-busy', 'false');
    }
  }

  function renderProfile(profile) {
    const name = profile.display_name || 'Игрок';
    $('profileName').textContent = name;
    $('avatarInitials').textContent = name.trim().split(/\s+/).slice(0, 2).map(part => Array.from(part)[0]).join('').toUpperCase();
    $('levelBadge').textContent = profile.level;
    $('rankBadge').textContent = RANKS[profile.rank] || profile.rank;
    $('xp').textContent = number(profile.xp);
    $('wins').textContent = number(profile.wins);
    $('hands').textContent = number(profile.hands_played);
    $('handsLabel').textContent = noun(profile.hands_played, 'раздача', 'раздачи', 'раздач');
    $('winsLabel').textContent = noun(profile.wins, 'победа', 'победы', 'побед');
    $('walletBalance').textContent = units(profile.available_units);
    refillAt = profile.play_refill_at || null;
    $('tableStack').textContent = units(profile.active_table_stack_units);
    const left = profile.xp_to_next_level;
    $('levelProgress').textContent = left == null ? 'Максимальный уровень' : `Ещё ${number(left)} XP до ${profile.level + 1} уровня`;
    $('returnToTable').hidden = !profile.active_table_id;
    if (profile.active_table_id) $('returnToTable').href = `/table?table=${encodeURIComponent(profile.active_table_id)}`;
    $('profileLoading').hidden = true;
    document.querySelector('.profile-hero').setAttribute('aria-busy', 'false');
  }

  function applyProduct() {
    const cube = product === 'cube';
    document.body.classList.toggle('cube-context', cube);
    document.title = cube ? 'CUBE · Профиль' : 'Poker · Профиль';
    $('brandLogo').innerHTML = cube ? 'cube<i aria-hidden="true">⬢</i>' : 'poker<i aria-hidden="true">♠</i>';
    $('brandLogo').href = cube ? '/static/profile.html?app=poker#cash' : '/static/profile.html?app=cube#cash';
    $('brandLogo').setAttribute('aria-label', cube ? 'Переключиться на Poker' : 'Переключиться на CUBE');
    $('backToProduct').href = cube ? '/cube' : '/';
    $('backToProductLabel').textContent = cube ? 'В CUBE' : 'В лобби';
    $('cashModeLabel').textContent = cube ? 'USDT-касса' : 'CASH-касса';
    $('cashModeMark').textContent = cube ? 'USDT' : '$$$';
    $('profileModeLabel').textContent = cube ? 'Профиль CUBE' : 'Профиль Poker';
    $('cashKicker').textContent = cube ? 'CUBE WALLET' : 'REAL CASH';
    $('cashHeading').textContent = cube ? 'USDT-касса' : 'CASH-касса';
    $('pokerProfile').hidden = cube;
    $('cubeProfile').hidden = !cube;
  }

  // CASH is exact money in micro-USDT; it never goes through the play-chip
  // formatter, which divides by 100.
  const usdt = micros => {
    const amount = BigInt(micros || 0);
    const sign = amount < 0n ? '-' : amount > 0n ? '+' : '';
    const absolute = amount < 0n ? -amount : amount;
    const tail = String(absolute % 1000000n).padStart(6, '0').replace(/0+$/, '');
    return sign + (absolute / 1000000n) + (tail ? '.' + tail : '') + ' USDT';
  };

  function renderCashWallet(wallet) {
    for (const [name, strongId, smallId] of [
      ['available', 'profileCashAvailable', 'profileCashAvailableUsdt'],
      ['escrow', 'profileCashEscrow', 'profileCashEscrowUsdt'],
      ['withdrawal', 'profileCashWithdrawal', 'profileCashWithdrawalUsdt'],
    ]) {
      $(strongId).textContent = product === 'cube'
        ? `${wallet[`${name}_usdt`]} USDT` : `${wallet[`${name}_units`]} CASH`;
      $(smallId).textContent = product === 'cube'
        ? `${wallet[`${name}_units`]} CASH` : `${wallet[`${name}_usdt`]} USDT`;
    }
  }

  function setSigned(element, value, format) {
    element.textContent = value == null ? '—' : format(value);
    element.classList.toggle('up', Number(value) > 0);
    element.classList.toggle('down', Number(value) < 0);
  }

  function renderDay(element, day) {
    setSigned(element, day?.net_bb, value => `${bb(value)} · ${day.day.slice(8)}.${day.day.slice(5, 7)}`);
  }

  function renderStats(stats) {
    $('statsSample').textContent = `Выборка: ${number(stats.result_hands)} ${noun(stats.result_hands, 'зачётная раздача', 'зачётные раздачи', 'зачётных раздач')}`;
    $('statsAccounting').textContent = `С начала учёта — ${number(stats.hands)} ${noun(stats.hands, 'раздача', 'раздачи', 'раздач')}, выиграно ${number(stats.hands_won)}. Результат и BB / 100 считаются только за сетевыми столами. Сессия учитывается от 10 раздач. Общий счёт у имени включает и игру до запуска статистики.`;
    $('statsConfidence').textContent = {low: 'Небольшая выборка', medium: 'Средняя выборка', high: 'Большая выборка'}[stats.confidence] || '';
    $('statSessions').textContent = number(stats.sessions);
    $('statDays').textContent = number(stats.days_played);
    $('sessionsLabel').textContent = noun(stats.sessions, 'сессия', 'сессии', 'сессий');
    $('daysLabel').textContent = noun(stats.days_played, 'день', 'дня', 'дней');
    setSigned($('statBbPer100'), stats.bb_per_100, value => number(value, 1));
    setSigned($('statNetBb'), stats.result_hands ? stats.net_bb : null, bb);
    $('statBiggestPot').textContent = stats.biggest_pot_bb ? `${number(stats.biggest_pot_bb, 1)} BB` : '—';
    $('statLongest').textContent = stats.longest_session_minutes ? `${number(stats.longest_session_minutes)} мин` : '—';
    renderDay($('statBestDay'), stats.best_day);
    renderDay($('statWorstDay'), stats.worst_day);
    $('statsEmpty').hidden = stats.result_hands > 0;
  }

  function renderMissions(payload) {
    $('missionsCount').textContent = `${payload.completed} / ${payload.missions.length}`;
    $('missionsBonus').textContent = `+${payload.completion_xp} XP`;
    $('missionsBonusLabel').textContent = payload.completed === payload.missions.length ? 'Бонус получен' : 'Бонус за все три';
    $('missionsNote').textContent = payload.completed === payload.missions.length
      ? 'На сегодня всё. Новые задания — завтра.'
      : payload.reroll_available ? '↻ Одно задание в день можно заменить.' : 'Замена на сегодня использована.';
    $('missionList').innerHTML = payload.missions.map(item => `
      <div class="mission ${item.done ? 'done' : ''}">
        <div class="mission-copy">
          <b>${escapeHtml(item.title)}</b>
          <div class="mission-meta"><span class="at">${item.done ? 'Выполнено' : `${number(item.progress)} / ${number(item.target)}`}</span><span class="gain">+${item.xp} XP</span></div>
          <progress class="mission-bar" value="${Math.min(item.progress, item.target)}" max="${item.target}" aria-label="${escapeHtml(item.title)}"></progress>
        </div>
        ${item.done ? '<span class="mission-check" aria-hidden="true">✓</span>' : payload.reroll_available
          ? `<button class="mission-reroll" type="button" data-reroll="${escapeHtml(item.slot)}" aria-label="Заменить: ${escapeHtml(item.title)}" title="Заменить задание">↻</button>` : ''}
      </div>`).join('');
  }

  let rerolling = false;
  async function rerollMission(slot) {
    if (rerolling) return;
    rerolling = true;
    showError('missionsError', '');
    document.querySelectorAll('[data-reroll]').forEach(button => { button.disabled = true; });
    try {
      await json(`/api/profile/missions/${encodeURIComponent(slot)}/reroll`, {method: 'POST'});
      renderMissions(await json('/api/profile/missions'));
    } catch (error) {
      showError('missionsError', 'Не удалось заменить задание. Обновите страницу, чтобы проверить его состояние.');
      // A concurrent request can spend the quota. Refresh rather than leaving
      // another apparently available swap on the screen.
      try { renderMissions(await json('/api/profile/missions')); } catch (_) { /* Keep the visible error. */ }
    } finally {
      rerolling = false;
      document.querySelectorAll('[data-reroll]').forEach(button => { button.disabled = false; });
    }
  }

  function renderAchievements(payload) {
    $('achievementPoints').textContent = `${number(payload.achievement_points)} AP`;
    $('achievementsCount').textContent = `${payload.completed} / ${payload.total}`;
    const items = [...payload.achievements].sort((a, b) => Number(b.tier > 0) - Number(a.tier > 0));
    $('achievementList').innerHTML = items.map(item => {
      const secret = item.secret && !item.tier;
      // Do not localize by code before checking secrecy: the API deliberately
      // conceals the title while still returning a stable achievement code.
      const [title, symbol] = secret ? ['Секретное', '?'] : ACHIEVEMENTS[item.code] || [item.title, '◇'];
      const done = item.tier === item.tiers;
      const status = item.tiers > 1
        ? `Ступень ${item.tier} / ${item.tiers}` : done ? 'Получено' : 'Не открыто';
      return `<article class="achievement ${item.tier ? 'earned' : 'locked'}">
        <span class="achievement-medal" aria-hidden="true">${symbol}</span>
        <b>${escapeHtml(title)}</b><span class="at">${status}</span><span class="achievement-rarity">${escapeHtml(RARITY[item.rarity])}</span>
        ${item.tiers > 1 && !done ? `<span class="at">${number(item.progress)} / ${number(item.next_threshold)}</span>` : ''}
        ${item.tiers > 1 && !done ? `<progress class="achievement-bar" value="${Math.min(item.progress, item.next_threshold)}" max="${item.next_threshold}" aria-label="${escapeHtml(title)}"></progress>` : ''}
      </article>`;
    }).join('');
    $('showAchievements').hidden = items.length <= 6;
  }

  //: One arrow, drawn once: up-right for money in, the same path turned
  //: half a turn for money out, a bar for neither. The glyphs it replaces were
  //: whatever ↗ ↙ – happened to be in the system font, which is why they sat
  //: at three different weights and three different optical sizes.
  const ARROW = '<svg class="ui-arrow" viewBox="0 0 16 16"><path d="M4 12 12 4M6 4h6v6"/></svg>';
  const FLAT = '<svg class="ui-arrow" viewBox="0 0 16 16"><path d="M3.5 8h9"/></svg>';
  const signIcon = amount => (amount > 0 ? ARROW : amount < 0 ? ARROW : FLAT);

  function pokerActivity(hand) {
    const mine = (hand.players || []).find(player => player.you);
    const net = Number(mine?.net_micros || 0);
    const seated = (hand.players || []).length;
    const handId = hand.hand_id;
    return {
      id: `poker:${handId}`, category: 'poker', amountMicros: net,
      title: net > 0 ? 'Выигрыш в POKER' : net < 0 ? 'Проигрыш в POKER' : 'Раздача без изменений',
      detail: `${dateText(hand.completed_at || hand.started_at)} · ${seated} ${noun(seated, 'игрок', 'игрока', 'игроков')}`,
      createdAt: hand.completed_at || hand.started_at,
    };
  }

  function cubeActivity(round) {
    return {
      id: `cube:${round.round_id}`, category: 'cube', amountMicros: Number(round.net_micros || 0),
      title: round.won ? 'Выигрыш в CUBE' : 'Проигрыш в CUBE',
      detail: `${dateText(round.created_at)} · выпало ${round.roll} · выбрано ${(round.selected || []).join(', ')}`,
      createdAt: round.created_at,
    };
  }

  function operationActivities(wallet) {
    const unique = new Map();
    for (const row of wallet.journal || []) {
      const scope = String(row.scope || '');
      const deposit = row.kind === 'deposit';
      const withdrawal = scope.startsWith('withdrawal-') && row.kind === 'payout';
      if (!deposit && !withdrawal || unique.has(row.id)) continue;
      unique.set(row.id, {
        id: `operation:${row.id}`, category: 'operation', amountMicros: Number(row.amount_micros || 0),
        title: deposit ? 'Пополнение' : 'Вывод средств', detail: dateText(row.created_at), createdAt: row.created_at,
      });
    }
    return [...unique.values()];
  }

  function cashAmount(micros) {
    const amount = BigInt(micros || 0);
    const sign = amount < 0n ? '-' : amount > 0n ? '+' : '';
    const absolute = amount < 0n ? -amount : amount;
    const tail = String(absolute % 100000n).padStart(5, '0').replace(/0+$/, '');
    return `${sign}${absolute / 100000n}${tail ? `.${tail}` : ''} CASH`;
  }

  function cashActivityRow(row) {
    const outcome = row.amountMicros > 0 ? 'win' : row.amountMicros < 0 ? 'loss' : 'flat';
    const primary = product === 'cube' ? usdt(row.amountMicros) : cashAmount(row.amountMicros);
    const secondary = product === 'cube' ? cashAmount(row.amountMicros) : usdt(row.amountMicros);
    return `<article class="history-row ${outcome}">
      <div class="history-what"><span class="history-sign" aria-hidden="true">${signIcon(row.amountMicros)}</span><div><strong>${escapeHtml(row.title)}</strong><small>${escapeHtml(row.detail)}</small></div></div>
      <span class="history-amount"><b>${escapeHtml(primary)}</b><small>${escapeHtml(secondary)}</small></span>
    </article>`;
  }

  function renderCashHistory(wallet, pokerPayload, cubePayload) {
    const rows = [
      ...(pokerPayload.hands || []).map(pokerActivity),
      ...(cubePayload.rounds || []).map(cubeActivity),
      ...operationActivities(wallet),
    ].sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt));
    const render = (id, selected, empty) => fill(id, rows.filter(selected).map(cashActivityRow), empty);
    render('allHistory', () => true, 'Операций пока нет.');
    render('cubeHistory', row => row.category === 'cube', 'Игр в CUBE пока нет.');
    render('pokerHistory', row => row.category === 'poker', 'Раздач в POKER пока нет.');
    render('operationsHistory', row => row.category === 'operation', 'Пополнений и выводов пока нет.');
    $('showCashHistory').hidden = rows.length <= 5;
    $('allHistoryPanel').setAttribute('aria-busy', 'false');
  }

  // Set from the profile payload; only ever non-null while the player is out
  // of chips and the faucet is still shut.
  let refillAt = null;
  let topupEnabled = false;
  let toppingUp = false;
  function renderTopUp(enabled) {
    topupEnabled = enabled;
    $('topupDetails').hidden = !enabled;
    $('topupForm').querySelectorAll('input, button').forEach(control => { control.disabled = !enabled; });
    $('topupNote').textContent = enabled ? 'Только виртуальные фишки.'
      : refillAt ? `Фишки закончились. Новые — ${dateText(refillAt)}.`
      // Nothing at all when there is nothing to say: "пополнение пока
      // недоступно" is a line about a feature the player never asked for.
      : '';
    if (enabled && location.hash === '#topup') $('topupDetails').open = true;
  }

  async function topUp(displayAmount) {
    const value = Number(displayAmount);
    if (!topupEnabled || toppingUp || !Number.isFinite(value) || value < 1 || value > 1000000) return;
    toppingUp = true;
    $('topupForm').querySelectorAll('input, button').forEach(control => { control.disabled = true; });
    try {
      const result = await json('/api/profile/play-top-up', {
        method: 'POST', headers: {'content-type': 'application/json'},
        body: JSON.stringify({amount_units: Math.round(value * 100), request_id: crypto.randomUUID?.() || `profile-${Date.now()}-${Math.random().toString(36).slice(2)}`}),
      });
      $('walletBalance').textContent = units(result.available_units);
      $('topupNote').textContent = `Зачислено ${units(Math.round(value * 100))} фишек.`;
    } catch (error) {
      $('topupNote').textContent = 'Пополнение не прошло. Попробуйте ещё раз.';
    } finally {
      toppingUp = false;
      $('topupForm').querySelectorAll('input, button').forEach(control => { control.disabled = !topupEnabled; });
    }
  }

  function bindControls() {
    $('missionList').addEventListener('click', event => {
      const button = event.target.closest('[data-reroll]');
      if (button) rerollMission(button.dataset.reroll);
    });
    $('topupPresets').addEventListener('click', event => {
      const button = event.target.closest('[data-amount]');
      if (button) topUp(Number(button.dataset.amount) / 100);
    });
    $('topupForm').addEventListener('submit', event => { event.preventDefault(); topUp($('topupAmount').value); });
    for (const [buttonId, listId, label] of [
      ['showAchievements', 'achievementList', 'Все достижения'],
    ]) {
      $(buttonId).addEventListener('click', () => {
        const expanded = $(listId).classList.toggle('expanded');
        $(buttonId).setAttribute('aria-expanded', String(expanded));
        $(buttonId).innerHTML = `${expanded ? 'Свернуть' : label} <span aria-hidden="true">${expanded ? '↑' : '↓'}</span>`;
      });
    }
    $('showCashHistory').addEventListener('click', () => {
      const expanded = !$('allHistory').classList.contains('expanded');
      $('cashHistory').querySelectorAll('.history-list').forEach(list => list.classList.toggle('expanded', expanded));
      $('showCashHistory').setAttribute('aria-expanded', String(expanded));
      $('showCashHistory').innerHTML = `${expanded ? 'Свернуть' : 'Вся история'} <span aria-hidden="true">${expanded ? '↑' : '↓'}</span>`;
    });
    // Per tablist, not per page: the profile has two independent groups now
    // (Профиль / CASH-касса above, Раздачи / Операции inside), and one flat
    // list of every [role="tab"] would hide one group's panel whenever the
    // other group was used.
    document.querySelectorAll('[role="tablist"]').forEach(bindTabs);
  }

  function bindTabs(list) {
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    const selectTab = selected => tabs.forEach(tab => {
      const active = tab === selected;
      tab.setAttribute('aria-selected', String(active));
      tab.classList.toggle('is-active', active);
      tab.tabIndex = active ? 0 : -1;
      $(tab.getAttribute('aria-controls')).hidden = !active;
    });
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => selectTab(tab));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const step = event.key === 'ArrowLeft' ? -1 : 1;
        const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1)
          : tabs[(index + step + tabs.length) % tabs.length];
        selectTab(next);
        next.focus();
      });
    });
    list.selectTab = selectTab;
  }

  // The cashier only exists for a player the pilot actually lets in, so its
  // tab appears with the wallet and not before.
  async function loadCashData() {
    const wallet = await json('/api/cash/wallet');
    const [pokerPayload, cubePayload] = await Promise.all([
      json('/api/profile/hands?limit=20&asset=CASH_USDT').catch(() => ({hands: []})),
      json('/api/cube/history?limit=20').catch(() => ({rounds: []})),
    ]);
    renderCashWallet(wallet);
    renderCashHistory(wallet, pokerPayload, cubePayload);
  }

  async function openCashier() {
    await loadCashData();
    $('cashModeTab').hidden = false;
    // One tab is not a choice: the switch appears only once there are two.
    document.querySelector('.profile-modes').hidden = false;
    window.Poker8Cashier.mount({
      onSettled: () => loadCashData().catch(console.error),
    });
    // The money is what the profile opens on, here and from the lobby's
    // "Открыть CASH-кассу" alike. Profile stays one tap to the right.
    document.querySelector('.profile-modes').selectTab($('cashModeTab'));
  }

  async function load() {
    const session = await window.Poker8Auth.ensureSession();
    // ensureSession publishes the profile when it got there through the
    // session cookie, which is the usual way in; only a fresh login returns an
    // auth receipt instead, and that one has no XP, level or table stack.
    if (product === 'poker') renderProfile(window.Poker8Profile || await json('/api/profile'));
    void session;
    const config = await json('/api/config').catch(() => ({}));
    renderTopUp(product === 'poker' && Boolean(config.self_top_up_enabled));
    const pokerBlocks = product === 'poker' ? [
      loadBlock('/api/profile/missions', 'missionList', renderMissions, 'Не удалось загрузить задания. Обновите страницу.', 'missionsError'),
      loadBlock('/api/profile/stats', 'statsGrid', renderStats, 'Не удалось загрузить статистику. Обновите страницу.', 'statsError'),
      loadBlock('/api/profile/achievements', 'achievementList', renderAchievements, 'Не удалось загрузить достижения. Обновите страницу.', 'achievementsError'),
    ] : [];
    await Promise.all([...pokerBlocks, openCashier().catch(() => { $('cashModeTab').hidden = true; })]);
  }

  applyProduct();
  bindControls();
  load().catch(error => {
    console.error(error);
    $('profileLoading').hidden = true;
    const signIn = window.Poker8Auth.needsSignIn(error);
    showError('profileError', signIn
      ? 'Войдите через Telegram: откройте профиль из бота.'
      : 'Профиль временно недоступен. Попробуйте обновить страницу через минуту.');
    showError('missionsError', 'Задания появятся после входа.');
    showError('statsError', 'Статистика появится после входа.');
    showError('achievementsError', 'Коллекция появится после входа.');
    $('missionList').replaceChildren();
    $('achievementList').replaceChildren();
    fill('allHistory', [], 'Не удалось загрузить историю.');
    renderTopUp(false);
    document.querySelectorAll('[aria-busy]').forEach(node => node.setAttribute('aria-busy', 'false'));
  });
})();
