(() => {
  const $ = id => document.getElementById(id);
  let tables = [];
  let selected = null;
  const format = units => (Number(units) / 100).toFixed(2);
  const buyInRange = table => `${Math.round(table.min_buy_in_units / table.big_blind_units)}–${Math.round(table.max_buy_in_units / table.big_blind_units)} BB`;
  const requestId = () => crypto.randomUUID?.() || `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $('wallet').textContent = `${format(profile.available_units)} PLAY`;
    const response = await fetch('/api/lobby/tables?page=1&per_page=6');
    const payload = await response.json(); tables = payload.tables;
    $('tableGrid').innerHTML = tables.map((table, index) => `<article class="table-card" style="--delay:${index * 45}ms"><div class="card-top"><span class="table-index">0${index + 1}</span><span class="table-state">● OPEN</span></div><h3>${table.name}</h3><p class="blinds">Blinds <b>${format(table.small_blind_units)} / ${format(table.big_blind_units)}</b></p><div class="card-bottom"><span>Entry ${buyInRange(table)}</span><span>${table.occupied_count} / 6</span></div><button class="card-action" data-table="${table.id}">Смотреть стол <span>↗</span></button></article>`).join('');
    document.querySelectorAll('[data-table]').forEach(button => button.addEventListener('click', () => openBuyIn(tables.find(table => table.id === button.dataset.table))));
  }
  function openBuyIn(table) {
    selected = table;
    $('buyInTable').textContent = `${table.name} · ${format(table.small_blind_units)} / ${format(table.big_blind_units)} BB`;
    // Every table has its own blinds, so the limits cannot live in the markup.
    const input = $('buyInUnits');
    input.min = table.min_buy_in_units;
    input.max = table.max_buy_in_units;
    input.step = table.big_blind_units;
    input.value = table.min_buy_in_units;
    $('buyInDialog').showModal();
  }
  const openTable = id => { window.location.href = `/table?table=${encodeURIComponent(id)}`; };
  $('buyInForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (!selected) return;
    const response = await fetch(`/api/tables/${selected.id}/ready`, {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({seat_no:2, buy_in_units:Number($('buyInUnits').value), request_id:requestId()})});
    $('buyInDialog').close();
    if (response.ok) return openTable(selected.id);
    const detail = (await response.json()).detail || {};
    // Already seated somewhere: take the player there instead of refusing.
    if (detail.code === 'already_seated' && detail.seat_state !== 'leaving') return openTable(detail.table_id);
    alert(detail.seat_state === 'leaving' ? 'Вы встаёте из-за стола — попробуйте через несколько секунд' : detail.message || 'Не удалось встать в очередь');
  });
  $('quickPlay').addEventListener('click', async () => { const response = await fetch('/api/lobby/quick-play', {method:'POST'}); if (!response.ok) return; openBuyIn((await response.json()).table); });
  load().catch(error => { $('loadStatus').textContent = 'OFFLINE'; console.error(error); });
})();
