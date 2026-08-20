const ONLINE_TABLE_ID = new URLSearchParams(location.search).get("table");
let game = null;
let tableData = null;
let solverPreview = null;
let modalSeat = null;
let modalDifficulty = "normal";
let modalOccupantType = "bot";
let animationBusy = false;
let profileModalMode = "create";
let infiniteMode = localStorage.getItem("pokerTrainerInfiniteMode") === "1";
let botSpeedMode = localStorage.getItem("pokerTrainerBotSpeed") || "normal";
let spectatorPaused = false;
let automationTimer = null;
let autoSessionActive = false;
let cooldownRefreshPending = false;
let lastCooldownRefreshAt = 0;
const NEXT_HAND_DELAY = 1500;
const BOT_SPEED_RANGES = {
  fast: [900, 1700],
  normal: [2200, 4000],
  slow: [4200, 7000],
};
const REDUCED_MOTION = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
let pendingAction = null;
let pendingInvalidReason = "";
let actionTimerId = null;
let actionDeadline = 0;
let actionTurnToken = null;


const $ = (id) => document.getElementById(id);

/* v0.10.3 mobile sheets */
function isMobileLayout() {
  return window.matchMedia?.("(max-width: 780px)")?.matches ?? false;
}

function closeMobileSheets() {
  document.body.classList.remove("mobile-history-open", "mobile-solver-open", "sheet-open");
  const backdrop = $("mobileSheetBackdrop");
  if (backdrop) backdrop.hidden = true;
}

function openMobileSheet(kind) {
  if (!isMobileLayout()) {
    const target = kind === "history" ? document.querySelector(".history-card") : document.querySelector(".solver-panel");
    target?.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "start" });
    return;
  }
  closeMobileSheets();
  document.body.classList.add(kind === "history" ? "mobile-history-open" : "mobile-solver-open", "sheet-open");
  const backdrop = $("mobileSheetBackdrop");
  if (backdrop) backdrop.hidden = false;
}

function scrollToMobileTable() {
  closeMobileSheets();
  document.querySelector(".table-frame")?.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "start" });
}


const ACTION_LABELS = {
  fold: "Пас",
  check: "Чек",
  call: "Колл",
  bet: "Ставка",
  raise: "Рейз",
  all_in: "ALL-IN",
};

function localViewerPlayer() {
  if (!game) return null;
  return Object.values(game.players || {}).find(p =>
    (game.viewer_player_id && p.id === game.viewer_player_id)
    || (p.profile_id && p.profile_id === game.active_profile_id)
  ) || null;
}

function isLocalHumanTurn() {
  return Boolean(game && !game.terminal && (
    (game.acting_human_profile_id && game.acting_human_profile_id === game.active_profile_id)
    || (game.acting_human_player_id && game.acting_human_player_id === game.viewer_player_id)
  ));
}

function localPlayerAlive() {
  const player = localViewerPlayer();
  return Boolean(player && !player.folded && !player.all_in && Number(player.stack || 0) > 0);
}

function turnToken() {
  if (!game) return "";
  return [game.hand_id, game.street, game.acting_player, game.history?.length || 0].join(":");
}

function clearPendingAction(render = true) {
  pendingAction = null;
  pendingInvalidReason = "";
  if (render) renderQueuedActionStatus();
}

function togglePendingAction(kind) {
  if (!game || !localPlayerAlive() || game.terminal) return;
  const localPlayer = localViewerPlayer();
  const estimateToCall = Math.max(0, Number(game.current_bet || 0) - Number(localPlayer?.street_invested || 0));
  const amount = Number($("amount")?.value || 0);
  let next = null;
  if (!pendingAction || pendingAction.kind !== kind) {
    next = { kind, amount, estimateToCall, selectedAt: Date.now() };
  }
  pendingAction = next;
  pendingInvalidReason = "";
  renderQueuedActionStatus();
}

function queuedActionText(item = pendingAction) {
  if (!item) return "";
  if (item.kind === "fold") return "Маркер: Пас";
  if (item.kind === "check") return "Маркер: Чек";
  if (item.kind === "call") return `Маркер: Колл ${formatBB(item.estimateToCall || 0)}`;
  if (item.kind === "all_in") return "Маркер: ALL-IN";
  if (item.kind === "aggressive") return `Маркер: Ставка ${formatBB(item.amount || 0)}`;
  return "Маркер";
}

function renderQueuedActionStatus() {
  const status = $("preActionStatus");
  const clearBtn = $("clearQueuedAction");
  if (!status || !clearBtn) return;
  if (!pendingAction && !pendingInvalidReason) {
    status.hidden = true;
    status.textContent = "";
    status.classList.remove("invalid");
    clearBtn.hidden = true;
    renderMobileSelectedCard();
    return;
  }
  status.hidden = false;
  status.textContent = pendingInvalidReason || queuedActionText();
  status.classList.toggle("invalid", Boolean(pendingInvalidReason));
  clearBtn.hidden = !pendingAction && !pendingInvalidReason;
  renderMobileSelectedCard();
}

async function maybeAutoFirePendingAction() {
  if (!pendingAction || !game || animationBusy || !isLocalHumanTurn()) return false;
  const legal = game.human_legal_actions || [];
  if (!legal.length) return false;
  if (pendingAction.kind === "fold") {
    clearPendingAction(false);
    await sendAction(legal.includes("fold") ? "fold" : "check", 0);
    return true;
  }
  if (pendingAction.kind === "check") {
    if (legal.includes("check")) {
      clearPendingAction(false);
      await sendAction("check", 0);
      return true;
    }
    pendingInvalidReason = "Маркер «Чек» не сработал: появилась ставка";
    pendingAction = null;
    renderQueuedActionStatus();
    return false;
  }
  if (pendingAction.kind === "call") {
    const currentToCall = Number(game.human_to_call || 0);
    if (legal.includes("call") && Math.abs(currentToCall - Number(pendingAction.estimateToCall || 0)) < 1e-9) {
      clearPendingAction(false);
      await sendAction("call", 0);
      return true;
    }
    pendingInvalidReason = "Маркер «Колл» не сработал: сумма изменилась";
    pendingAction = null;
    renderQueuedActionStatus();
    return false;
  }
  if (pendingAction.kind === "all_in") {
    if (legal.includes("all_in")) {
      clearPendingAction(false);
      await sendAction("all_in", 0);
      return true;
    }
    pendingInvalidReason = "Маркер «ALL-IN» сейчас недоступен";
    pendingAction = null;
    renderQueuedActionStatus();
    return false;
  }
  if (pendingAction.kind === "aggressive") {
    const amount = Number(pendingAction.amount || 0);
    if (legal.includes("bet") && !(Number(game.human_to_call || 0) > 0) && amount > 0) {
      clearPendingAction(false);
      await sendAction("bet", amount);
      return true;
    }
    if (legal.includes("raise") && amount >= Number(game.human_min_raise_to || 0)) {
      clearPendingAction(false);
      await sendAction("raise", amount);
      return true;
    }
    pendingInvalidReason = "Маркер «Ставка» не сработал: текущая сумма выше выбранной";
    pendingAction = null;
    renderQueuedActionStatus();
    return false;
  }
  return false;
}

function startActionTimer() {
  stopActionTimer();
  // Network hands carry the server deadline; a local hand has none and keeps
  // the fixed 30 s clock.
  const serverDeadline = game?.action_deadline ? Date.parse(game.action_deadline) : NaN;
  actionDeadline = Number.isNaN(serverDeadline) ? Date.now() + 30000 : serverDeadline;
  actionTurnToken = turnToken();
  const el = $("actionTimer");
  if (!el) return;
  el.hidden = false;
  const tick = () => {
    const left = Math.max(0, actionDeadline - Date.now());
    const total = Math.ceil(left / 1000);
    const mm = String(Math.floor(total / 60)).padStart(2, "0");
    const ss = String(total % 60).padStart(2, "0");
    el.textContent = `${mm}:${ss}`;
    el.classList.toggle("danger", left <= 15000);
    const mobileTimer = $("mobileActionTimer");
    if (mobileTimer) mobileTimer.textContent = `${mm}:${ss}`;
    const mobileFill = $("mobileTimerFill");
    if (mobileFill) mobileFill.style.width = `${Math.max(0, Math.min(100, left / 30000 * 100))}%`;
    const timerCard = $("mobileTimerCard");
    timerCard?.classList.toggle("warning", left <= 15000 && left > 5000);
    timerCard?.classList.toggle("danger", left <= 5000);
    if (left <= 0) {
      stopActionTimer();
      if (isLocalHumanTurn() && !animationBusy) timeoutFold();
    }
  };
  tick();
  actionTimerId = setInterval(tick, 250);
}

function stopActionTimer() {
  if (actionTimerId) clearInterval(actionTimerId);
  actionTimerId = null;
  actionDeadline = 0;
  actionTurnToken = null;
  const el = $("actionTimer");
  if (el) {
    el.hidden = true;
    el.classList.remove("danger");
  }
  const mobileTimer = $("mobileActionTimer");
  if (mobileTimer) mobileTimer.textContent = "00:30";
  const mobileFill = $("mobileTimerFill");
  if (mobileFill) mobileFill.style.width = "100%";
  $("mobileTimerCard")?.classList.remove("warning", "danger");
}

function updateActionTimerState() {
  if (!game || game.terminal || !isLocalHumanTurn()) {
    stopActionTimer();
    return;
  }
  const token = turnToken();
  if (actionTurnToken !== token) startActionTimer();
}


const STREET_LABELS = {
  preflop: "ПРЕФЛОП",
  flop: "ФЛОП",
  turn: "ТЁРН",
  river: "РИВЕР",
  showdown: "ВСКРЫТИЕ",
  complete: "ЗАВЕРШЕНО",
};
const DIFFICULTY_LABELS = {
  easy: "Лёгкий",
  normal: "Нормальный",
  hard: "Сложный",
  maximum: "Максимальный",
};
const CHIP_DENOMS = [
  { value: 100, cls: "chip-100" },
  { value: 25, cls: "chip-25" },
  { value: 5, cls: "chip-5" },
  { value: 1, cls: "chip-1" },
  { value: 0.5, cls: "chip-05" },
];

function chipsForAmount(value, maxChips = 12) {
  let rest = Math.max(0, Number(value || 0));
  const out = [];
  for (const denom of CHIP_DENOMS) {
    const wholeCount = Math.floor((rest + 1e-9) / denom.value);
    if (!wholeCount) continue;
    const visibleCount = Math.min(wholeCount, Math.max(1, maxChips - out.length));
    for (let i = 0; i < visibleCount; i++) out.push(denom.cls);
    rest -= wholeCount * denom.value;
    if (out.length >= maxChips) break;
  }
  if (!out.length && value > 0) out.push("chip-05");
  return out;
}

function visualStackCount(value, compact = false) {
  const n = Math.max(0, Number(value || 0));
  // A wager is one stack whatever it is worth. It sits inches from the player
  // it belongs to, next to a label that already says the number, so spreading
  // it sideways only made it wider -- the height carries the size instead.
  if (compact) return 1;
  if (n < 3) return 1;
  if (n < 12) return 2;
  if (n < 40) return 3;
  if (n < 120) return 4;
  return 5;
}

//: A one-chip ripple across the columns, so the tops of the pot are not dead
//: level. Fixed rather than random: the same pot has to look the same twice.
const POT_LAYER_RIPPLE = [0, 1, -1, 1, 0];

