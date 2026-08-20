(() => {
  let socket = null;
  let tableId = null;
  let handlers = {};
  let revision = 0;
  let retry = 0;
  let reconnectTimer = null;
  let intentionalClose = false;
  let actionInFlight = null;
  let actionAckTimer = null;
  let pendingAction = null;
  let actionRetrySocket = null;
  const requestId = () => crypto.randomUUID?.() || `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  function setActionInFlight(commandId) {
    clearTimeout(actionAckTimer);
    actionAckTimer = null;
    actionInFlight = commandId;
    if (!commandId) {
      pendingAction = null;
      const retrySocket = actionRetrySocket;
      actionRetrySocket = null;
      if (retrySocket && retrySocket.readyState <= WebSocket.OPEN) retrySocket.close();
    }
    window.dispatchEvent(new CustomEvent('poker8:action-pending', {detail:{pending:Boolean(commandId)}}));
  }

  function scheduleActionRecovery(delay = 1800) {
    clearTimeout(actionAckTimer);
    actionAckTimer = setTimeout(recoverPendingAction, delay);
  }

  function recoverPendingAction() {
    if (!actionInFlight || !pendingAction) return;
    if (pendingAction.retried || !tableId) {
      setActionInFlight(null);
      return;
    }
    // If the first socket silently loses an outgoing frame, a fresh authenticated
    // connection lets us observe the authoritative revision before one safe retry.
    pendingAction.retried = true;
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const retrySocket = new WebSocket(`${protocol}://${location.host}/ws/tables/${encodeURIComponent(tableId)}`);
    actionRetrySocket = retrySocket;
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      if (actionRetrySocket === retrySocket) actionRetrySocket = null;
      if (retrySocket.readyState <= WebSocket.OPEN) retrySocket.close();
      setActionInFlight(null);
    };
    const retryTimeout = setTimeout(finish, 5000);
    retrySocket.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.revision != null) revision = message.revision;
      if (message.type === 'snapshot' && message.reason === 'connected') {
        const state = message.state || {};
        const legal = state.legal_actions || [];
        // This dedicated socket is the only channel that submits the command.
        // Its fresh snapshot makes the expected revision authoritative and
        // prevents accidental execution after turn or legality has changed.
        if (state.acting_player !== state.viewer_player_id || !legal.includes(pendingAction.action)) {
          clearTimeout(retryTimeout);
          finish();
          handlers.onMessage?.(message);
          return;
        }
        pendingAction.expectedRevision = Number(message.revision || 0);
        pendingAction.commandId = requestId();
        retrySocket.send(JSON.stringify({
          type: 'action', command_id: pendingAction.commandId,
          expected_revision: pendingAction.expectedRevision,
          action: pendingAction.action, amount_units: pendingAction.amountUnits,
        }));
        return;
      }
      const actionResolved = message.type === 'command_rejected'
        || (message.type === 'snapshot' && ['state_changed', 'stale_revision'].includes(message.reason));
      if (actionResolved) {
        clearTimeout(retryTimeout);
        finish();
      }
      handlers.onMessage?.(message);
    };
    retrySocket.onerror = () => { clearTimeout(retryTimeout); finish(); };
    retrySocket.onclose = () => {
      if (!settled) { clearTimeout(retryTimeout); finish(); }
    };
  }

  const request = (url, options = {}) => fetch(url, {credentials: 'same-origin', ...options})
    .then(async response => {
      const data = await response.json();
      if (!response.ok) throw Object.assign(new Error(data.detail?.message || 'Request failed'), {data});
      return data;
    });

  function connect(id, nextHandlers = {}) {
    tableId = id;
    handlers = nextHandlers;
    intentionalClose = false;
    clearTimeout(reconnectTimer);
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${protocol}://${location.host}/ws/tables/${encodeURIComponent(id)}`);
    socket.onopen = () => {
      retry = 0;
      handlers.onStatus?.('connected');
      socket.send(JSON.stringify({type: 'resync', known_revision: revision}));
    };
    socket.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.revision != null) revision = message.revision;
      const actionResolved = message.type === 'command_rejected'
        || (message.type === 'snapshot' && ['state_changed', 'stale_revision'].includes(message.reason));
      if (actionInFlight && actionResolved) setActionInFlight(null);
      handlers.onMessage?.(message);
    };
    socket.onclose = () => {
      if (intentionalClose) {
        setActionInFlight(null);
        return;
      }
      if (actionInFlight && pendingAction && !pendingAction.retried) recoverPendingAction();
      else if (!actionRetrySocket) setActionInFlight(null);
      handlers.onStatus?.('reconnecting');
      const delay = Math.min(5000, 250 * 2 ** retry++);
      reconnectTimer = setTimeout(() => connect(tableId, handlers), delay);
    };
    return socket;
  }

  function sendAction(action, amountUnits = 0) {
    if (actionInFlight || !tableId) return null;
    const command_id = requestId();
    pendingAction = {commandId: command_id, action, amountUnits, expectedRevision: revision, retried: false};
    setActionInFlight(command_id);
    // A command-specific socket receives a fresh, authenticated snapshot before
    // it sends the action. The persistent socket remains dedicated to rendering.
    recoverPendingAction();
    return command_id;
  }

  function disconnect() {
    intentionalClose = true;
    clearTimeout(reconnectTimer);
    setActionInFlight(null);
    socket?.close();
    socket = null;
  }

  function reconnect() {
    intentionalClose = false;
    if (socket && socket.readyState <= WebSocket.OPEN) socket.close();
    else connect(tableId, handlers);
  }

  function resync() {
    socket?.send(JSON.stringify({type: 'resync', known_revision: revision}));
  }

  function setRevision(nextRevision) {
    if (Number.isFinite(Number(nextRevision))) revision = Math.max(revision, Number(nextRevision));
  }

  const id = () => encodeURIComponent(tableId);
  window.Poker8Transport = {
    connect, disconnect, reconnect, resync, setRevision, sendAction,
    isActionPending: () => Boolean(actionInFlight),
    ready: (seatNo, buyInUnits) => request(`/api/tables/${id()}/ready`, {
      method: 'POST', headers: {'content-type': 'application/json'},
      body: JSON.stringify({seat_no: seatNo, buy_in_units: buyInUnits, request_id: requestId()}),
    }),
    cancelReady: () => request(`/api/tables/${id()}/ready/cancel`, {method: 'POST'}),
    readyUp: () => request(`/api/tables/${id()}/ready-up`, {method: 'POST'}),
    leave: () => request(`/api/tables/${id()}/leave`, {method: 'POST'}),
    // Same request, but the page does not wait for it. keepalive is what lets
    // it outlive the navigation that follows, so leaving is instant even when
    // the table is mid-hand and the server takes a few seconds to fold the
    // hand out. If it fails anyway the lobby re-sends it while it waits.
    leaveInBackground: () => {
      try {
        fetch(`/api/tables/${id()}/leave`, {
          method: 'POST', credentials: 'same-origin', keepalive: true,
        }).catch(() => {});
      } catch {
        return request(`/api/tables/${id()}/leave`, {method: 'POST'});
      }
      return Promise.resolve();
    },
    addOn: amountUnits => request(`/api/tables/${id()}/add-on`, {
      method: 'POST', headers: {'content-type': 'application/json'},
      body: JSON.stringify({amount_units: amountUnits, request_id: requestId()}),
    }),
    loadChat: () => request(`/api/tables/${id()}/chat`),
    sendChat: text => request(`/api/tables/${id()}/chat`, {
      method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({text}),
    }),
  };
})();
