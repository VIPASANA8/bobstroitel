(() => {
  const $ = id => document.getElementById(id);
  let tables = [];
  let selected = null;
  const format = units => (Number(units) / 100).toFixed(2);
  async function load() {
    const profile = await window.Poker8Auth.ensureSession();
    $('wallet').textContent = `${format(profile.available_units)} PLAY`;
    const response = await fetch('/api/lobby/tables?page=1&per_page=6');
    const payload = await response.json(); tables = payload.tables;
    $('tableGrid').innerHTML = tables.map((table, index) => `<article class="table-card" style="--delay:${index * 45}ms"><div class="card-top"><span class="table-index">0${index + 1}</span><span class="table-state">● OPEN</span></div><h3>${table.name}</h3><p class="blinds">Blinds <b>${format(table.small_blind_units)} / ${format(table.big_blind_units)}</b></p><div class="card-bottom"><span>Entry ${table.min_buy_in_bb}–${table.max_buy_in_bb} BB</span><span>${table.occupancy} / 6</span></div><button class="card-action" data-table="${table.id}">Смотреть стол <span>↗</span></button></article>`).join('');
    document.querySelectorAll('[data-table]').forEach(button => button.addEventListener('click', () => openBuyIn(tables.find(table => table.id === button.dataset.table))));
  }
  function openBuyIn(table) { selected = table; $('buyInTable').textContent = `${table.name} · ${format(table.small_blind_units)} / ${format(table.big_blind_units)} BB`; $('buyInUnits').value = table.min_buy_in_units; $('buyInDialog').showModal(); }
  $('buyInForm').addEventListener('submit', async event => { event.preventDefault(); if (!selected) return; const response = await fetch(`/api/tables/${selected.id}/ready`, {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({seat_no:2, buy_in_units:Number($('buyInUnits').value), request_id:crypto.randomUUID()})}); if (response.ok) window.location.href = `/table?table=${encodeURIComponent(selected.id)}`; else alert((await response.json()).detail?.message || 'Не удалось встать в очередь'); $('buyInDialog').close(); });
  $('quickPlay').addEventListener('click', async () => { const response = await fetch('/api/lobby/quick-play', {method:'POST'}); if (!response.ok) return; openBuyIn((await response.json()).table); });
  load().catch(error => { $('loadStatus').textContent = 'OFFLINE'; console.error(error); });
})();
