(() => {
  let socket = null, tableId = null, handlers = {}, revision = 0, retry = 0, reconnectTimer = null;
  const request = (url, options = {}) => fetch(url, {credentials:'same-origin', ...options}).then(async response => { const data = await response.json(); if (!response.ok) throw Object.assign(new Error(data.detail?.message || 'Request failed'), {data}); return data; });
  function connect(id, nextHandlers = {}) {
    tableId = id; handlers = nextHandlers; clearTimeout(reconnectTimer); const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${protocol}://${location.host}/ws/tables/${encodeURIComponent(id)}`);
    socket.onopen = () => { retry = 0; handlers.onStatus?.('connected'); socket.send(JSON.stringify({type:'resync', known_revision:revision})); };
    socket.onmessage = event => { const message = JSON.parse(event.data); if (message.revision != null) revision = message.revision; handlers.onMessage?.(message); };
    socket.onclose = () => { handlers.onStatus?.('reconnecting'); const delay = Math.min(5000, 250 * 2 ** retry++); reconnectTimer = setTimeout(() => connect(tableId, handlers), delay); };
    return socket;
  }
  function sendAction(action, amountUnits = 0) { const command_id = crypto.randomUUID(); socket?.send(JSON.stringify({type:'action', command_id, expected_revision:revision, action, amount_units:amountUnits})); return command_id; }
  function disconnect() { clearTimeout(reconnectTimer); socket?.close(); socket = null; }
  function resync() { socket?.send(JSON.stringify({type:'resync', known_revision:revision})); }
  const id = () => encodeURIComponent(tableId);
  window.Poker8Transport = {connect, disconnect, sendAction, resync, ready:(seatNo,buyInUnits)=>request(`/api/tables/${id()}/ready`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({seat_no:seatNo,buy_in_units:buyInUnits,request_id:crypto.randomUUID()})}),cancelReady:()=>request(`/api/tables/${id()}/ready/cancel`,{method:'POST'}),observe:()=>request(`/api/tables/${id()}/observe`,{method:'POST'}),leave:()=>request(`/api/tables/${id()}/leave`,{method:'POST'}),addOn:amountUnits=>request(`/api/tables/${id()}/add-on`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({amount_units:amountUnits,request_id:crypto.randomUUID()})}),loadChat:()=>request(`/api/tables/${id()}/chat`),sendChat:text=>request(`/api/tables/${id()}/chat`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text})})};
})();
