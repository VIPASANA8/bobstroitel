/* The neon cube by itself: a canvas that drifts, drags, rolls and lands.
   Lifted verbatim out of cube.js so the same cube can sit on the login card
   with no game behind it -- `update` is still the only way in, and a cube
   nobody updates just idles and follows the finger. */
window.Poker8NeonCube = (() => {
  "use strict";

  const motion = window.Poker8CubeMotion;
  const canvasCube = window.Poker8CubeCanvas;

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

  return createNeonCube;
})();