function chipLayers(value, col, compact) {
  // How tall a column stands. It used to be 4 + ((col * 2 + round(n)) % 5),
  // which made a pot of 20 and a pot of 25 look identical while 20 and 21
  // looked nothing alike -- the height said nothing about the money.
  //
  // Growth is logarithmic on purpose: chips are read at a glance, so the step
  // from 5 to 50 should show and the step from 300 to 400 should not.
  const base = 2 + Math.log10(1 + Math.max(0, Number(value || 0))) * 2;
  if (compact) return Math.max(2, Math.min(7, Math.round(base)));
  return Math.max(2, Math.min(6, Math.round(base) + POT_LAYER_RIPPLE[col % POT_LAYER_RIPPLE.length]));
}

function potClusterOffsets(stackCount) {
  const patterns = {
    1: [{ x: 0, y: 10, z: 4 }],
    2: [{ x: -9, y: 12, z: 3 }, { x: 8, y: 10, z: 4 }],
    3: [{ x: -14, y: 13, z: 2 }, { x: 1, y: 4, z: 5 }, { x: 15, y: 11, z: 3 }],
    4: [{ x: -18, y: 15, z: 2 }, { x: -5, y: 8, z: 4 }, { x: 8, y: 4, z: 6 }, { x: 19, y: 12, z: 3 }],
    5: [{ x: -23, y: 16, z: 2 }, { x: -11, y: 10, z: 4 }, { x: 0, y: 2, z: 7 }, { x: 12, y: 8, z: 5 }, { x: 23, y: 14, z: 3 }],
    6: [{ x: -25, y: 17, z: 2 }, { x: -15, y: 12, z: 3 }, { x: -4, y: 6, z: 5 }, { x: 7, y: 2, z: 7 }, { x: 18, y: 9, z: 4 }, { x: 28, y: 15, z: 2 }],
    7: [{ x: -28, y: 18, z: 1 }, { x: -18, y: 13, z: 3 }, { x: -8, y: 8, z: 5 }, { x: 1, y: 1, z: 8 }, { x: 10, y: 6, z: 6 }, { x: 20, y: 11, z: 4 }, { x: 30, y: 17, z: 2 }],
  };
  return patterns[stackCount] || patterns[7];
}

function chipStackHtml(value, compact = false) {
  const n = Number(value || 0);
  if (!(n > 0)) return "";

  // A wager is a single upright stack; the pot is a scattered cluster, laid
  // out by potClusterOffsets. Both used to live in v031, which overrode this
  // function -- so the pot had one implementation here, another in v020 and a
  // third there, and only the last one drew anything.
  const stackCount = compact
    ? 1
    : Math.min(7, Math.max(1, visualStackCount(n, false) + (n >= 8 ? 1 : 0)));
  const palette = chipsForAmount(n, compact ? 8 : 16);
  const fallback = ["chip-1", "chip-25", "chip-5", "chip-100", "chip-05"];
  const offsets = compact ? null : potClusterOffsets(stackCount);
  const columns = [];

  for (let col = 0; col < stackCount; col++) {
    const cls = palette[col % Math.max(1, palette.length)] || fallback[col % fallback.length];
    const chips = Array.from({ length: chipLayers(n, col, compact) }, (_, i) =>
      `<i class="poker-chip ${cls}" style="--i:${i}"></i>`
    ).join("");
    if (offsets) {
      const pos = offsets[col] || { x: 0, y: 0, z: 1 };
      columns.push(
        `<span class="chip-column pot-stack" style="--col:${col};--cols:${stackCount};--stack-x:${pos.x}px;--stack-y:${pos.y}px;--stack-z:${pos.z}">${chips}</span>`
      );
    } else {
      columns.push(`<span class="chip-column" style="--col:${col};--cols:${stackCount}">${chips}</span>`);
    }
  }

  return `<div class="chip-cluster ${compact ? "compact" : "pot-cluster"}">${columns.join("")}</div>`;
}

function renderPotChips(value) {
  const target = $("potChips");
  if (!target) return;
  // Chips already pushed out this street are still on the felt, not in the
  // pot number the server sends, so show them together -- otherwise the
  // cluster shrinks the moment a street ends and grows again on the next.
  let visualValue = Number(value || 0);
  if (game && !game.terminal) {
    const liveWagers = Object.values(game.players || {}).reduce(
      (sum, player) => sum + Math.max(0, Number(player?.street_invested || 0)),
      0
    );
    visualValue = Math.max(visualValue, Number(game.pot || 0) + liveWagers);
  }
  target.innerHTML = chipStackHtml(visualValue, false);
  target.classList.toggle("has-chips", visualValue > 0);
}


function deckPoint() {
  return centerInsideFelt($("deckAnchor")) || potPoint();
}

function setDeckActive(active) {
  $("deckAnchor")?.classList.toggle("active", Boolean(active));
}

function rotateOrderFrom(order, startId) {
  if (!Array.isArray(order) || !order.length) return [];
  const idx = Math.max(0, order.indexOf(startId));
  return order.slice(idx).concat(order.slice(0, idx));
}

function makeFlyingCard(code = "??") {
  const felt = feltNode();
  if (!felt) return null;
  const wrap = document.createElement("div");
  wrap.className = "card-flight";
  const card = cardEl(code);
  card.classList.add("flight-card");
  wrap.appendChild(card);
  felt.appendChild(wrap);
  return wrap;
}

async function flyCard(from, to, options = {}) {
  if (REDUCED_MOTION || !from || !to) return;
  const el = makeFlyingCard(options.code || "??");
  if (!el) return;
  el.style.left = `${from.x}px`;
  el.style.top = `${from.y}px`;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const rot = Number(options.rotate ?? ((dx >= 0 ? 1 : -1) * 7));
  const duration = Number(options.duration || 220);
  const arc = Math.min(42, Math.max(14, Math.hypot(dx, dy) * .08));

  const animation = el.animate([
    { transform: "translate(-50%, -50%) scale(.82) rotate(-3deg)", opacity: .15, offset: 0 },
    { transform: `translate(calc(-50% + ${dx * .52}px), calc(-50% + ${dy * .52 - arc}px)) scale(1.03) rotate(${rot * .45}deg)`, opacity: 1, offset: .55 },
    { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(.98) rotate(${rot}deg)`, opacity: 1, offset: 1 },
  ], {
    duration,
    easing: "cubic-bezier(.18,.74,.24,1)",
    fill: "forwards",
  });
  try { await animation.finished; } catch (_) {}
  el.remove();
}

async function popCard(card) {
  if (!card || REDUCED_MOTION) return;
  const anim = card.animate([
    { transform: "translateY(-3px) scale(.92)", opacity: .2 },
    { transform: "translateY(0) scale(1.035)", opacity: 1, offset: .72 },
    { transform: "translateY(0) scale(1)", opacity: 1 },
  ], { duration: 155, easing: "ease-out" });
  try { await anim.finished; } catch (_) {}
}

async function flipCardElement(el, code) {
  if (!el || !code || code === "??") return;
  const face = cardEl(code);
  if (REDUCED_MOTION) {
    el.className = face.className;
    el.innerHTML = face.innerHTML;
    return;
  }
  el.classList.add("is-flipping");
  const out = el.animate([
    { transform: "rotateY(0deg) scale(1)" },
    { transform: "rotateY(88deg) scale(.97)" },
  ], { duration: 115, easing: "ease-in", fill: "forwards" });
  try { await out.finished; } catch (_) {}
  el.className = `${face.className} is-flipping`;
  el.innerHTML = face.innerHTML;
  const incoming = el.animate([
    { transform: "rotateY(-88deg) scale(.97)" },
    { transform: "rotateY(0deg) scale(1)" },
  ], { duration: 145, easing: "ease-out", fill: "forwards" });
  try { await incoming.finished; } catch (_) {}
  el.classList.remove("is-flipping");
}

async function showStreetSplash(street) {
  const splash = $("streetSplash");
  if (!splash) return;
  const text = STREET_LABELS[street] || String(street || "").toUpperCase();
  splash.textContent = text;
  $("street").textContent = text;
  if (REDUCED_MOTION) return;
  splash.classList.remove("show");
  void splash.offsetWidth;
  splash.classList.add("show");
  await sleep(250);
  splash.classList.remove("show");
  await sleep(60);
}

async function animateInitialDeal(state) {
  if (!state) return;
  const allCards = [...document.querySelectorAll(".player-cards .card")];
  if (REDUCED_MOTION) return;

  animationBusy = true;
  document.body.classList.add("cards-moving");
  setDeckActive(true);
  allCards.forEach(card => card.classList.add("deal-hidden"));

  try {
    const order = rotateOrderFrom(state.seat_order || [], state.small_blind_player || state.seat_order?.[0]);
    const origin = deckPoint();
    for (let round = 0; round < 2; round++) {
      for (const pid of order) {
        const player = state.players?.[pid];
        if (!player) continue;
        const cards = document.querySelectorAll(`.seat[data-seat="${player.seat}"] .player-cards .card`);
        const targetCard = cards[round];
        const target = centerInsideFelt(targetCard) || seatPointForPlayer(state, pid);
        await flyCard(origin, target, { code: "??", duration: 175, rotate: round ? 6 : -6 });
        targetCard?.classList.remove("deal-hidden");
        await popCard(targetCard);
        await sleep(25);
      }
    }
  } finally {
    allCards.forEach(card => card.classList.remove("deal-hidden"));
    setDeckActive(false);
    document.body.classList.remove("cards-moving");
    animationBusy = false;
  }
}

function boardTargetCountForStreet(street) {
  if (street === "flop") return 3;
  if (street === "turn") return 4;
  if (street === "river" || street === "showdown" || street === "complete") return 5;
  return 0;
}

async function revealBoardTo(state, targetCount, streetName = null) {
  if (!state?.board?.length) return;
  const board = $("board");
  if (!board) return;
  const finalCount = Math.min(Number(targetCount || 0), state.board.length);
  let current = board.children.length;
  if (finalCount <= current) return;

  if (streetName) await showStreetSplash(streetName);
  setDeckActive(true);

  const slots = [];
  for (let i = current; i < finalCount; i++) {
    const card = cardEl(state.board[i]);
    card.classList.add("community-hidden");
    board.appendChild(card);
    slots.push({ card, code: state.board[i] });
  }

  const origin = deckPoint();
  for (const { card } of slots) {
    const target = centerInsideFelt(card);
    await flyCard(origin, target, { code: "??", duration: 205, rotate: 4 });
    card.classList.remove("community-hidden");
    await popCard(card);
    await sleep(streetName === "flop" ? 55 : 95);
  }
  setDeckActive(false);
}

async function revealRemainingBoard(previousState, nextState) {
  let count = $("board")?.children?.length || previousState?.board?.length || 0;
  const target = nextState?.board?.length || 0;
  while (count < target) {
    let street = count < 3 ? "flop" : count === 3 ? "turn" : "river";
    const nextCount = Math.min(target, boardTargetCountForStreet(street));
    await revealBoardTo(nextState, nextCount, street);
    count = nextCount;
  }
}

async function animateShowdownReveal(previousState, nextState) {
  if (!nextState?.terminal) return;
  const live = (nextState.seat_order || []).filter(pid => !nextState.players?.[pid]?.folded);
  const bots = live.filter(pid => nextState.players?.[pid]?.is_bot);
  if (!bots.length) return;

  await showStreetSplash("showdown");
  for (const pid of bots) {
    const player = nextState.players[pid];
    const els = document.querySelectorAll(`.seat[data-seat="${player.seat}"] .player-cards .card`);
    for (let i = 0; i < Math.min(2, els.length); i++) {
      await flipCardElement(els[i], player.hole_cards?.[i]);
      await sleep(65);
    }
  }
  await sleep(110);
}



function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function feltNode() {
  return document.querySelector(".felt");
}

function centerInsideFelt(node) {
  const felt = feltNode();
  if (!felt || !node) return null;
  const fr = felt.getBoundingClientRect();
  const r = node.getBoundingClientRect();
  return {
    x: r.left - fr.left + r.width / 2,
    y: r.top - fr.top + r.height / 2,
  };
}

function seatPointForPlayer(state, playerId) {
  const player = state?.players?.[playerId];
  if (!player) return null;
  const seat = document.querySelector(`.seat[data-seat="${player.seat}"]`);
  return centerInsideFelt(seat);
}

function potPoint() {
  return centerInsideFelt($("potChips")) || centerInsideFelt($("pot"));
}

function wagerPointForPlayer(state, playerId) {
  const from = seatPointForPlayer(state, playerId);
  const to = potPoint();
  if (!from || !to) return to || from;
  // Ставка лежит на линии от игрока к банку — как фишки перед игроком на живом столе.
  return {
    x: from.x + (to.x - from.x) * 0.57,
    y: from.y + (to.y - from.y) * 0.57,
  };
}

function makeFlyingPacket(amount, label = "") {
  const felt = feltNode();
  if (!felt) return null;
  const el = document.createElement("div");
  el.className = "chip-flight";
  el.dataset.amount = String(Number(amount || .5));
  el.innerHTML = `${chipStackHtml(Math.max(.5, amount || .5), true)}${label ? `<span>${escapeHtml(label)}</span>` : ""}`;
  felt.appendChild(el);
  return el;
}

async function flyPacket(from, to, amount, options = {}) {
  if (REDUCED_MOTION || !from || !to) return null;
  const duration = Number(options.duration || 260);
  const el = makeFlyingPacket(amount, options.label || "");
  if (!el) return null;

  el.style.left = `${from.x}px`;
  el.style.top = `${from.y}px`;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const arcLift = Math.min(18, Math.max(10, Math.abs(dx) * .08 + Math.abs(dy) * .04));

  // Короткая низкая дуга сохраняет ощущение веса, а финальное сжатие обозначает приземление.
  const animation = el.animate([
    { transform: "translate(-50%, -50%) scale(.86)", opacity: .25, offset: 0 },
    { transform: `translate(calc(-50% + ${dx * .52}px), calc(-50% + ${dy * .52 - arcLift}px)) scale(1.06)`, opacity: 1, offset: .52 },
    { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy - 2}px)) scale(1.04,.92)`, opacity: 1, filter: "brightness(1.28) drop-shadow(0 7px 8px rgba(0,0,0,.42))", offset: .86 },
    { transform: `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(1)`, opacity: 1, filter: "brightness(1) drop-shadow(0 7px 8px rgba(0,0,0,.36))", offset: 1 },
  ], {
    duration: Math.max(250, duration),
    easing: "cubic-bezier(.2,.72,.22,1)",
    fill: "forwards",
  });

  try { await animation.finished; } catch (_) {}
  if (!options.keep) {
    el.animate([{opacity:1}, {opacity:0}], {duration:90, fill:"forwards"});
    await sleep(80);
    el.remove();
    return null;
  }
  el.classList.add("parked");
  el.dataset.owner = options.owner || "";
  return el;
}

