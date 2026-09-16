/* CUBE, from CASE8 src/features/cube/game/{NeonCube,App}.tsx.
   Same screen, same motion, no React: poker8 serves static files, so the two
   components are a closure that draws and a closure that wires the controls.

   What did not come across is the standalone game's own wallet -- the local
   round source, the faucet dialog, the reset dialog and the owner numbers all
   belong to a copy that keeps its money in localStorage. Here the money is
   real: the balance is the CASH wallet, the round is settled by the server,
   and "пополнить" goes to the cashier every other deposit goes through.

   Amounts are micro-USDT integers on this side too. The wire carries decimal
   strings, because a float that has been through JSON turns three ten-cent
   stakes into 0.30000000000000004. */
(() => {
  "use strict";

  const motion = window.Poker8CubeMotion;
  const canvasCube = window.Poker8CubeCanvas;
  const $ = id => document.getElementById(id);

  const MICROS_PER_USDT = 1_000_000;
  const STAKE_STEP = 100_000;          // 0.10 USDT
  const MAX_STAKE = 50_000_000;        // 50 USDT
  const STAKE_NUDGE = 500_000;         // what +/- moves
  const MULTIPLIER_TENTHS = { 1: 60, 2: 30, 3: 20 };
  const DEFAULT_STAKE = "1.00";
  const FACES = [1, 2, 3, 4, 5, 6];

  const money = micros => (Number(micros || 0) / MICROS_PER_USDT).toFixed(2);
  /** The server's decimal string ("0.3", "12") back into micros. */
  const toMicros = usdt => Math.round(Number(usdt || 0) * MICROS_PER_USDT);
  const potentialPayout = (stake, count) => Math.floor((stake * MULTIPLIER_TENTHS[count] + 5) / 10);

  /** Micros from what the player typed, or null if that is not an amount. */
  function parseUnits(input) {
    const match = /^(\d{1,3})(?:[.,](\d{1,2}))?$/.exec(String(input).trim());
    if (!match) return null;
    const micros = Number(match[1]) * MICROS_PER_USDT + Number((match[2] || "").padEnd(2, "0")) * 10_000;
    return micros <= 0 || micros > MAX_STAKE ? null : micros;
  }

  const requestId = () => crypto.randomUUID?.()
    || `cube-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  const createNeonCube = window.Poker8NeonCube;

  // --- the screen -------------------------------------------------------------

  const cube = createNeonCube($("cubeCanvas"));
  const view = {
    selected: [2, 5],
    stakeInput: DEFAULT_STAKE,
    balanceUnits: null,
    error: "",
    isRolling: false,
    currentFace: 1,
    visibleRound: null,
    // Frozen to the pre-roll balance while the cube is in the air, so the new
    // amount lands with the face rather than the instant the round settles.
    rollingBalance: null,
  };
  let rollTimer = null;
  let clearResultAt = null;
  let rollLock = false;

  function buildFaceButtons() {
    const grid = $("faceGrid");
    grid.replaceChildren(...FACES.map(face => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `face-choice face-choice-${face}`;
      button.dataset.face = String(face);
      button.setAttribute("aria-label", `Грань ${face}`);
      const pips = document.createElement("span");
      pips.className = "face-pips";
      pips.setAttribute("aria-hidden", "true");
      for (let slot = 1; slot <= 9; slot += 1) {
        const pip = document.createElement("b");
        if (canvasCube.PIP_SLOTS[face].includes(slot)) pip.className = "is-on";
        pips.appendChild(pip);
      }
      button.appendChild(pips);
      button.addEventListener("click", () => toggleFace(face));
      return button;
    }));
  }

  function stake() {
    return parseUnits(view.stakeInput);
  }

  function validStake() {
    const units = stake();
    return units !== null && units >= STAKE_STEP && units % STAKE_STEP === 0;
  }

  function render() {
    const units = stake();
    const count = view.selected.length;
    const balance = view.rollingBalance ?? view.balanceUnits;
    const insufficient = validStake() && balance !== null && units > balance;
    const payout = validStake() && count ? potentialPayout(units, count) : null;
    const round = view.visibleRound;
    const settled = round && !view.isRolling;

    $("diceCard").className = `dice-card${settled ? (round.won ? " result-win" : " result-loss") : ""}`;

    const resultLine = $("resultLine");
    if (view.isRolling) {
      resultLine.innerHTML = "<small>БРОСОК В ПРОЦЕССЕ</small><strong>Кубик набирает скорость…</strong>";
    } else if (round) {
      resultLine.replaceChildren();
      const small = document.createElement("small");
      small.append("ВЫПАЛО ", Object.assign(document.createElement("b"), { textContent: String(round.roll) }));
      const strong = document.createElement("strong");
      strong.textContent = round.won
        ? `Выигрыш ${money(round.payout_micros)} USDT`
        : `Ставка ${money(round.stake_micros)} USDT не сыграла`;
      resultLine.append(small, strong);
    } else {
      resultLine.innerHTML = "<small>КУБИК ГОТОВ</small><strong>Настрой ставку и запускай</strong>";
    }

    const input = $("stakeInput");
    if (input.value !== view.stakeInput) input.value = view.stakeInput;
    input.disabled = view.isRolling;
    $("stakeUp").disabled = view.isRolling || (units !== null && units >= MAX_STAKE);
    $("stakeDown").disabled = view.isRolling || (units !== null && units <= STAKE_STEP);

    // A balance that cannot cover the next roll says so on its own, and a
    // settled round tints it either way.
    const balanceState = balance === 0 || insufficient
      ? " is-empty"
      : settled ? (round.won ? " is-win" : " is-loss") : "";
    const balanceButton = $("stakeBalance");
    balanceButton.className = `stake-balance${balanceState}`;
    balanceButton.disabled = view.isRolling;
    $("balanceAmount").textContent = balance === null ? "—" : money(balance);
    balanceButton.setAttribute("aria-label",
      `Баланс ${balance === null ? "неизвестен" : `${money(balance)} USDT`}, пополнить`);

    for (const button of $("faceGrid").children) {
      const face = Number(button.dataset.face);
      const chosen = view.selected.includes(face);
      button.classList.toggle("is-selected", chosen);
      button.setAttribute("aria-pressed", String(chosen));
      button.disabled = view.isRolling;
    }
    $("selectedCount").textContent = `${count}/3`;
    $("summarySelected").textContent = count ? `${count} / 6` : "—";
    $("summaryMultiplier").textContent = count ? `×${(MULTIPLIER_TENTHS[count] / 10).toFixed(1)}` : "—";
    $("summaryPayout").textContent = payout ? money(payout) : "—";

    const stakeMessage = view.stakeInput.trim() === ""
      ? ""
      : units === null
        ? "Введите сумму от 0.10 до 50.00 USDT."
        : !validStake() ? "Шаг ставки — 0.10 USDT." : "";
    const message = view.error || stakeMessage;
    $("cubeError").textContent = message;
    $("cubeError").hidden = !message;

    const play = $("playButton");
    play.disabled = view.isRolling || count === 0 || !validStake();
    $("playLabel").textContent = view.isRolling
      ? "КУБИК ВРАЩАЕТСЯ"
      : insufficient ? "ПОПОЛНИТЬ БАЛАНС" : round ? "ПОВТОРИТЬ БРОСОК" : "БРОСИТЬ КУБИК";

    cube.update({
      currentFace: view.currentFace,
      targetFace: round ? round.roll : view.currentFace,
      rolling: view.isRolling,
      idle: !round && !view.isRolling,
    });
  }

  function toggleFace(face) {
    view.error = "";
    if (view.selected.includes(face)) {
      view.selected = view.selected.filter(value => value !== face);
    } else if (view.selected.length === 3) {
      view.error = "Можно выбрать не больше трёх граней.";
    } else {
      view.selected = [...view.selected, face].sort();
    }
    render();
  }

  function stepStake(by) {
    const next = (stake() ?? 0) + by;
    view.error = "";
    view.stakeInput = money(next < STAKE_STEP ? STAKE_STEP : Math.min(next, MAX_STAKE));
    render();
  }

  /* The cube lets go of the result long after the impulse has: once it does,
     the round line goes back to idle. */
  function holdResult() {
    if (clearResultAt !== null) window.clearTimeout(clearResultAt);
    clearResultAt = window.setTimeout(() => {
      view.visibleRound = null;
      render();
    }, canvasCube.RESULT_CLEAR_MS);
  }

  async function refreshBalance() {
    try {
      await window.Poker8Auth.ensureSession();
      const response = await fetch("/api/cash/wallet");
      // 404 is cash mode off, 403 is this account not being let into it. Both
      // mean there is no USDT to play with, and neither is the player's fault.
      if (!response.ok) throw new Error(String(response.status));
      view.balanceUnits = toMicros((await response.json()).available_usdt);
    } catch (error) {
      view.error = window.Poker8Auth.needsSignIn(error)
        ? "Откройте игру из Telegram, чтобы играть на свой баланс."
        : "CASH-касса недоступна — играть на USDT сейчас нельзя.";
    }
    render();
  }

  async function play() {
    const balance = view.balanceUnits;
    const units = stake();
    if (balance !== null && units !== null && units > balance) {
      window.location.href = "/static/profile.html?app=cube#cash";
      return;
    }
    if (rollLock || !validStake() || !view.selected.length) return;
    rollLock = true;

    try {
      // Freeze the shown amount before settling, so the new one lands with the face.
      view.rollingBalance = balance;
      const response = await fetch("/api/cube/roll", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stake_usdt: money(units), selected: view.selected, request_id: requestId(),
        }),
      });
      const body = await response.json().catch(() => ({}));
      // FastAPI answers a schema failure with a list of problems, not a sentence.
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : "Бросок не выполнен.");
      }

      view.error = "";
      view.isRolling = true;
      view.visibleRound = {
        ...body,
        stake_micros: toMicros(body.stake_usdt),
        payout_micros: toMicros(body.payout_usdt),
      };
      render();

      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (rollTimer !== null) window.clearTimeout(rollTimer);
      rollTimer = window.setTimeout(() => {
        rollTimer = null;
        view.currentFace = body.roll;
        view.balanceUnits = toMicros(body.available_usdt);
        view.rollingBalance = null;
        view.isRolling = false;
        rollLock = false;
        render();
        holdResult();
      }, reduced ? 60 : motion.ROLL_DURATION_MS);
    } catch (error) {
      rollLock = false;
      view.rollingBalance = null;
      view.isRolling = false;
      view.visibleRound = null;
      view.error = error.message || "Не удалось выполнить бросок.";
      render();
    }
  }

  buildFaceButtons();
  $("stakeInput").addEventListener("input", event => {
    view.stakeInput = event.target.value;
    view.error = "";
    render();
  });
  $("stakeUp").addEventListener("click", () => stepStake(STAKE_NUDGE));
  $("stakeDown").addEventListener("click", () => stepStake(-STAKE_NUDGE));
  $("stakeBalance").addEventListener("click", () => {
    window.location.href = "/static/profile.html?app=cube#cash";
  });
  $("playButton").addEventListener("click", play);

  render();
  refreshBalance();
})();
