(() => {
  const $ = id => document.getElementById(id);
  const number = (value, digits = 0) => Number(value || 0).toLocaleString('ru-RU', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
  const units = value => number(Number(value || 0) / 100, 2);
  const signed = value => `${Number(value) > 0 ? '+' : ''}${units(value)}`;
  const bb = value => `${Number(value) > 0 ? '+' : ''}${number(value, 1)} BB`;
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
  const LEDGER_KINDS = {
    buy_in: 'Бай-ин', add_on: 'Докупка', return: 'Возврат со стола',
    settlement: 'Расчёт раздачи', faucet_grant: 'Начисление',
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
    $('tableStack').textContent = units(profile.active_table_stack_units);
    const left = profile.xp_to_next_level;
    $('levelProgress').textContent = left == null ? 'Максимальный уровень' : `Ещё ${number(left)} XP до ${profile.level + 1} уровня`;
    $('returnToTable').hidden = !profile.active_table_id;
    if (profile.active_table_id) $('returnToTable').href = `/table?table=${encodeURIComponent(profile.active_table_id)}`;
    $('profileLoading').hidden = true;
    document.querySelector('.profile-hero').setAttribute('aria-busy', 'false');
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

  function historyRow(title, detail, amount) {
    const outcome = amount > 0 ? 'win' : amount < 0 ? 'loss' : 'flat';
    return `<article class="history-row ${outcome}">
      <div class="history-what"><span class="history-sign" aria-hidden="true">${amount > 0 ? '↗' : amount < 0 ? '↙' : '–'}</span><div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></div></div>
      <span class="history-amount">${signed(amount)}</span>
    </article>`;
  }

  function handRow(hand) {
    const mine = (hand.players || []).find(player => player.you);
    const net = Number(mine?.net_units || 0);
    return historyRow(net > 0 ? 'Выигрыш' : net < 0 ? 'Проигрыш' : 'Без изменений',
      `${dateText(hand.completed_at || hand.started_at)} · ${(hand.players || []).length} ${noun((hand.players || []).length, 'игрок', 'игрока', 'игроков')}`, net);
  }

  function ledgerRow(row) {
    return historyRow(LEDGER_KINDS[row.kind] || row.kind, dateText(row.created_at), Number(row.amount_units || 0));
  }

  function renderHistory(payload) {
    const rows = (payload.hands || []).map(handRow);
    fill('handHistory', rows, 'Здесь будут ваши последние раздачи. Сыграйте первую за любым столом.');
    $('showHands').hidden = rows.length <= 5;
  }

  function renderLedger(payload) {
    const rows = (payload.entries || []).map(ledgerRow);
    fill('ledger', rows, 'Операций пока нет. Здесь будут движения игровых фишек.');
    $('showLedger').hidden = rows.length <= 5;
  }

  let topupEnabled = false;
  let toppingUp = false;
  function renderTopUp(enabled) {
    topupEnabled = enabled;
    $('topupDetails').hidden = !enabled;
    $('topupForm').querySelectorAll('input, button').forEach(control => { control.disabled = !enabled; });
    $('topupNote').textContent = enabled ? 'Только виртуальные фишки.' : 'Пополнение пока недоступно.';
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
      await loadBlock('/api/profile/play-journal?limit=20', 'ledger', renderLedger, 'Не удалось загрузить журнал.');
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
      ['showAchievements', 'achievementList', 'Все достижения'], ['showHands', 'handHistory', 'Все раздачи'], ['showLedger', 'ledger', 'Все операции'],
    ]) {
      $(buttonId).addEventListener('click', () => {
        const expanded = $(listId).classList.toggle('expanded');
        $(buttonId).setAttribute('aria-expanded', String(expanded));
        $(buttonId).innerHTML = `${expanded ? 'Свернуть' : label} <span aria-hidden="true">${expanded ? '↑' : '↓'}</span>`;
      });
    }
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const selectTab = selected => tabs.forEach(tab => {
      const active = tab === selected;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      $(tab.getAttribute('aria-controls')).hidden = !active;
    });
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => selectTab(tab));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) : tabs[1 - index];
        selectTab(next);
        next.focus();
      });
    });
  }

  async function load() {
    await window.Poker8Auth.ensureSession();
    // First login returns an auth receipt, not XP/level/balance-at-table.
    renderProfile(await json('/api/profile'));
    await Promise.all([
      loadBlock('/api/profile/missions', 'missionList', renderMissions, 'Не удалось загрузить задания. Обновите страницу.', 'missionsError'),
      loadBlock('/api/profile/stats', 'statsGrid', renderStats, 'Не удалось загрузить статистику. Обновите страницу.', 'statsError'),
      loadBlock('/api/profile/achievements', 'achievementList', renderAchievements, 'Не удалось загрузить достижения. Обновите страницу.', 'achievementsError'),
      loadBlock('/api/profile/hands?limit=20', 'handHistory', renderHistory, 'Не удалось загрузить историю.'),
      loadBlock('/api/profile/play-journal?limit=20', 'ledger', renderLedger, 'Не удалось загрузить журнал.'),
      json('/api/config').then(config => renderTopUp(Boolean(config.self_top_up_enabled))).catch(() => renderTopUp(false)),
    ]);
  }

  bindControls();
  load().catch(error => {
    console.error(error);
    $('profileLoading').hidden = true;
    showError('profileError', 'Профиль не загрузился. Откройте его через Telegram или обновите страницу.');
    showError('missionsError', 'Задания появятся после входа.');
    showError('statsError', 'Статистика появится после входа.');
    showError('achievementsError', 'Коллекция появится после входа.');
    $('missionList').replaceChildren();
    $('achievementList').replaceChildren();
    fill('handHistory', [], 'Не удалось загрузить историю.');
    fill('ledger', [], 'Не удалось загрузить журнал.');
    renderTopUp(false);
    document.querySelectorAll('[aria-busy]').forEach(node => node.setAttribute('aria-busy', 'false'));
  });
})();