async function collectParkedPackets(includeExistingMarkers = false) {
  if (REDUCED_MOTION) return;
  const target = potPoint();
  if (!target) return;

  const moves = [];

  // Фишки, которые прилетели в текущем анимируемом пакете действий.
  for (const el of [...document.querySelectorAll(".chip-flight.parked")]) {
    const from = centerInsideFelt(el);
    const amount = Number(el.dataset.amount || 1);
    if (!from) { el.remove(); continue; }
    el.remove();
    moves.push(flyPacket(from, target, amount, { duration:220 }));
  }

  // Уже лежавшие на столе ставки из предыдущего состояния.
  // Они нужны, когда новое действие закрывает улицу.
  if (includeExistingMarkers) {
    for (const marker of [...document.querySelectorAll(".bet-marker:not(.fx-collected)")]) {
      const from = centerInsideFelt(marker);
      if (!from) continue;
      const text = marker.querySelector("span")?.textContent || "1";
      const amount = Number.parseFloat(text.replace(",", ".")) || 1;
      marker.classList.add("fx-collected");
      moves.push(flyPacket(from, target, amount, { duration:225 }));
    }
  }

  if (!moves.length) return;
  await Promise.all(moves);
  $("potChips")?.classList.add("pot-impact");
  await sleep(90);
  $("potChips")?.classList.remove("pot-impact");
}

function clearAnimationPackets() {
  document.querySelectorAll(".chip-flight").forEach(el => el.remove());
}

async function animateBlindPosts(nextState) {
  if (REDUCED_MOTION || !nextState) return;
  const blindRows = [
    [nextState.small_blind_player, .5],
    [nextState.big_blind_player, 1],
  ].filter(([pid]) => pid && nextState.players?.[pid]);

  for (const [pid, amount] of blindRows) {
    const from = seatPointForPlayer(nextState, pid);
    const to = wagerPointForPlayer(nextState, pid);
    await flyPacket(from, to, amount, { keep:true, owner:pid, label:formatBB(amount), duration:210 });
  }
}

async function animateActionDelta(previousState, nextState, { includeBlinds = false } = {}) {
  if (REDUCED_MOTION || !nextState) return;
  clearAnimationPackets();
  animationBusy = true;
  document.body.classList.add("chips-moving");

  try {
    if (includeBlinds) await animateBlindPosts(nextState);

    // До финального render DOM хранит предыдущее состояние борда.
    // Поэтому новые улицы можно открыть именно в момент, когда завершились ставки.
    const oldCount = includeBlinds ? 0 : Number(previousState?.history?.length || 0);
    const rows = (nextState.history || []).slice(oldCount);

    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      if (Number(row.amount || 0) > 0) {
        const from = seatPointForPlayer(nextState, row.player_id) || seatPointForPlayer(previousState, row.player_id);
        const to = wagerPointForPlayer(nextState, row.player_id) || potPoint();
        await flyPacket(from, to, row.amount, {
          keep:true,
          owner:row.player_id,
          label:formatBB(row.amount),
          duration:235,
        });
      } else {
        // Чек/пас читаются статусом и историей, но оставляем короткую паузу,
        // чтобы последовательность действий ботов не выглядела мгновенной.
        await sleep(85);
      }

      const followingStreet = rows[i + 1]?.street ?? nextState.street;
      if (followingStreet !== row.street || nextState.terminal && i === rows.length - 1) {
        await collectParkedPackets(!includeBlinds);
        if (["flop", "turn", "river"].includes(followingStreet)) {
          await revealBoardTo(nextState, boardTargetCountForStreet(followingStreet), followingStreet);
        }
      }
    }

    // Если новая раздача дошла до первого решения без действий в history,
    // блайнды всё равно должны собраться только после завершения улицы.
    if (includeBlinds && !rows.length) {
      // Оставляем их визуально на линии ставок — финальный render нарисует точные значения.
      await sleep(80);
    }

    if (nextState.terminal) {
      await collectParkedPackets(!includeBlinds);
      await revealRemainingBoard(previousState, nextState);
      await animateShowdownReveal(previousState, nextState);
      await animatePayouts(nextState);
    } else {
      await revealRemainingBoard(previousState, nextState);
    }
  } finally {
    clearAnimationPackets();
    animationBusy = false;
    document.body.classList.remove("chips-moving");
  }
}

async function animatePayouts(state) {
  if (REDUCED_MOTION || !state?.terminal) return;
  const origin = potPoint();
  if (!origin) return;

  const details = Array.isArray(state.result_details) ? state.result_details : [];
  const payouts = [];
  if (details.length) {
    for (const row of details) {
      const winners = row.winners || [];
      if (!winners.length) continue;
      const share = Number(row.amount || 0) / winners.length;
      winners.forEach(pid => payouts.push({ pid, amount: share }));
    }
  } else {
    (state.winners || []).forEach(pid => payouts.push({ pid, amount: 1 }));
  }

  for (const payout of payouts) {
    const target = seatPointForPlayer(state, payout.pid);
    if (!target) continue;
    await flyPacket(origin, target, payout.amount, {
      keep:false,
      label: payout.amount > 1 ? `+${formatBB(payout.amount)}` : "",
      duration:320,
    });
    const seat = document.querySelector(`.seat[data-seat="${state.players[payout.pid]?.seat}"] .seat-card`);
    seat?.classList.add("winner-impact");
    await sleep(70);
    seat?.classList.remove("winner-impact");
  }
}

function formatBB(value) {
  return `${Number(value || 0).toFixed(2)} ББ`;
}

