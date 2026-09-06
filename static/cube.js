/* CUBE, from CASE8 src/features/cube/game/{NeonCube,App}.tsx.
   Same screen, same motion, no React: poker8 serves static files, so the two
   components are a closure that draws and a closure that wires the controls.

   What did not come across is the standalone game's own wallet -- the local
   round source, the faucet dialog, the reset dialog and the owner numbers all
   belong to a copy that keeps its money in localStorage. Here the wallet is
   the one the poker tables pay from, the round is settled by the server, and
   "пополнить" goes where every other top-up in poker8 goes. */
(() => {
  "use strict";

  const motion = window.Poker8CubeMotion;
  const canvasCube = window.Poker8CubeCanvas;
  const $ = id => document.getElementById(id);

  const STAKE_STEP = 5;
  const MAX_STAKE = 100_000;
  const STAKE_NUDGE = 50;
  const MULTIPLIER_TENTHS = { 1: 60, 2: 30, 3: 20 };
  const DEFAULT_STAKE = "2.00";
  const FACES = [1, 2, 3, 4, 5, 6];

  const money = units => (Number(units || 0) / 100).toFixed(2);
  const potentialPayout = (stake, count) => Math.floor((stake * MULTIPLIER_TENTHS[count] + 5) / 10);

  /** Units from what the player typed, or null if that is not an amount. */
  function parseUnits(input) {
    const match = /^(\d{1,4})(?:[.,](\d{1,2}))?$/.exec(String(input).trim());
    if (!match) return null;
    const units = Number(match[1]) * 100 + Number((match[2] || "").padEnd(2, "0"));
    return units <= 0 || units > MAX_STAKE ? null : units;
  }

  const requestId = () => crypto.randomUUID?.()
    || `cube-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  // --- the cube ---------------------------------------------------------------

  /** The neon cube on its canvas. `update` is the only way in: it takes the same
      four things the React component took as props. */
  function createNeonCube(canvas) {
    const REST_FRAME = motion.rollFrameAt(motion.ROLL_DURATION_MS);
    const state = { currentFace: 1, targetFace: 1, rolling: false, idle: true };
    const pose = { x: motion.IDLE_TILT_X, y: 24, velocityX: 0, velocityY: 0, phase: "idle" };

    let pointer = null;
    let returning = null;
    let rolling = null;
    let resultTimer = null;
    let resultTimerDueAt = null;
    let pausedResultDelay = null;
    let frameHandle = null;
    let reducedMotion = false;
    let pulseStartedAt = null;
    let landedAt = null;
    let idleAnchor = null;
    let resultRestStartedAt = null;
    const histories = new Map();
    const velocities = new Map();
    const previousPips = new Map();

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const readMotionPreference = () => { reducedMotion = media.matches; };
    readMotionPreference();
    media.addEventListener("change", readMotionPreference);

    function applyRotation(rotation) {
      pose.x = rotation.x;
      pose.y = rotation.y;
    }

    function clearResultTimer() {
      if (resultTimer !== null) window.clearTimeout(resultTimer);
      resultTimer = null;
      resultTimerDueAt = null;
      pausedResultDelay = null;
    }

    function startResultTimer(delay) {
      resultTimerDueAt = performance.now() + delay;
      if (document.visibilityState === "hidden") {
        pausedResultDelay = delay;
        resultTimerDueAt = null;
        return;
      }
      resultTimer = window.setTimeout(() => {
        resultTimer = null;
        resultTimerDueAt = null;
        pausedResultDelay = null;
        beginReturn(motion.resultRestRotation(state.currentFace), 900, "result-rest");
      }, delay);
    }

    function beginReturn(to, duration, next, delay = 0) {
      if (reducedMotion || duration === 0) {
        applyRotation(to);
        pose.phase = next;
        returning = null;
        return;
      }
      returning = {
        from: { x: pose.x, y: pose.y },
        to,
        startedAt: performance.now() + delay,
        duration,
        next,
      };
      pose.phase = "returning";
    }

    function scheduleContextualReturn() {
      clearResultTimer();
      if (state.idle) {
        beginReturn({ x: motion.IDLE_TILT_X, y: pose.y }, 800, "idle", 180);
        return;
      }
      if (reducedMotion) {
        beginReturn(motion.resultRestRotation(state.currentFace), 0, "result-rest");
        return;
      }
      pose.phase = "result-hold";
      startResultTimer(motion.resultHoldDelay());
    }

    function triggerPulse() {
      pulseStartedAt = reducedMotion ? null : performance.now();
    }

    function manualFrame() {
      if (reducedMotion) return REST_FRAME;
      const speed = Math.min(1, Math.hypot(pose.velocityX, pose.velocityY) / 0.5);
      if (pose.phase === "drag" || pose.phase === "inertia") {
        return { ...REST_FRAME, trailStrength: 0.24 + speed * 0.62, pipStretch: 1.25 + speed * 1.55, glow: 1.28 + speed * 0.24 };
      }
      if (pose.phase === "idle") return { ...REST_FRAME, trailStrength: 0.08, pipStretch: 1.08, glow: 1.16 };
      if (pose.phase === "returning") return { ...REST_FRAME, trailStrength: 0.12, pipStretch: 1.12, glow: 1.12 };
      return REST_FRAME;
    }

    function draw(now, profile, drawElapsed) {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (width <= 0 || height <= 0) return;
      const context = canvas.getContext("2d");
      if (!context) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const pixelWidth = Math.round(width * dpr);
      const pixelHeight = Math.round(height * dpr);
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
      }
      context.setTransform(dpr, 0, 0, dpr, 0, 0);

      const viewport = { width, height, size: Math.min(width, height) * 0.47, perspective: width * (520 / 312) };
      const cubePose = {
        rotation: { x: pose.x, y: pose.y },
        lift: profile.lift,
        scale: { x: profile.scaleX, y: profile.scaleY, z: profile.scaleZ },
      };
      const geometry = canvasCube.buildCubeGeometry(cubePose, viewport);
      const tracking = !reducedMotion && profile.trailStrength > 0;
      if (!tracking) velocities.clear();

      const visiblePips = geometry.pips.filter(item => item.visible);
      canvasCube.pruneHiddenPipState(
        new Set(visiblePips.map(pip => pip.id)), now, histories, velocities, previousPips,
      );
      for (const pip of visiblePips) {
        const previous = previousPips.get(pip.id);
        const history = histories.get(pip.id) || [];
        if (tracking && previous) {
          const oldVelocity = velocities.get(pip.id) || { x: 0, y: 0 };
          const velocity = canvasCube.smoothScreenVelocity(previous, pip, oldVelocity, drawElapsed);
          velocities.set(pip.id, velocity);
          histories.set(pip.id, canvasCube.appendTrailSample(
            history, { x: pip.x, y: pip.y, depth: pip.depth, at: now }, now,
          ));
        } else if (tracking && history.length > 0) {
          histories.set(pip.id, canvasCube.appendTrailSample(
            history, { x: pip.x, y: pip.y, depth: pip.depth, at: now, startsTrail: true }, now,
          ));
        }
        previousPips.set(pip.id, { x: pip.x, y: pip.y });
      }

      const pulseProgress = pulseStartedAt === null ? 2 : (now - pulseStartedAt) / 650;
      if (pulseProgress > 1) pulseStartedAt = null;
      const resultFace = state.idle || pose.phase === "rolling" ? null : state.currentFace;
      // No landing timestamp means the result was restored rather than played:
      // settled cube, no repaint, wave still runs.
      const sinceLanded = landedAt === null ? null : now - landedAt;
      const settled = sinceLanded === null;
      canvasCube.renderCanvasCube(context, canvasCube.buildRenderPlan({
        pose: cubePose,
        viewport,
        roll: profile,
        histories,
        velocities,
        now,
        pulseProgress,
        resultFace,
        sweepProgress: reducedMotion ? 2 : canvasCube.sweepProgressAt(sinceLanded ?? now),
        recolorProgress: reducedMotion || settled ? 0 : canvasCube.recolorProgressAt(sinceLanded),
        emphasisProgress: reducedMotion || settled ? 1 : canvasCube.emphasisProgressAt(sinceLanded),
      }));
    }

    let lastAt = performance.now();
    let lastDrawAt = 0;
    let hiddenAt = null;

    function frame(now) {
      const elapsed = Math.min(32, Math.max(0, now - lastAt));
      lastAt = now;
      if (pose.phase !== "idle") idleAnchor = null;
      let profile = manualFrame();

      if (pose.phase === "rolling" && rolling) {
        const rollElapsed = reducedMotion ? motion.ROLL_DURATION_MS : now - rolling.startedAt;
        profile = reducedMotion ? REST_FRAME : motion.rollFrameAt(rollElapsed);
        applyRotation(motion.rollRotationAt(rolling.fromFace, rolling.toFace, rollElapsed));
      } else if (pose.phase === "idle" && !reducedMotion) {
        idleAnchor = idleAnchor || { at: now, base: { x: pose.x, y: pose.y } };
        applyRotation(motion.idleRotationAt(now - idleAnchor.at, idleAnchor.base));
      } else if (pose.phase === "inertia") {
        const step = motion.stepInertia(pose, { x: pose.velocityX, y: pose.velocityY }, elapsed);
        pose.velocityX = step.velocity.x;
        pose.velocityY = step.velocity.y;
        applyRotation(step.rotation);
        if (!step.moving) scheduleContextualReturn();
      } else if (pose.phase === "returning" && returning) {
        const progress = (now - returning.startedAt) / returning.duration;
        applyRotation(motion.interpolateRotation(returning.from, returning.to, progress));
        if (progress >= 1) {
          pose.phase = returning.next;
          if (returning.next === "result-rest") resultRestStartedAt = now;
          returning = null;
        }
      } else if (pose.phase === "result-rest" && !reducedMotion) {
        resultRestStartedAt = resultRestStartedAt ?? now;
        applyRotation(motion.resultRestRotationAt(state.currentFace, now - resultRestStartedAt));
      }

      const showsResult = !state.idle && pose.phase !== "rolling";
      const active = !reducedMotion && (
        pose.phase === "rolling"
        || pose.phase === "drag"
        || pose.phase === "inertia"
        || pose.phase === "returning"
        || pulseStartedAt !== null
        // Only while a ring is actually crossing the cube; the gap between
        // passes stays at 30fps.
        || (showsResult && canvasCube.sweepProgressAt(landedAt === null ? now : now - landedAt) <= 1)
      );
      if (active || now - lastDrawAt >= 1000 / 30) {
        const drawElapsed = lastDrawAt === 0 ? 1000 / 60 : now - lastDrawAt;
        draw(now, profile, drawElapsed);
        lastDrawAt = now;
      }
      frameHandle = document.visibilityState === "hidden" ? null : window.requestAnimationFrame(frame);
    }

    function handleVisibility() {
      const now = performance.now();
      if (document.visibilityState === "hidden") {
        hiddenAt = now;
        const pausedDelay = motion.remainingDelay(resultTimerDueAt, now);
        if (pausedDelay !== null) {
          window.clearTimeout(resultTimer ?? undefined);
          resultTimer = null;
          resultTimerDueAt = null;
          pausedResultDelay = pausedDelay;
        }
        if (frameHandle !== null) window.cancelAnimationFrame(frameHandle);
        frameHandle = null;
        return;
      }
      if (hiddenAt !== null) {
        const pausedFor = now - hiddenAt;
        if (rolling) rolling.startedAt += pausedFor;
        if (returning) returning.startedAt += pausedFor;
        if (pulseStartedAt !== null) pulseStartedAt += pausedFor;
        if (landedAt !== null) landedAt += pausedFor;
      }
      hiddenAt = null;
      lastAt = now;
      if (pausedResultDelay !== null) {
        const delay = pausedResultDelay;
        pausedResultDelay = null;
        startResultTimer(delay);
      }
      if (frameHandle === null) frameHandle = window.requestAnimationFrame(frame);
    }

    document.addEventListener("visibilitychange", handleVisibility);
    if (document.visibilityState === "hidden") hiddenAt = performance.now();
    else frameHandle = window.requestAnimationFrame(frame);

    // --- pointer and keyboard ---

    canvas.addEventListener("pointerdown", event => {
      if (state.rolling || (event.pointerType === "mouse" && event.button !== 0)) return;
      clearResultTimer();
      returning = null;
      pose.phase = "drag";
      pose.velocityX = 0;
      pose.velocityY = 0;
      canvas.setPointerCapture(event.pointerId);
      pointer = {
        id: event.pointerId,
        startX: event.clientX, startY: event.clientY,
        lastX: event.clientX, lastY: event.clientY,
        lastAt: event.timeStamp, moved: false,
      };
    });

    canvas.addEventListener("pointermove", event => {
      if (!pointer || pointer.id !== event.pointerId || state.rolling) return;
      pointer.moved = pointer.moved
        || Math.hypot(event.clientX - pointer.startX, event.clientY - pointer.startY) >= 4;
      if (!pointer.moved) return;

      const deltaX = event.clientX - pointer.lastX;
      const deltaY = event.clientY - pointer.lastY;
      const elapsed = Math.max(8, event.timeStamp - pointer.lastAt);
      applyRotation(motion.dragRotation(pose, deltaX, deltaY));
      const velocity = motion.clampVelocity({
        x: -deltaY * motion.DRAG_DEGREES_PER_PX / elapsed,
        y: deltaX * motion.DRAG_DEGREES_PER_PX / elapsed,
      });
      pose.velocityX = velocity.x;
      pose.velocityY = velocity.y;
      Object.assign(pointer, { lastX: event.clientX, lastY: event.clientY, lastAt: event.timeStamp });
    });

    function finishPointer(event, cancelled) {
      if (!pointer || pointer.id !== event.pointerId) return;
      const released = pointer;
      pointer = null;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);

      if (!released.moved && !cancelled) {
        triggerPulse();
        scheduleContextualReturn();
        return;
      }
      if (reducedMotion) {
        scheduleContextualReturn();
        return;
      }
      pose.phase = "inertia";
    }

    canvas.addEventListener("pointerup", event => finishPointer(event, false));
    canvas.addEventListener("pointercancel", event => finishPointer(event, true));
    canvas.addEventListener("lostpointercapture", event => finishPointer(event, true));

    canvas.addEventListener("keydown", event => {
      if (state.rolling) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        triggerPulse();
        scheduleContextualReturn();
        return;
      }
      const step = event.shiftKey ? 24 : 12;
      const changes = {
        ArrowUp: { x: -step, y: 0 }, ArrowDown: { x: step, y: 0 },
        ArrowLeft: { x: 0, y: -step }, ArrowRight: { x: 0, y: step },
      };
      const change = changes[event.key];
      if (!change) return;
      event.preventDefault();
      clearResultTimer();
      returning = null;
      applyRotation({ x: pose.x + change.x, y: pose.y + change.y });
      scheduleContextualReturn();
    });

    return {
      update(next) {
        // React ran this on a change of one of the four; render() here is
        // called on every keystroke, and restarting the roll on each of them
        // would keep the cube permanently in the air.
        const unchanged = ["currentFace", "targetFace", "rolling", "idle"]
          .every(key => state[key] === next[key]);
        const wasRolling = state.rolling;
        Object.assign(state, next);
        canvas.setAttribute("aria-label", state.rolling
          ? "Неоновый кубик вращается"
          : state.idle ? "Интерактивный неоновый кубик" : `На кубике ${state.currentFace}`);
        if (unchanged) return;

        if (state.rolling) {
          clearResultTimer();
          pointer = null;
          returning = null;
          pose.phase = "rolling";
          rolling = { fromFace: state.currentFace, toFace: state.targetFace, startedAt: performance.now() };
          histories.clear();
          velocities.clear();
          previousPips.clear();
          resultRestStartedAt = null;
          landedAt = null;
          return;
        }

        if (wasRolling) {
          rolling = null;
          applyRotation(motion.resultRestRotation(state.currentFace));
          pose.velocityX = 0;
          pose.velocityY = 0;
          landedAt = performance.now();
          triggerPulse();
          scheduleContextualReturn();
          return;
        }

        if (state.idle) {
          landedAt = null;
          // Straight into the idle drift from the pose it is already in.
          if (pose.phase === "result-rest") pose.phase = "idle";
        }
      },
    };
  }

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
        ? `Выигрыш ${money(round.payout_units)}`
        : `Ставка ${money(round.stake_units)} не сыграла`;
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
      `Баланс ${balance === null ? "неизвестен" : money(balance)}, пополнить`);

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
        ? "Введите сумму от 0.05 до 1000.00."
        : !validStake() ? "Шаг игровой ставки — 0.05." : "";
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
      const profile = await window.Poker8Auth.ensureSession();
      view.balanceUnits = Number(profile.available_units || 0);
    } catch (error) {
      view.error = window.Poker8Auth.needsSignIn(error)
        ? "Откройте игру из Telegram, чтобы играть на свой баланс."
        : "Не удалось загрузить баланс.";
    }
    render();
  }

  async function play() {
    const balance = view.balanceUnits;
    const units = stake();
    if (balance !== null && units !== null && units > balance) {
      window.location.href = "/static/profile.html#topup";
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
          stake_units: units, selected: view.selected, request_id: requestId(),
        }),
      });
      const body = await response.json().catch(() => ({}));
      // FastAPI answers a schema failure with a list of problems, not a sentence.
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : "Бросок не выполнен.");
      }

      view.error = "";
      view.isRolling = true;
      view.visibleRound = body;
      render();

      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (rollTimer !== null) window.clearTimeout(rollTimer);
      rollTimer = window.setTimeout(() => {
        rollTimer = null;
        view.currentFace = body.roll;
        view.balanceUnits = Number(body.balance_units);
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
    window.location.href = "/static/profile.html#topup";
  });
  $("playButton").addEventListener("click", play);

  render();
  refreshBalance();
})();
