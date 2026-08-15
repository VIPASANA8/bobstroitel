(() => {
  const tableId = new URLSearchParams(location.search).get('table');
  if (!tableId) return;
  document.querySelector('.app-shell')?.setAttribute('hidden', '');
  document.querySelector('#mobileGameHeader')?.setAttribute('hidden', '');
  const surface = document.createElement('main'); surface.id = 'onlineSurface'; surface.className = 'online-surface'; document.body.append(surface);
  const style = document.createElement('style'); style.textContent = '#mobileGameHeader[hidden],.app-shell[hidden]{display:none!important}.online-surface{width:min(720px,100%);min-height:100vh;margin:auto;padding:18px 14px 32px;background:radial-gradient(circle at 50% 35%,#174d3c,#07100f 62%);color:#f4f5ee}.online-table-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.online-table-head a{color:#91e8ba;text-decoration:none;font-size:12px;font-weight:800}.online-table-head span{color:#f3a15c;font:800 10px monospace;letter-spacing:.18em}.online-felt{min-height:420px;padding:24px 14px;border:2px solid #4b9f7c;border-radius:46% / 20%;background:#0b392f;box-shadow:inset 0 0 70px #021c14,0 12px 60px #0008}.online-table-title{text-align:center;color:#a0c9b4;font:11px monospace}.online-table-title p{margin:0 0 5px;color:#f4f5ee;font-weight:800}.online-table-title strong{color:#f3a15c}.online-pot{text-align:center;margin:70px 0 16px;color:#8fb9a6;font:10px monospace;letter-spacing:.12em}.online-pot strong{display:block;margin-top:8px;color:#f4f5ee;font:700 26px system-ui}.online-players{display:grid;gap:8px}.online-player{display:flex;align-items:center;gap:10px;padding:10px;border:1px solid #366c56;border-radius:14px;background:#08281fdd}.online-player.is-turn{border-color:#91e8ba;box-shadow:0 0 0 2px #91e8ba33}.online-seat{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;background:#173e31;color:#91e8ba;font:11px monospace}.online-player div{flex:1}.online-player strong,.online-player small{display:block}.online-player small{margin-top:3px;color:#84a695;font-size:10px}.online-player>b{color:#f3a15c;font-size:12px}.online-panel{margin-top:14px;padding:16px;border:1px solid #294d3e;border-radius:16px;background:#0b1915}.online-panel strong,.online-panel span{display:block}.online-panel span{margin-top:4px;color:#8fa69a;font-size:12px}.online-panel button,.online-chat form button{width:100%;margin-top:14px;padding:13px;border:0;border-radius:11px;background:#91e8ba;color:#082018;font-weight:900}.online-actions{display:flex;gap:8px;margin-top:14px}.online-actions button{flex:1;padding:13px;border:1px solid #416d59;border-radius:11px;background:#112c22;color:#f4f5ee;font-weight:800}.online-actions button:disabled{opacity:.4}.chat-title{display:flex;justify-content:space-between;color:#91e8ba}.chat-title span{display:inline;color:#819b8d}.online-chat #onlineMessages{max-height:130px;overflow:auto;margin-top:12px;color:#c1d0c7;font-size:12px;line-height:1.7}.online-chat form{display:flex;gap:8px;margin-top:10px}.online-chat input{flex:1;padding:11px;border:1px solid #294d3e;border-radius:10px;background:#07100f;color:#f4f5ee}.online-chat form button{width:42px;margin:0;padding:0}.online-error{padding:80px 20px;text-align:center}.online-error a{color:#91e8ba}'; document.head.append(style);
  let table = null;
  let viewerState = 'spectator';
  const units = value => (Number(value || 0) / 100).toFixed(2);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function shell() { surface.innerHTML = `<header class="online-table-head"><a href="/">← Лобби</a><span id="onlinePhase">WAITING</span><a href="/static/profile.html">Профиль</a></header><section class="online-felt"><div class="online-table-title"><p>${escape(table?.name || 'Poker8 table')}</p><strong>${units(table?.small_blind_units)} / ${units(table?.big_blind_units)} BB</strong></div><div id="onlinePlayers" class="online-players"></div><div class="online-pot" id="onlinePot">БАНК<br><strong>0.00</strong></div></section><section id="onlineReady" class="online-panel"><strong>Наблюдатель</strong><span>Выберите место и бай-ин от 40 BB</span><button id="onlineReadyButton">Готов за 40 BB →</button></section><section id="onlineActions" class="online-actions" hidden><button data-action="fold">Пас</button><button data-action="check">Чек</button><button data-action="call">Колл</button><button data-action="all_in">Олл-ин</button></section><section class="online-panel online-chat"><div class="chat-title"><strong>Чат стола</strong><span id="onlineConnection">connecting</span></div><div id="onlineMessages"></div><form id="onlineChatForm"><input id="onlineChatInput" maxlength="300" placeholder="Сообщение…"/><button>→</button></form></section>`; }
  function render(next) { document.getElementById('onlinePhase').textContent = String(next.phase || 'waiting').toUpperCase(); document.getElementById('onlinePot').innerHTML = `БАНК<br><strong>${Number(next.pot || 0).toFixed(2)} BB</strong>`; const players = Object.values(next.players || {}); document.getElementById('onlinePlayers').innerHTML = players.map(player => `<article class="online-player ${next.acting_player === player.id ? 'is-turn' : ''}"><span class="online-seat">${player.seat + 1}</span><div><strong>${escape(player.name)}</strong><small>${player.is_bot ? 'System player' : 'Player'} · ${player.stack} BB</small></div><b>${player.hole_cards?.[0] === '??' ? '•• ••' : player.hole_cards.join(' ')}</b></article>`).join(''); const ready = document.getElementById('onlineReady'); const actions = document.getElementById('onlineActions'); if (next.phase === 'active') { ready.hidden = true; actions.hidden = !next.legal_actions?.length; actions.querySelectorAll('button').forEach(button => button.disabled = !next.legal_actions.includes(button.dataset.action)); } else { ready.hidden = false; actions.hidden = true; } }
  const baseRender = render;
  render = next => {
    baseRender(next);
    window.Poker8OnlineTable = true;
    surface.dataset.viewerState = viewerState;
    let countdown = document.getElementById('onlineCountdown');
    if (!countdown) {
      countdown = document.createElement('small');
      countdown.id = 'onlineCountdown';
      countdown.style.cssText = 'display:block;text-align:center;margin-top:6px;color:#91e8ba;font:11px monospace';
      document.getElementById('onlinePhase')?.parentElement?.append(countdown);
    }
    const phase = String(next.phase || 'waiting');
    const target = phase === 'result' ? next.result_clear_at : phase === 'countdown' ? next.next_hand_at : null;
    const seconds = target ? Math.max(0, Math.ceil((Date.parse(target) - Date.now()) / 1000)) : 0;
    countdown.textContent = phase === 'result' ? `Следующая раздача через ${seconds} сек.` : phase === 'countdown' ? `Новая раздача через ${seconds} сек.` : '';
    const ready = document.getElementById('onlineReady');
    if (ready && phase !== 'waiting' && phase !== 'active') ready.hidden = true;
    if (ready && phase === 'waiting') {
      ready.querySelector('strong').textContent = viewerState === 'waiting' ? 'В очереди' : 'Наблюдатель';
      ready.querySelector('span').textContent = viewerState === 'waiting' ? 'Ожидаем свободное место между раздачами' : 'Выберите место и бай-ин от 40 BB';
      ready.querySelector('button').textContent = viewerState === 'waiting' ? 'Ожидание места…' : 'Готов за 40 BB →';
    }
    if (phase === 'countdown') {
      document.querySelectorAll('#onlinePlayers b').forEach(card => { card.textContent = '•• ••'; });
    }
  };

  async function refreshState() {
    const response = await fetch(`/api/tables/${encodeURIComponent(tableId)}`);
    if (response.ok) {
      const payload = await response.json();
      viewerState = payload.viewer_state || viewerState;
      render(payload.state);
    }
  }

  async function boot() { const payload = await fetch(`/api/tables/${encodeURIComponent(tableId)}`).then(response => response.json()); table = payload.table; viewerState = payload.viewer_state || viewerState; shell(); render(payload.state); setInterval(() => refreshState().catch(() => {}), 500); document.getElementById('onlineReadyButton').onclick = async () => { const result = await window.Poker8Transport.ready(2, Number(table.big_blind_units) * 40); viewerState = result.queue_state === 'waiting' ? 'waiting' : viewerState; render(payload.state); }; document.querySelectorAll('[data-action]').forEach(button => button.onclick = () => window.Poker8Transport.sendAction(button.dataset.action, 0)); window.Poker8Transport.connect(tableId, {onStatus: status => document.getElementById('onlineConnection').textContent = status, onMessage: message => { if (message.state) render(message.state); }}); const chat = await window.Poker8Transport.loadChat().catch(() => ({messages:[]})); document.getElementById('onlineMessages').innerHTML = (chat.messages || []).map(row => `<div><b>${escape(row.user_id)}</b> ${escape(row.text)}</div>`).join(''); document.getElementById('onlineChatForm').onsubmit = async event => { event.preventDefault(); const input = document.getElementById('onlineChatInput'); const text = input.value.trim(); if (text) { const sent = await window.Poker8Transport.sendChat(text); document.getElementById('onlineMessages').insertAdjacentHTML('beforeend', `<div><b>${escape(sent.user_id)}</b> ${escape(sent.text)}</div>`); input.value = ''; } }; }
  boot().catch(error => { surface.innerHTML = `<section class="online-error"><h1>Стол недоступен</h1><p>${escape(error.message)}</p><a href="/">Вернуться в лобби</a></section>`; });
})();