function signedBB(value) {
  const n = Number(value || 0);
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)} ББ`;
}

function displayRank(rank) {
  return rank === "T" ? "10" : rank;
}

function cardEl(code) {
  const el = document.createElement("div");
  if (!code || code === "??") {
    el.className = "card back";
    return el;
  }
  const rank = displayRank(code[0]);
  const suit = code[1];
  const symbol = { s: "♠", h: "♥", d: "♦", c: "♣" }[suit] || suit;
  el.className = "card " + ((suit === "h" || suit === "d") ? "red" : "");
  el.innerHTML = `<span class="card-rank">${rank}</span><span class="card-suit">${symbol}</span>`;
  return el;
}

function renderCards(target, cards) {
  target.innerHTML = "";
  (cards || []).forEach(code => target.appendChild(cardEl(code)));
}

function currentSeatConfig(seatNumber) {
  return tableData?.seats?.find(row => Number(row.seat) === Number(seatNumber)) || null;
}

function gamePlayerForSeat(seatNumber) {
  const fromGame = game ? Object.values(game.players || {}).find(p => Number(p.seat) === Number(seatNumber)) || null : null;
  if (fromGame) return fromGame;
  // A seat sitting out the hand in progress (bought in after it started) has
  // nothing in game.players -- current_seats is where the server puts them
  // instead, and it carries the stack and hole cards this render needs.
  // The server sends it only for that gap, so between hands it is absent and
  // seatHtml falls back to the seat config, which carries the id.
  const row = tableData?.current_seats?.[seatNumber];
  // Carries the seat's real stack: this is what seatHtml prints, so a zero
  // here made every seat sitting out read "0.00 ББ" instead of its chips.
  return row ? { ...row, seat: seatNumber, stack: Number(row.stack || 0), hole_cards: [] } : null;
}

function avatarInitials(name, isBot = false) {
  if (isBot) return "AI";
  const parts = String(name || "Игрок").trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map(x => x[0]?.toUpperCase() || "").join("") || "И";
}

function avatarHue(seat, isBot = false) {
  const base = isBot ? 188 : 286;
  return (base + Number(seat || 0) * 37) % 360;
}

function seatHtml(config, player, offerSeat = true) {
  // Online, an empty seat is how you sit down: the request is queued and the
  // server seats you at the next hand boundary, so a hand in progress is no
  // reason to refuse. Locking these on every network table left six buttons
  // reading "Сесть" that could not be pressed -- and on a table with nobody at
  // it, they were the only thing on screen offering a way in. Offline they
  // still open the bot-seat editor, which a live hand does have to block.
  const locked = ONLINE_TABLE_ID ? false : Boolean(game && !game.terminal);
  if (!config) return "";

  if (!config.active || config.occupant_type === "empty") {
    // Six identical "Сесть" circles round an empty table is the same offer six
    // times over. Online only the seat you would actually be given carries it;
    // the rest of the ring stays a plain empty place. Offline each button is a
    // control for its own seat's bot editor, so they are not the same offer.
    if (ONLINE_TABLE_ID && !offerSeat) return "";
    return `
      <button class="seat-empty ${locked ? "seat-lock" : ""}" data-add-seat="${config.seat}" ${locked ? "disabled" : ""}>
        <span class="empty-avatar">＋</span>
        <strong>Сесть</strong>
      </button>
    `;
  }

  const source = player || config;
  const isHuman = !source.is_bot && (source.profile_id || config.occupant_type === "human");
  const activeTurn = game && !game.terminal && game.acting_player === source.id;
  const folded = Boolean(player?.folded);
  const allIn = Boolean(player?.all_in);
  const position = player?.position || (isHuman ? "ИГРОК" : "БОТ");
  const buttonClass = String(position).includes("BTN") ? "btn-pos" : "";
  const stack = player ? player.stack : config.balance;
  const wager = Number(player?.street_invested || 0);
  const isDealer = String(position).includes("BTN");
  // A human's turn is shown by the seat's own glow (.active-turn) -- the
  // "ХОД" badge on top of it was redundant. Bots keep "ДУМАЕТ": it's the
  // only sign a bot is actually deciding, not just informational chrome.
  const status = folded ? "ПАС" : allIn ? "ALL-IN" : activeTurn && !isHuman ? "ДУМАЕТ" : "";
  const typeClass = isHuman ? "seat-human" : "seat-bot";
  // game is null before a hand exists (waiting/countdown) -- tableData's own
  // copy survives those phases, so a freshly seated player still gets a hero
  // seat and can click ready instead of staying invisible until dealt in.
  const viewerPlayerId = game?.viewer_player_id || tableData?.viewer_player_id;
  const isViewer = Boolean(viewerPlayerId && viewerPlayerId === source.id);
  const telegramProfile = isViewer ? window.Poker8TelegramProfile : null;
  const displayName = telegramProfile?.displayName || source.name || config.name || "Игрок";
  // Avatars are level-based, not photos -- no --profile-avatar-image here.
  // The CSS hook stays (v038) since nothing sets the inline style anymore.
  const avatar = isViewer ? "ВЫ" : avatarInitials(displayName, !isHuman);
  const hue = avatarHue(config.seat, !isHuman);

  return `
    <div class="seat-card ${typeClass} ${isViewer ? "viewer-seat" : ""} ${activeTurn ? "active-turn p8-turn-gradient" : ""} ${folded ? "folded" : ""} ${allIn ? "all-in" : ""}" style="--avatar-hue:${hue}">
      ${!locked ? `<button class="seat-edit" data-edit-seat="${config.seat}" title="Настроить место">•••</button>` : ""}
      ${isDealer ? `<div class="dealer-button" title="Дилер / BTN">D</div>` : ""}
      <div class="avatar-wrap">
        <div class="player-avatar"><span>${escapeHtml(avatar)}</span></div>
        ${status ? `<div class="player-status ${folded ? "status-fold" : allIn ? "status-allin" : activeTurn && !isHuman ? "status-thinking" : "status-turn"}">${status}${activeTurn && !isHuman ? `<i class="thinking-dots"><b></b><b></b><b></b></i>` : ""}</div>` : ""}
      </div>
      <div class="seat-identity">
        <div class="seat-topline">
          <div class="seat-name">${escapeHtml(displayName)}</div>
          <div class="position-chip ${buttonClass}">${escapeHtml(position)}</div>
        </div>
        <div class="seat-stack">${allIn ? "ALL-IN" : formatBB(stack)}</div>
        <div class="bot-level">${isHuman ? "ИГРОК" : DIFFICULTY_LABELS[source.difficulty || config.difficulty] || "БОТ"}</div>
      </div>
      <div class="player-cards" data-cards-seat="${config.seat}"></div>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderWagerMarkers() {
  const layer = $("wagerLayer");
  if (!layer) return;
  layer.innerHTML = "";
  if (!game || game.terminal) return;

  for (const player of Object.values(game.players || {})) {
    const wager = Number(player.street_invested || 0);
    if (!(wager > 0)) continue;
    const point = wagerPointForPlayer(game, player.id);
    if (!point) continue;

    const marker = document.createElement("div");
    marker.className = "bet-marker";
    marker.dataset.playerId = player.id;
    marker.style.left = `${point.x}px`;
    marker.style.top = `${point.y}px`;
    marker.innerHTML = `${chipStackHtml(wager, true)}<span>${formatBB(wager)}</span>`;
    layer.appendChild(marker);
  }
}

//: Post-render hooks. Four layers used to reassign renderSeats, each wrapping
//: the one before, so calling it walked a five-deep chain that only worked if
//: every link remembered to call its predecessor -- and one throw anywhere in
//: it silently cost every layer after. Layers register here instead. The order
//: is the order they load, which is what it always was.
const renderHooks = { seats: [], mobileHeader: [] };

function onRendered(phase, fn) {
  if (typeof fn === "function") renderHooks[phase]?.push(fn);
}

function runRenderHooks(phase) {
  for (const fn of renderHooks[phase] || []) {
    // One layer's decoration failing must not cost every layer after it.
    try { fn(); } catch (error) { console.error(`render hook (${phase}) failed`, error); }
  }
}

function renderSeats() {
  if (!tableData) return;
  const offeredSeat = tableData.seats.find(
    config => !config.active || config.occupant_type === "empty",
  )?.seat;
  tableData.seats.forEach(config => {
    const target = document.querySelector(`.seat[data-seat="${config.seat}"]`);
    if (!target) return;
    const player = gamePlayerForSeat(config.seat);
    target.innerHTML = seatHtml(config, player, config.seat === offeredSeat);
    const cardsTarget = target.querySelector(`[data-cards-seat="${config.seat}"]`);
    if (cardsTarget && player) {
      renderCards(cardsTarget, player.hole_cards || ["??", "??"]);
    }
  });

  window.syncComponentSeatLayout?.(game, tableData);
  renderWagerMarkers();

  // Online the seat flow is a buy-in against the server, and online-table.js
  // owns it through a listener delegated on the document -- the mobile layers
  // rebuild this markup on every snapshot, and a handler bound to the element
  // dies with the node it was bound to. Offline the button edits its own seat,
  // and nothing replaces the node underneath it.
  if (!ONLINE_TABLE_ID) {
    document.querySelectorAll("[data-add-seat]").forEach(btn => {
      btn.onclick = () => openSeatModal(Number(btn.dataset.addSeat));
    });
  }
  document.querySelectorAll("[data-edit-seat]").forEach(btn => {
    btn.onclick = () => openSeatModal(Number(btn.dataset.editSeat));
  });

  const active = tableData.seats.filter(s => s.active).length;
  $("activeCount").textContent = String(active);
  runRenderHooks("seats");
}

function renderProfile(profile) {
  if (!profile) return;
  $("heroBankroll").textContent = formatBB(profile.hero_balance ?? profile.balance);
  $("savedHands").textContent = String(profile.hands || 0);
  $("vpipStat").textContent = `${Number(profile.vpip || 0).toFixed(1)}%`;
  $("pfrStat").textContent = `${Number(profile.pfr || 0).toFixed(1)}%`;
  $("threeBetStat").textContent = `${Number(profile.three_bet || 0).toFixed(1)}%`;
  $("fold3Stat").textContent = `${Number(profile.fold_to_3bet || 0).toFixed(1)}%`;
  $("aggressionStat").textContent = Number(profile.postflop_aggression || 0).toFixed(2);
  $("evLossStat").textContent = `${Number(profile.avg_ev_loss_bb || 0).toFixed(3)} ББ`;

  const model = profile.model || {};
  const confidence = Number(model.confidence_pct || 0);
  $("modelConfidence").textContent = `${confidence.toFixed(0)}%`;
  $("modelConfidenceBar").style.width = `${Math.max(0, Math.min(100, confidence))}%`;

  const traits = Array.isArray(model.traits) ? model.traits : [];
  if (!traits.length) {
    $("modelTraits").innerHTML = `<div class="model-empty">${profile.hands ? "Модель собирается. Для устойчивых тенденций нужно больше рук." : "Сыграйте первые раздачи — модель начнёт собираться автоматически."}</div>`;
  } else {
    $("modelTraits").innerHTML = traits.map(t => `
      <div class="model-trait">
        <div><strong>${escapeHtml(t.label)}</strong><span>${escapeHtml(t.detail)}</span></div>
        <i style="--strength:${Math.round(Number(t.strength || 0) * 100)}%"></i>
      </div>`).join("");
  }

  const select = $("profileSelect");
  if (select && tableData?.profiles) {
    const currentValue = profile.id || tableData.active_profile_id;
    select.innerHTML = "";
    tableData.profiles.forEach(row => {
      const option = document.createElement("option");
      option.value = row.id;
      option.textContent = `${row.name} · ${Number(row.balance).toFixed(2)} ББ · ${row.hands || 0} рук`;
      option.selected = row.id === currentValue;
      select.appendChild(option);
    });
    const locked = Boolean(tableData.locked);
    select.disabled = locked;
    $("newProfile").disabled = locked;
    $("renameProfile").disabled = locked;
  }
}

function tableHasHumans() {
  if (game && typeof game.human_count === "number") return game.human_count > 0;
  return Boolean(tableData?.seats?.some(s => s.active && s.occupant_type === "human"));
}

function spectatorOnly() {
  if (game && typeof game.spectator_only === "boolean") return game.spectator_only;
  return Boolean(tableData?.spectator_only);
}

function clearAutomationTimer() {
  if (automationTimer) clearTimeout(automationTimer);
  automationTimer = null;
}

function cooldownRemainingSeconds(row) {
  const target = Date.parse(row?.return_at || "");
  if (!Number.isFinite(target)) return Number(row?.remaining_seconds || 0);
  return Math.max(0, Math.ceil((target - Date.now()) / 1000));
}

function formatCooldown(seconds) {
  seconds = Math.max(0, Number(seconds || 0));
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function renderCooldowns() {
  const select = $("botCooldownSelect");
  if (select && tableData) {
    select.value = String(tableData.bot_bust_cooldown_minutes || 10);
    select.disabled = Boolean(tableData.locked);
  }
  const target = $("botCooldownList");
  if (!target) return;
  const rows = tableData?.bot_cooldowns || [];
  if (!rows.length) {
    target.innerHTML = "<span>Никого</span>";
    return;
  }
  target.innerHTML = rows.map(row => {
    const seconds = cooldownRemainingSeconds(row);
    const state = seconds > 0 ? `вернётся через ${formatCooldown(seconds)}` : "ждёт свободное место";
    return `<div class="cooldown-row"><strong>${escapeHtml(row.name)}</strong><span>${state}</span></div>`;
  }).join("");
}

function nextCooldownDelay() {
  const rows = tableData?.bot_cooldowns || [];
  if (!rows.length) return null;
  const seconds = Math.min(...rows.map(cooldownRemainingSeconds));
  return Math.max(500, Math.min(30000, seconds * 1000 + 250));
}

function scheduleCooldownRetry() {
  const delay = nextCooldownDelay();
  if (delay == null) return false;
  clearAutomationTimer();
  autoSessionActive = true;
  automationTimer = setTimeout(async () => {
    await loadTable(false);
    const active = tableData?.seats?.filter(s => s.active).length || 0;
    if (active >= 2) newHand(true);
    else if (infiniteMode) scheduleCooldownRetry();
  }, delay);
  return true;
}

async function setBotCooldown(minutes) {
  if (tableData?.locked) {
    renderCooldowns();
    alert("Тайм-аут ботов можно менять только между раздачами");
    return;
  }
  const res = await fetch("/api/table/bot-cooldown", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ minutes: Number(minutes) }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось изменить тайм-аут");
    return;
  }
  await loadTable(true);
}

function activeBotPlayer() {
  if (!game || game.terminal || !game.acting_player) return null;
  const actor = game.players?.[game.acting_player];
  return actor?.is_bot ? actor : null;
}

function botThinkDelay(player = activeBotPlayer()) {
  const range = BOT_SPEED_RANGES[botSpeedMode] || BOT_SPEED_RANGES.normal;
  let [lo, hi] = range;
  const difficultyFactor = { easy: .84, normal: 1, hard: 1.12, maximum: 1.25 }[player?.difficulty] || 1;
  const streetFactor = { preflop: .88, flop: 1, turn: 1.10, river: 1.22 }[game?.street] || 1;
  const jitter = lo + Math.random() * Math.max(1, hi - lo);
  return Math.round(jitter * difficultyFactor * streetFactor);
}

function setBotSpeed(mode) {
  if (!BOT_SPEED_RANGES[mode]) mode = "normal";
  botSpeedMode = mode;
  localStorage.setItem("pokerTrainerBotSpeed", mode);
  renderRunControls();
  if (activeBotPlayer() && autoSessionActive && !animationBusy) queueAutomation();
}

function renderRunControls() {
  renderCooldowns();
  const speed = $("botSpeedSelect");
  if (speed) speed.value = botSpeedMode;
  const infinite = $("infiniteMode");
  if (infinite) {
    infinite.textContent = infiniteMode ? "∞ Бесконечный: вкл" : "∞ Бесконечный: выкл";
    infinite.classList.toggle("mode-active", infiniteMode);
  }
  const pause = $("spectatorPause");
  const showPause = Boolean(game && !game.terminal && spectatorOnly());
  if (pause) {
    pause.hidden = !showPause;
    pause.textContent = spectatorPaused ? "▶ Продолжить" : "⏸ Пауза";
    pause.classList.toggle("spectator-paused", spectatorPaused);
  }
  document.body.classList.toggle("spectator-mode", Boolean(game && spectatorOnly()));
}

function queueAutomation(delay = null) {
  clearAutomationTimer();
  if (!autoSessionActive || animationBusy) return;

  const actor = activeBotPlayer();
  if (game && !game.terminal && actor) {
    if (spectatorOnly() && spectatorPaused) return;
    const wait = delay == null ? botThinkDelay(actor) : delay;
    automationTimer = setTimeout(() => botStepOnce(), Math.max(120, wait));
    return;
  }

  if (game?.terminal && infiniteMode) {
    automationTimer = setTimeout(() => newHand(true), NEXT_HAND_DELAY);
  }
}

function setInfiniteMode(value) {
  infiniteMode = Boolean(value);
  localStorage.setItem("pokerTrainerInfiniteMode", infiniteMode ? "1" : "0");
  renderRunControls();
  if (infiniteMode && game?.terminal && autoSessionActive) queueAutomation(350);
  if (!infiniteMode && game?.terminal) clearAutomationTimer();
}

function toggleSpectatorPause() {
  spectatorPaused = !spectatorPaused;
  renderRunControls();
  if (!spectatorPaused) queueAutomation();
  else clearAutomationTimer();
}

async function botStepOnce() {
  const actor = activeBotPlayer();
  if (!game || game.terminal || !actor || animationBusy) return;
  if (spectatorOnly() && spectatorPaused) return;
  clearAutomationTimer();
  const currentId = game.hand_id;
  const res = await fetch(`/api/game/${encodeURIComponent(currentId)}/bot-step`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    if (spectatorOnly()) spectatorPaused = true;
    renderRunControls();
    alert(data.detail || "Не удалось выполнить ход бота");
    return;
  }
  const previousGame = game;
  await animateActionDelta(previousGame, data);
  game = data;
  if (game.terminal) await loadTable(false);
  renderGame();
  queueAutomation();
}


function amountBounds() {
  const player = localViewerPlayer();
  if (!game || !player) return { min: 1, max: 100, value: 1 };
  const max = Math.max(1, Number(player.street_invested || 0) + Number(player.stack || 0));
  let min = 1;
  if (isLocalHumanTurn()) {
    if (Number(game.human_to_call || 0) > 0) min = Math.max(Number(game.human_min_raise_to || 0), Number(game.current_bet || 0) + Number(game.min_raise_size || 1));
    else min = Math.min(max, 1);
  } else {
    const estimated = Math.max(1, Number(game.current_bet || 0) + Math.max(1, Number(game.min_raise_size || 1)));
    min = Math.min(max, estimated);
  }
  if (!Number.isFinite(min) || min <= 0) min = 1;
  if (min > max) min = max;
  const current = Number($("amount")?.value || min);
  const value = Math.min(max, Math.max(min, current));
  return { min, max, value };
}

function syncAmountControls(preferred = null) {
  const input = $("amount");
  const slider = $("amountSlider");
  if (!input || !slider) return;
  const bounds = amountBounds();
  slider.min = String(bounds.min);
  slider.max = String(bounds.max);
  slider.step = "0.5";
  const raw = preferred == null ? Number(input.value || bounds.value) : Number(preferred);
  const value = Math.min(bounds.max, Math.max(bounds.min, Number.isFinite(raw) ? raw : bounds.value));
  input.min = String(bounds.min);
  input.max = String(bounds.max);
  input.value = value.toFixed(2).replace(/\.00$/, "");
  slider.value = String(value);
  slider.style.setProperty("--range-progress", `${bounds.max > bounds.min ? ((value - bounds.min) / (bounds.max - bounds.min)) * 100 : 100}%`);
  if (pendingAction?.kind === "aggressive") {
    pendingAction.amount = value;
    renderQueuedActionStatus();
  }
  const minLabel = $("sliderMinLabel");
  const maxLabel = $("sliderMaxLabel");
  if (minLabel) minLabel.textContent = `МИН ${formatBB(bounds.min)}`;
  if (maxLabel) maxLabel.textContent = `МАКС ${formatBB(bounds.max)}`;
  refreshQuickSizeLabels();
  renderPersistentActionButtons();
}


function actionButtonLabel(action, localTurn = false) {
  const localPlayer = localViewerPlayer();
  const amount = Number($("amount")?.value || 0);
  if (action === "call") {
    const toCall = localTurn
      ? Number(game?.human_to_call || 0)
      : Math.max(0, Number(game?.current_bet || 0) - Number(localPlayer?.street_invested || 0));
    return toCall > 0 ? `КОЛЛ\n${formatBB(toCall)}` : "КОЛЛ";
  }
  if (action === "bet") return `СТАВКА\n${formatBB(amount)}`;
  if (action === "raise") return `РЕЙЗ\n${formatBB(amount)}`;
  if (action === "aggressive") return `${Number(game?.current_bet || 0) > Number(localPlayer?.street_invested || 0) ? "РЕЙЗ" : "СТАВКА"}\n${formatBB(amount)}`;
  if (action === "all_in") {
    const total = Number(localPlayer?.stack || 0) + Number(localPlayer?.street_invested || 0);
    return `ALL-IN\n${formatBB(total)}`;
  }
  return String(ACTION_LABELS[action] || action).toUpperCase();
}

function refreshActionButtonLabels() {
  document.querySelectorAll('#actionButtons button[data-action-key]').forEach(btn => {
    const key = btn.dataset.actionKey;
    btn.textContent = actionButtonLabel(key, isLocalHumanTurn());
  });
}


function estimatedLocalToCall() {
  const player = localViewerPlayer();
  if (!game || !player) return 0;
  return isLocalHumanTurn()
    ? Number(game.human_to_call || 0)
    : Math.max(0, Number(game.current_bet || 0) - Number(player.street_invested || 0));
}

function mobileStreetIndex() {
  return { preflop: 0, flop: 1, turn: 2, river: 3, showdown: 3, complete: 3 }[game?.street] ?? -1;
}

function renderMobileHeader() {
  const label = $("mobileStreetLabel");
  const dots = $("mobileStreetDots");
  if (label) label.textContent = game ? (STREET_LABELS[game.street] || String(game.street).toUpperCase()) : "СТОЛ";
  const idx = mobileStreetIndex();
  dots?.querySelectorAll("i").forEach((dot, i) => {
    dot.classList.toggle("done", idx >= 0 && i < idx);
    dot.classList.toggle("active", i === idx);
  });
  const primary = $("mobilePrimaryAction");
  if (primary) {
    const active = Boolean(game && !game.terminal);
    primary.textContent = active ? "Прервать раздачу" : "Новая раздача";
    primary.classList.toggle("abort", active);
    const activeSeats = tableData?.seats?.filter(s => s.active).length || 0;
    primary.disabled = !active && activeSeats < 2;
  }
  runRenderHooks("mobileHeader");
}

function selectedActionParts() {
  if (!pendingAction) return { label: "—", amount: "" };
  if (pendingAction.kind === "fold") return { label: "ПАС", amount: "" };
  if (pendingAction.kind === "check") return { label: "ЧЕК", amount: "" };
  if (pendingAction.kind === "call") return { label: "КОЛЛ", amount: formatBB(pendingAction.estimateToCall || 0) };
  if (pendingAction.kind === "all_in") return { label: "ALL-IN", amount: "" };
  if (pendingAction.kind === "aggressive") return { label: Number(game?.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "РЕЙЗ" : "СТАВКА", amount: formatBB(pendingAction.amount || 0) };
  return { label: "—", amount: "" };
}

function renderMobileSelectedCard() {
  const parts = selectedActionParts();
  const action = $("mobileSelectedAction");
  const amount = $("mobileSelectedAmount");
  if (action) action.textContent = pendingInvalidReason ? "ОТМЕНЕНО" : parts.label;
  if (amount) amount.textContent = pendingInvalidReason ? "условия изменились" : parts.amount;
  $("mobileSelectedCard")?.classList.toggle("empty", !pendingAction && !pendingInvalidReason);
  $("mobileSelectedCard")?.classList.toggle("invalid", Boolean(pendingInvalidReason));

  const autoBar = $("mobileAutoActionBar");
  const autoTitle = $("mobileAutoActionTitle");
  const autoText = $("mobileAutoActionText");
  if (autoBar) {
    autoBar.classList.toggle("active", Boolean(pendingAction && !pendingInvalidReason));
    autoBar.classList.toggle("invalid", Boolean(pendingInvalidReason));
  }
  if (autoTitle) {
    autoTitle.textContent = pendingInvalidReason
      ? "Авто-действие отменено"
      : pendingAction
        ? `Авто-действие: ${parts.label}${parts.amount ? ` ${parts.amount}` : ""}`
        : "Авто-действие: не выбрано";
  }
  if (autoText) {
    autoText.textContent = pendingInvalidReason
      ? "Ситуация за столом изменилась — выберите действие заново."
      : pendingAction
        ? "Будет выполнено автоматически, когда ход дойдёт до вас."
        : "Выберите действие заранее — оно выполнится, когда ход дойдёт до вас.";
  }
}

function presetTarget(fraction) {
  if (!game) return 0;
  const bounds = amountBounds();
  let target;
  if (estimatedLocalToCall() > 0) target = Number(game.current_bet || 0) + Number(game.pot || 0) * fraction;
  else target = Math.max(1, Number(game.pot || 0) * fraction);
  return Math.min(bounds.max, Math.max(bounds.min, target));
}

function refreshQuickSizeLabels() {
  document.querySelectorAll("[data-sizing]").forEach(btn => {
    const f = Number(btn.dataset.sizing || 0);
    const base = f === 1 ? "БАНК" : f === .75 ? "¾" : f === .5 ? "½" : "⅓";
    const value = game ? presetTarget(f) : 0;
    btn.innerHTML = `<strong>${base}</strong>${game ? `<small>${formatBB(value)}</small>` : ""}`;
  });
}

function renderPersistentActionButtons() {
  const buttons = $("actionButtons");
  if (!buttons) return;
  if (window.matchMedia?.("(max-width: 780px)")?.matches && buttons.dataset.v038ReferenceActions === "1") return;
  buttons.innerHTML = "";
  const alive = localPlayerAlive();
  const localTurn = isLocalHumanTurn();
  const legal = game?.human_legal_actions || [];
  const toCall = estimatedLocalToCall();
  const leftKey = localTurn ? (legal.includes("check") ? "check" : "fold") : (toCall > 0 ? "fold" : "check");
  const aggressiveName = Number(game?.current_bet || 0) > Number(localViewerPlayer()?.street_invested || 0) ? "РЕЙЗ" : "СТАВКА";
  const amount = Number($("amount")?.value || amountBounds().value || 0);
  const allInTotal = Number(localViewerPlayer()?.stack || 0) + Number(localViewerPlayer()?.street_invested || 0);
  const defs = [
    { slot:"left", key:leftKey, label:leftKey === "check" ? "ЧЕК" : "ПАС", cls:leftKey === "fold" ? "fold" : "check" },
    { slot:"call", key:"call", label:`КОЛЛ${toCall > 0 ? `\n${formatBB(toCall)}` : ""}`, cls:"call" },
    { slot:"aggressive", key:"aggressive", label:`${aggressiveName}\n${formatBB(amount)}`, cls:"raise" },
    { slot:"all_in", key:"all_in", label:`ALL-IN\n${formatBB(allInTotal)}`, cls:"all-in" },
  ];

  defs.forEach(def => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.actionKey = def.key;
    b.dataset.actionSlot = def.slot;
    b.className = `action-slot ${def.cls}`;
    b.textContent = def.label;
    b.classList.toggle("queued", pendingAction?.kind === def.key);
    let enabled = Boolean(game && !game.terminal && alive);
    if (localTurn) {
      if (def.key === "check") enabled = legal.includes("check");
      else if (def.key === "fold") enabled = legal.includes("fold") || legal.includes("check");
      else if (def.key === "call") enabled = legal.includes("call");
      else if (def.key === "aggressive") enabled = legal.includes("bet") || legal.includes("raise");
      else if (def.key === "all_in") enabled = legal.includes("all_in");
    } else if (def.key === "call") {
      enabled = enabled && toCall > 0;
    }
    b.disabled = !enabled;
    b.onclick = () => {
      if (!game || game.terminal || !localPlayerAlive() || window.Poker8Transport?.isActionPending?.()) return;
      const liveTurn = isLocalHumanTurn();
      const liveLegal = game.human_legal_actions || [];
      const liveToCall = estimatedLocalToCall();
      const liveKey = def.slot === "left"
        ? (liveTurn ? (liveLegal.includes("check") ? "check" : "fold") : (liveToCall > 0 ? "fold" : "check"))
        : def.slot;
      // Snapshot мог измениться между отрисовкой и кликом: сначала синхронизировать UI, не выполнять другую команду.
      if (b.dataset.actionKey !== liveKey) {
        renderPersistentActionButtons();
        renderMobileSelectedCard();
        return;
      }
      if (!liveTurn) {
        togglePendingAction(liveKey);
        renderPersistentActionButtons();
        renderMobileSelectedCard();
        return;
      }
      clearPendingAction(false);
      if (liveKey === "check") return sendAction("check", 0);
      if (liveKey === "fold") return sendAction("fold", 0);
      if (liveKey === "call") return sendAction("call", 0);
      if (liveKey === "all_in") return sendAction("all_in", 0);
      const act = liveLegal.includes("raise") ? "raise" : "bet";
      return sendAction(act, Number($("amount")?.value || 0));
    };
    buttons.appendChild(b);
  });
}

function renderMobileHud() {
  renderMobileHeader();
  renderMobileSelectedCard();
  refreshQuickSizeLabels();
}


function renderGame() {
  renderSeats();
  renderMobileHud();
  document.body.dataset.street = game?.street || "idle";
  // Nothing has been wagered before a hand exists -- a "0.00 ББ" pot readout
  // was just clutter on an empty table.
  document.body.classList.toggle("p8-no-pot", !game);
  document.body.classList.toggle("human-turn", Boolean(game && !game.terminal && game.acting_human_player_id));
  document.body.classList.toggle("local-human-turn", isLocalHumanTurn());
  document.body.classList.toggle("local-player-active", localPlayerAlive());
  document.body.classList.toggle("bot-thinking", Boolean(activeBotPlayer()));
  window.syncComponentUi?.(game, tableData);

  if (!game) {
    $("street").textContent = "СТОЛ ГОТОВ";
    $("pot").textContent = "0.00 ББ";
    renderPotChips(0);
    renderCards($("board"), []);
    $("result").textContent = "Посадите людей или ботов и начните раздачу";
    $("turnTitle").textContent = spectatorOnly() ? "Стол наблюдения готов" : "Стол не запущен";
    $("actionPanelKicker").textContent = spectatorOnly() ? "НАБЛЮДЕНИЕ" : activeBotPlayer() ? "БОТ ДУМАЕТ" : "ВАШ ХОД";
    $("hint").textContent = spectatorOnly()
      ? "Стол может работать без людей. Нажмите «Новая раздача» — боты будут ходить по одному, чтобы вы видели игру."
      : "За столом могут одновременно играть несколько профилей людей и боты.";
    renderPersistentActionButtons();
    $("sizingWrap").hidden = false;
    syncAmountControls(1);
    $("newHand").disabled = (tableData?.seats?.filter(s => s.active).length || 0) < 2;
    $("analysisLink").classList.add("disabled");
    stopActionTimer();
    clearPendingAction(false);
    renderQueuedActionStatus();
    renderHistory();
    renderSolverPanel();
    renderRunControls();
    renderMobileHud();
    return;
  }

  $("street").textContent = STREET_LABELS[game.street] || game.street.toUpperCase();
  $("pot").textContent = formatBB(game.pot);
  renderPotChips(game.pot);
  renderCards($("board"), game.board);
  $("result").textContent = game.result_text || "";
  $("analysisLink").href = `/api/game/${game.hand_id}/analysis`;
  $("analysisLink").classList.remove("disabled");
  renderProfile(game.training_profile);
  $("actionPanelKicker").textContent = spectatorOnly() ? "НАБЛЮДЕНИЕ" : activeBotPlayer() ? "БОТ ДУМАЕТ" : "ВАШ ХОД";

  if (game.terminal) {
    $("turnTitle").textContent = "Раздача завершена";
    const busted = game.busted_bots || [];
    $("hint").textContent = busted.length
      ? `${busted.map(x => x.name).join(", ")} покинул(и) рум после потери депозита. Их места уже свободны.`
      : "Можно изменить состав стола или начать следующую раздачу.";
  } else if (game.acting_human_player_id) {
    const who = game.acting_human_name || game.players?.[game.acting_human_player_id]?.name || "Игрок";
    $("turnTitle").textContent = `Ход: ${who}`;
    if (game.human_to_call > 0) {
      $("hint").innerHTML = game.persistent_hole_cards
        ? `<strong>${escapeHtml(who)}</strong>, ваши карты остаются открыты всю раздачу. Для колла ${formatBB(game.human_to_call)}${game.human_min_raise_to ? ` · минимальный рейз до ${formatBB(game.human_min_raise_to)}` : ""}`
        : `<strong>${escapeHtml(who)}</strong>, ваши карты открыты в режиме hot-seat на вашем ходе. Для колла ${formatBB(game.human_to_call)}${game.human_min_raise_to ? ` · минимальный рейз до ${formatBB(game.human_min_raise_to)}` : ""}`;
    } else {
      $("hint").innerHTML = `<strong>${escapeHtml(who)}</strong>, ваши карты открыты. Выберите действие.`;
    }
  } else {
    const actor = game.players[game.acting_player];
    $("turnTitle").textContent = actor ? `Ход: ${actor.name}` : "Ход соперника";
    if (spectatorOnly()) {
      $("hint").textContent = spectatorPaused
        ? "Наблюдение на паузе. Нажмите «Продолжить», чтобы боты продолжили раздачу."
        : "Режим наблюдения: боты играют автоматически, по одному действию за шаг.";
    } else {
      $("hint").textContent = "Бот думает над решением… темп можно изменить в настройках стола.";
    }
  }


renderPersistentActionButtons();
$("sizingWrap").hidden = false;
if (localPlayerAlive()) syncAmountControls(isLocalHumanTurn() && game.human_min_raise_to ? game.human_min_raise_to : null);
renderQueuedActionStatus();
updateActionTimerState();
renderMobileHud();

  renderHistory();
  renderSolverPanel();
  renderRunControls();
  queueMicrotask(() => { maybeAutoFirePendingAction(); });
}

window.Poker8LegacyView = {
  renderSnapshot({ table, state, viewerState }) {
    const players = Object.values(state?.players || {});
    // Between hands (waiting for ready-up, countdown) state.players still
    // only lists whoever played the last hand -- a freshly bought-in seat
    // has nothing there yet. current_seats is sourced from the actual seating
    // instead, so a fresh seat still gets an avatar to render and click ready
    // on, rather than staying invisible until the hand that finally deals
    // them in.
    const currentSeatFor = seatNo => {
      const row = state?.current_seats?.[seatNo];
      // The seat's own stack, not 0 -- this is what every seat renders from
      // between hands, so hardcoding 0 made the whole table read "0" until
      // the next deal put everyone back into state.players.
      return row ? { ...row, seat: seatNo, stack: Number(row.stack || 0), hole_cards: [] } : null;
    };
    const playerAtSeat = seatNo => players.find(row => Number(row.seat) === seatNo) || currentSeatFor(seatNo);
    const viewer = state?.viewer_player_id
      ? players.find(player => player.id === state.viewer_player_id)
        || Object.keys(state?.current_seats || {}).map(Number).map(currentSeatFor).find(row => row?.id === state.viewer_player_id)
        || null
      : window.Poker8OnlineTable
        ? null
        : players.find(player => !player.is_bot && (player.hole_cards || []).some(card => card && card !== "??")) || null;
    const seats = Array.from({ length: 6 }, (_, seat) => {
      const player = playerAtSeat(seat);
      return {
        seat,
        active: Boolean(player),
        // The participant id, so a seat can still be recognised as the
        // viewer's between hands. `game` is null then, and the server omits
        // current_seats for anyone who played the last hand -- leaving this
        // out meant nothing tied a seat to a player, so seatHtml marked no
        // seat as the viewer's, v040 found no hero seat and rotated the
        // table into spectator layout with an unclickable avatar.
        id: player?.id || null,
        occupant_type: player?.is_bot ? "bot" : "human",
        profile_id: player?.profile_id || null,
        name: player?.name || `Место ${seat + 1}`,
        balance: Number(player?.stack || 0),
        difficulty: player?.difficulty || "normal",
      };
    });
    const phase = state?.phase || "waiting";
    const live = phase === "active" || phase === "result";
    const actor = state?.players?.[state?.acting_player];
    const onlineGame = live && state ? {
      ...state,
      viewer_player_id: viewer?.id || null,
      active_profile_id: viewer?.profile_id || null,
      acting_human_player_id: actor && !actor.is_bot ? state.acting_player : null,
      acting_human_profile_id: actor && !actor.is_bot ? actor.profile_id : null,
      acting_human_name: actor && !actor.is_bot ? actor.name : null,
      human_legal_actions: viewer?.id === state.acting_player ? (state.legal_actions || []) : [],
      human_to_call: viewer?.id === state.acting_player
        ? Math.max(0, Number(state.current_bet || 0) - Number(viewer.street_invested || 0))
        : 0,
      human_min_raise_to: viewer?.id === state.acting_player
        ? Number(state.current_bet || 0) + Number(state.min_raise_size || 1)
        : 0,
      player_count: players.length,
      human_count: players.filter(player => !player.is_bot).length,
      spectator_only: viewerState !== "seated",
    } : null;
    tableData = {
      ...(tableData || {}),
      id: table?.id,
      name: table?.name,
      seats,
      locked: live,
      active_profile_id: viewer?.profile_id || null,
      spectator_only: viewerState !== "seated",
      profile: null,
      profiles: [],
      // Same reason as ready_seats below: needed to know which seat is "you"
      // before a hand exists to identify it via game.viewer_player_id.
      viewer_player_id: viewer?.id || null,
      // Ready-up is a pre-hand affordance, so it has to survive on tableData
      // (set every phase) rather than on `game`, which is null exactly then.
      ready_seats: state?.ready_seats || [],
      hand_starts_at: state?.hand_starts_at || null,
      // gamePlayerForSeat falls back to this for a seat sitting out the
      // current hand -- current_seats itself is only a local in this
      // function, so it has to be persisted here to still be reachable from
      // renderSeats(), which runs later off the module-level game/tableData.
      current_seats: state?.current_seats || null,
    };
    game = onlineGame;
    renderGame();
  },
};

function renderHistory() {
  const target = $("history");
  target.innerHTML = "";
  if (!game || !game.history?.length) {
    target.innerHTML = '<div class="empty-state">Начните раздачу — все действия появятся здесь.</div>';
    return;
  }
  game.history.forEach(row => {
    const player = game.players[row.player_id];
    const el = document.createElement("div");
    el.className = "history-row";
    const amount = row.amount > 0 ? ` · ${formatBB(row.amount)}` : "";
    el.innerHTML = `
      <div class="history-street">${STREET_LABELS[row.street] || row.street}</div>
      <div class="history-player ${player && !player.is_bot ? "hero" : ""}">${escapeHtml(player?.name || row.player_id)}</div>
      <div class="history-action">${ACTION_LABELS[row.action] || row.action}${amount}</div>
      <div class="history-pot">банк ${formatBB(row.pot_after)}</div>
    `;
    target.appendChild(el);
  });
  target.scrollTop = target.scrollHeight;
}

function gradeClass(loss) {
  if (loss < 0.06) return "";
  if (loss < 0.9) return "mid";
  return "bad";
}

function renderSolverData(result, review = null) {
  $("solverEmpty").hidden = true;
  $("solverResult").hidden = false;
  if (review) {
    const loss = Number(review.ev_loss_bb || 0);
    $("solverSummary").innerHTML = `
      <div class="review-card">
        <div class="review-grade ${gradeClass(loss)}">${escapeHtml(review.grade)}</div>
        <div class="review-meta">
          Вы: <strong>${escapeHtml(review.chosen.label)}</strong> · EV ${signedBB(review.chosen.ev_bb)}<br>
          Лучшее: <strong>${escapeHtml(review.best.label)}</strong> · EV ${signedBB(review.best.ev_bb)}<br>
          Потеря: <strong>${loss.toFixed(3)} ББ EV</strong>
        </div>
      </div>`;
  } else {
    $("solverSummary").innerHTML = `
      <div class="review-card">
        <div class="review-grade">Heads-up подсказка</div>
        <div class="review-meta">Итераций: <strong>${result.iterations}</strong></div>
      </div>`;
  }

  $("solverActions").innerHTML = "";
  (result.actions || []).forEach(row => {
    const pct = Number(row.frequency || 0) * 100;
    const el = document.createElement("div");
    el.className = `solver-row ${row.key === result.best_action_key ? "best" : ""}`;
    el.innerHTML = `
      <div class="solver-row-top">
        <div>${escapeHtml(row.label)}</div>
        <div class="solver-frequency">${pct.toFixed(1)}%</div>
        <div class="solver-ev">${signedBB(row.ev_bb)}</div>
      </div>
      <div class="solver-bar"><span style="width:${Math.max(1,pct)}%"></span></div>`;
    $("solverActions").appendChild(el);
  });
  $("solverWarning").textContent = result.warning || "";
}

function renderSolverPanel() {
  const canSolve = Boolean(game && game.solver_available);
  $("solveSpot").disabled = !canSolve;
  $("solveSpot").textContent = canSolve ? "Показать подсказку" : "Подсказка недоступна";

  if (solverPreview) {
    renderSolverData(solverPreview, null);
    return;
  }
  if (game?.last_review) {
    renderSolverData(game.last_review.solver, game.last_review);
    return;
  }

  $("solverResult").hidden = true;
  $("solverEmpty").hidden = false;
  if (game && spectatorOnly()) {
    $("solverEmpty").textContent = "В режиме наблюдения CFR-подсказка игроку не нужна. Все действия ботов сохраняются в истории раздач для будущего анализа.";
  } else if (game && !game.terminal && !game.solver_available && game.player_count > 2) {
    $("solverEmpty").textContent = "CFR-lite v0.9 анализирует heads-up споты. В multiway раздаче бот использует multiway equity, pot odds и позиционную логику.";
  } else {
    $("solverEmpty").textContent = "Когда в раздаче останутся два игрока и будет ваш ход, здесь станет доступен CFR-lite разбор.";
  }
}

async function loadTable(render = true) {
  if (ONLINE_TABLE_ID) return;
  const res = await fetch("/api/table");
  tableData = await res.json();

  // Восстанавливаем активную раздачу после F5/повторного открытия вкладки.
  // Раньше сервер держал hand lock, но браузер терял `game`, из-за чего
  // пользователь не мог ни доиграть руку, ни изменить состав стола.
  const activeHandId = tableData?.active_hand_id;
  if (activeHandId) {
    if (!game || game.hand_id !== activeHandId || game.terminal) {
      const handRes = await fetch(`/api/game/${encodeURIComponent(activeHandId)}`);
      if (handRes.ok) {
        game = await handRes.json();
        solverPreview = null;
        autoSessionActive = true;
      } else {
        // Сервер больше не может отдать состояние — не оставляем UI в ложном lock.
        game = null;
      }
    }
  } else if (game && !game.terminal) {
    game = null;
    solverPreview = null;
  }

  renderProfile(tableData.profile);
  renderSavedTables();
  const abortBtn = $("abortHand");
  if (abortBtn) abortBtn.hidden = !Boolean(activeHandId);
  if (render) renderGame(); else renderSeats();
  renderRunControls();
  if (game && !game.terminal && activeBotPlayer() && (!spectatorOnly() || !spectatorPaused)) queueAutomation();
}

async function newHand(fromAutomation = false) {
  if (animationBusy) return;
  const button = $("newHand");
  button.disabled = true;
  button.textContent = "Раздаём…";
  solverPreview = null;
  try {
    const res = await fetch("/api/game/new", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      if (res.status === 409 && String(data.detail || "").includes("завершите текущую раздачу")) {
        await loadTable(true);
        return;
      }
      await loadTable(false);
      const waitingBots = (tableData?.bot_cooldowns || []).length > 0;
      const tooFew = res.status === 409 && String(data.detail || "").includes("хотя бы двух");
      if (fromAutomation && infiniteMode && waitingBots && tooFew) {
        $("hint").textContent = "Недостаточно игроков: выбитые боты на тайм-ауте. Места свободны — к столу можно посадить человека.";
        scheduleCooldownRetry();
        return;
      }
      const lowStack = res.status === 409 && String(data.detail || "").includes("меньше 1 ББ");
      if (lowStack) {
        alert("У человеческого профиля осталось меньше 1 ББ. Боты с нулевым депозитом автоматически покидают рум; человеческий баланс не пополняется автоматически.");
      } else {
        alert(data.detail || "Не удалось начать раздачу");
      }
      autoSessionActive = false;
      clearAutomationTimer();
      return;
    }
    game = data;
    autoSessionActive = true;
    spectatorPaused = false;
    await loadTable(false);
    renderGame();
    await animateInitialDeal(game);
    await animateActionDelta(null, game, { includeBlinds: true });
    queueAutomation();
  } finally {
    button.textContent = infiniteMode ? "Следующая раздача" : "Новая раздача";
    if (!game || game.terminal) button.disabled = false;
    renderRunControls();
  }
}

async function sendAction(action, amount = 0) {
  if (!game || animationBusy) return;
  if (window.Poker8OnlineTable && window.Poker8Transport) return Poker8Transport.sendAction(action, Math.round(Number(amount || 0) * 100));
  if (isLocalHumanTurn()) clearPendingAction(false);
  solverPreview = null;
  document.querySelectorAll("#actionButtons button").forEach(b => b.disabled = true);
  const res = await fetch("/api/game/" + encodeURIComponent(game.hand_id) + "/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, amount }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось выполнить действие");
    renderGame();
    return;
  }
  const previousGame = game;
  await animateActionDelta(previousGame, data);
  game = data;
  if (game.terminal) await loadTable(false);
  renderGame();
  queueAutomation();
}

async function timeoutFold() {
  if (!game || animationBusy || !isLocalHumanTurn()) return;
  clearPendingAction(false);
  const res = await fetch(`/api/game/${game.hand_id}/timeout-fold`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) { renderGame(); return; }
  const previousGame = game;
  await animateActionDelta(previousGame, data);
  game = data;
  if (game.terminal) await loadTable(false);
  renderGame();
  queueAutomation();
}

async function requestSolver() {
  if (!game?.solver_available) return;
  $("solveSpot").disabled = true;
  $("solverLoading").hidden = false;
  try {
    const res = await fetch(`/api/game/${game.hand_id}/solver`);
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Не удалось рассчитать спот");
      return;
    }
    solverPreview = data;
    renderSolverPanel();
  } finally {
    $("solverLoading").hidden = true;
    $("solveSpot").disabled = !game?.solver_available;
  }
}

function setOccupantType(type) {
  modalOccupantType = type === "human" ? "human" : "bot";
  $("chooseHuman").classList.toggle("active", modalOccupantType === "human");
  $("chooseBot").classList.toggle("active", modalOccupantType === "bot");
  $("humanSeatFields").hidden = modalOccupantType !== "human";
  $("botSeatFields").hidden = modalOccupantType !== "bot";
}

function fillSeatProfileSelect(config) {
  const select = $("seatProfileSelect");
  select.innerHTML = "";
  const profiles = tableData?.profiles || [];
  profiles.forEach(profile => {
    const seatedElsewhere = tableData?.seats?.some(s =>
      s.active && s.occupant_type === "human" && s.profile_id === profile.id && Number(s.seat) !== Number(config.seat)
    );
    if (seatedElsewhere) return;
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = `${profile.name} · ${Number(profile.balance || 0).toFixed(2)} ББ`;
    option.selected = config.profile_id === profile.id || (!config.profile_id && profile.id === tableData?.active_profile_id);
    select.appendChild(option);
  });
  if (!select.options.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Нет свободных профилей — создайте новый";
    select.appendChild(option);
  }
}

function openSeatModal(seat) {
  if ((game && !game.terminal) || tableData?.locked) {
    alert("Состав стола нельзя менять во время раздачи. Доиграйте её или нажмите «Прервать раздачу» вверху.");
    return;
  }
  const config = currentSeatConfig(seat);
  if (!config) return;
  modalSeat = seat;
  modalDifficulty = config.difficulty || "normal";
  modalOccupantType = config.occupant_type === "human" ? "human" : "bot";
  $("modalSeatNumber").textContent = String(seat + 1);
  $("modalTitle").textContent = config.active ? "Настроить место" : "Посадить за стол";
  $("botName").value = config.occupant_type === "bot" ? config.name : `Бот ${seat + 1}`;
  $("removeBot").hidden = !config.active;
  $("saveBot").textContent = config.active ? "Сохранить место" : "Посадить за стол";
  fillSeatProfileSelect(config);
  setOccupantType(modalOccupantType);
  document.querySelectorAll("[data-difficulty]").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.difficulty === modalDifficulty);
  });
  $("botModal").hidden = false;
}

function closeBotModal() {
  $("botModal").hidden = true;
  modalSeat = null;
}

async function saveSeat() {
  if (modalSeat == null) return;
  let url, body;
  if (modalOccupantType === "human") {
    const profileId = $("seatProfileSelect").value;
    if (!profileId) {
      alert("Создайте свободный профиль игрока");
      return;
    }
    url = `/api/table/seats/${modalSeat}/human`;
    body = { profile_id: profileId };
  } else {
    url = `/api/table/seats/${modalSeat}/bot`;
    body = { name: $("botName").value, difficulty: modalDifficulty };
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось изменить место");
    return;
  }
  closeBotModal();
  await renderRunControls();
loadTable();
}

async function clearSeat() {
  if (modalSeat == null) return;
  const res = await fetch(`/api/table/seats/${modalSeat}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось освободить место");
    return;
  }
  closeBotModal();
  await renderRunControls();
loadTable();
}

function openProfileModal(mode = "create") {
  if (tableData?.locked) {
    alert("Профиль нельзя менять во время раздачи. Доиграйте её или нажмите «Прервать раздачу» вверху.");
    return;
  }
  profileModalMode = mode;
  const active = tableData?.profile;
  if (mode === "rename") {
    $("profileModalTitle").textContent = "Переименовать профиль";
    $("profileName").value = active?.name || "";
    $("saveProfile").textContent = "Сохранить";
  } else {
    $("profileModalTitle").textContent = "Новый профиль";
    $("profileName").value = "";
    $("saveProfile").textContent = "Создать и выбрать";
  }
  $("profileModal").hidden = false;
  setTimeout(() => $("profileName").focus(), 30);
}

function closeProfileModal() {
  $("profileModal").hidden = true;
}

async function saveProfileModal() {
  const name = $("profileName").value.trim();
  if (!name) {
    alert("Введите имя профиля");
    return;
  }

  const activeId = tableData?.active_profile_id;
  const url = profileModalMode === "rename"
    ? `/api/profiles/${encodeURIComponent(activeId)}`
    : "/api/profiles";
  const method = profileModalMode === "rename" ? "PATCH" : "POST";

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось сохранить профиль");
    return;
  }
  closeProfileModal();
  game = null;
  solverPreview = null;
  await renderRunControls();
loadTable();
}

async function activateProfile(profileId) {
  if (!profileId || profileId === tableData?.active_profile_id) return;
  if (tableData?.locked) {
    alert("Сначала завершите текущую раздачу");
    renderProfile(tableData.profile);
    return;
  }
  const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}/activate`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось переключить профиль");
    renderProfile(tableData.profile);
    return;
  }
  game = null;
  solverPreview = null;
  await renderRunControls();
loadTable();
}

async function abortCurrentHand() {
  if (animationBusy) return;
  clearAutomationTimer();
  const activeId = tableData?.active_hand_id || (game && !game.terminal ? game.hand_id : null);
  if (!activeId) {
    await loadTable(true);
    return;
  }

  if (!confirm("Прервать текущую раздачу? Незавершённая рука не попадёт в статистику, а постоянные балансы останутся такими, какими были до её начала.")) return;

  const button = $("abortHand");
  if (button) button.disabled = true;
  try {
    const res = await fetch("/api/game/active/abort", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Не удалось прервать раздачу");
      return;
    }
    game = null;
    solverPreview = null;
    autoSessionActive = false;
    spectatorPaused = false;
    await loadTable(true);
  } finally {
    if (button) button.disabled = false;
  }
}

async function resetBalances() {
  clearAutomationTimer();
  if (game && !game.terminal) {
    alert("Сначала завершите текущую раздачу");
    return;
  }
  if (!confirm("Сбросить балансы всех профилей и ботов до 1000 ББ? История раздач и модели останутся.")) return;
  const res = await fetch("/api/bankroll/reset", { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось сбросить баланс");
    return;
  }
  game = null;
  solverPreview = null;
  await renderRunControls();
loadTable();
}

function renderSavedTables() {
  const target = $("savedTablesList");
  if (!target) return;
  const rows = tableData?.saved_tables || [];
  if (!rows.length) {
    target.innerHTML = '<div class="model-empty">Сохранённых столов пока нет.</div>';
    return;
  }
  target.innerHTML = rows.map(row => `
    <div class="saved-table-row ${row.current ? "current" : ""}">
      <div class="saved-table-main">
        <strong>${escapeHtml(row.name)}</strong>
        <span>${row.players} игроков · ${row.humans} людей · ${row.bots} ботов${row.current ? " · открыт" : ""}</span>
      </div>
      <div class="saved-table-actions">
        <button data-load-table="${row.id}" title="Открыть">↗</button>
        <button data-delete-table="${row.id}" class="danger" title="Удалить">×</button>
      </div>
    </div>`).join("");
  target.querySelectorAll("[data-load-table]").forEach(btn => btn.onclick = () => loadSavedTable(btn.dataset.loadTable));
  target.querySelectorAll("[data-delete-table]").forEach(btn => btn.onclick = () => deleteSavedTable(btn.dataset.deleteTable));
  const current = rows.find(r => r.current);
  if (current && !$("savedTableName").value) $("savedTableName").value = current.name;
  $("saveCurrentTable").textContent = current ? "Сохранить как новый стол" : "Сохранить текущий стол";
}

async function saveCurrentTable() {
  if (tableData?.locked) {
    alert("Сначала завершите или прервите текущую раздачу");
    return;
  }
  let name = $("savedTableName").value.trim();
  const current = (tableData?.saved_tables || []).find(r => r.current);
  if (!name && current) name = current.name;
  if (!name) {
    alert("Введите название стола");
    return;
  }
  const res = await fetch("/api/tables", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось сохранить стол");
    return;
  }
  await renderRunControls();
loadTable();
}

async function loadSavedTable(tableId) {
  if (tableData?.locked) {
    alert("Сначала завершите или прервите текущую раздачу");
    return;
  }
  const res = await fetch(`/api/tables/${encodeURIComponent(tableId)}/load`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось открыть стол");
    return;
  }
  game = null;
  solverPreview = null;
  $("savedTableName").value = data.saved_table?.name || "";
  await renderRunControls();
loadTable();
}

async function deleteSavedTable(tableId) {
  if (tableData?.locked) {
    alert("Сначала завершите или прервите текущую раздачу");
    return;
  }
  const row = (tableData?.saved_tables || []).find(r => r.id === tableId);
  if (!confirm(`Удалить сохранённый стол «${row?.name || ""}»? Профили и их история не удаляются.`)) return;
  const res = await fetch(`/api/tables/${encodeURIComponent(tableId)}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "Не удалось удалить стол");
    return;
  }
  if (row?.current) $("savedTableName").value = "";
  await renderRunControls();
loadTable();
}

function setMobileDrawer(open) {
  const drawer=$("mobileDrawer"), backdrop=$("mobileDrawerBackdrop");
  drawer?.classList.toggle("open", open);
  drawer?.setAttribute("aria-hidden", open ? "false" : "true");
  if (backdrop) backdrop.hidden=!open;
}

$("newHand").onclick = () => newHand(false);
$("mobilePrimaryAction").onclick = () => (game && !game.terminal ? abortCurrentHand() : newHand(false));
$("mobileMenuButton").onclick = () => setMobileDrawer(true);
$("mobileDrawerClose").onclick = () => setMobileDrawer(false);
$("mobileDrawerBackdrop").onclick = () => setMobileDrawer(false);
$("mobileDrawerNewHand").onclick = () => { setMobileDrawer(false); if (!game || game.terminal) newHand(false); };
$("mobileDrawerInfinite").onclick = () => { setMobileDrawer(false); setInfiniteMode(!infiniteMode); };
$("mobileDrawerPause").onclick = () => { setMobileDrawer(false); toggleSpectatorPause(); };
$("infiniteMode").onclick = () => setInfiniteMode(!infiniteMode);
$("spectatorPause").onclick = toggleSpectatorPause;
$("botSpeedSelect").onchange = (event) => setBotSpeed(event.target.value);
$("abortHand").onclick = abortCurrentHand;
$("solveSpot").onclick = requestSolver;
$("resetBankroll").onclick = resetBalances;
$("saveCurrentTable").onclick = saveCurrentTable;
$("botCooldownSelect").onchange = (e) => setBotCooldown(e.target.value);
$("profileSelect").onchange = (e) => activateProfile(e.target.value);
$("newProfile").onclick = () => openProfileModal("create");
$("renameProfile").onclick = () => openProfileModal("rename");
$("closeProfileModal").onclick = closeProfileModal;
$("saveProfile").onclick = saveProfileModal;
$("profileModal").onclick = (e) => { if (e.target === $("profileModal")) closeProfileModal(); };
$("profileName").onkeydown = (e) => { if (e.key === "Enter") saveProfileModal(); };
$("closeModal").onclick = closeBotModal;
$("saveBot").onclick = saveSeat;
$("removeBot").onclick = clearSeat;
$("chooseHuman").onclick = () => setOccupantType("human");
$("chooseBot").onclick = () => setOccupantType("bot");
$("botModal").onclick = (e) => { if (e.target === $("botModal")) closeBotModal(); };

document.querySelectorAll("[data-difficulty]").forEach(btn => {
  btn.onclick = () => {
    modalDifficulty = btn.dataset.difficulty;
    document.querySelectorAll("[data-difficulty]").forEach(x => x.classList.toggle("active", x === btn));
  };
});


$("mobileHistoryButton").onclick = () => openMobileSheet("history");
$("mobileSolverButton").onclick = () => openMobileSheet("solver");
$("mobileTableButton").onclick = scrollToMobileTable;
$("mobileHistoryFromAction").onclick = () => openMobileSheet("history");
$("mobileSolverFromAction").onclick = () => openMobileSheet("solver");
$("closeHistorySheet").onclick = closeMobileSheets;
$("closeSolverSheet").onclick = closeMobileSheets;
$("mobileSheetBackdrop").onclick = closeMobileSheets;
window.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMobileSheets(); });
window.addEventListener("resize", () => { if (!isMobileLayout()) closeMobileSheets(); });

$("clearQueuedAction").onclick = () => clearPendingAction();
$("amountMinus").onclick = () => { const input=$("amount"); const step=Number(input.step||0.5)||0.5; syncAmountControls(Number(input.value||0)-step); };
$("amountPlus").onclick = () => { const input=$("amount"); const step=Number(input.step||0.5)||0.5; syncAmountControls(Number(input.value||0)+step); };

$("amount").addEventListener("input", () => syncAmountControls(Number($("amount").value || 0)));
$("amountSlider").addEventListener("input", () => syncAmountControls(Number($("amountSlider").value || 0)));

document.querySelectorAll("[data-sizing]").forEach(btn => {
  btn.onclick = () => {
    if (!game) return;
    syncAmountControls(presetTarget(Number(btn.dataset.sizing || 0)));
  };
});

setInterval(() => {
  renderCooldowns();
  const ready = (tableData?.bot_cooldowns || []).some(row => cooldownRemainingSeconds(row) <= 0);
  const now = Date.now();
  if (ready && !tableData?.locked && !cooldownRefreshPending && now - lastCooldownRefreshAt > 4000) {
    cooldownRefreshPending = true;
    lastCooldownRefreshAt = now;
    loadTable(true).finally(() => { cooldownRefreshPending = false; });
  }
}, 1000);

renderRunControls();
loadTable();
