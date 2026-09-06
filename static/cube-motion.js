/* CUBE motion, from CASE8 src/features/cube/game/cubeMotion.ts.
   Pure arithmetic: where the cube is pointing, and what shape it is in, at a
   given millisecond. Types are the only thing dropped -- poker8 serves static
   files with no build step, so the browser gets what is written here. */
window.Poker8CubeMotion = (() => {
  "use strict";

  const ROLL_DURATION_MS = 3000;
  const RESULT_HOLD_MIN_MS = 3000;
  const RESULT_HOLD_MAX_MS = 6000;
  const IDLE_TILT_X = -24;
  const DRAG_DEGREES_PER_PX = 0.45;
  const MAX_VELOCITY_DEGREES_PER_MS = 0.8;

  const RESULT_REST_ORIENTATIONS = {
    1: { x: -24, y: 24 },
    2: { x: -42, y: -56 },
    3: { x: -114, y: 24 },
    4: { x: 66, y: 24 },
    5: { x: -42, y: 124 },
    6: { x: -24, y: 204 },
  };

  const clamp01 = value => Math.min(1, Math.max(0, value));
  const lerp = (from, to, progress) => from + (to - from) * progress;
  const easeOutCubic = value => 1 - (1 - clamp01(value)) ** 3;
  const easeInOutCubic = value => {
    const t = clamp01(value);
    return t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
  };
  const segment = (elapsed, from, to) => clamp01((elapsed - from) / (to - from));

  function rollFrameAt(elapsedMs) {
    const elapsed = Math.min(ROLL_DURATION_MS, Math.max(0, elapsedMs));

    if (elapsed < 180) {
      const t = easeOutCubic(segment(elapsed, 0, 180));
      return {
        phase: "compress", rotationProgress: 0.02 * t, lift: 0,
        scaleX: lerp(1, 1.08, t), scaleY: lerp(1, 0.88, t), scaleZ: lerp(1, 1.04, t),
        trailStrength: 0.12 * t, pipStretch: lerp(1, 1.25, t), glow: lerp(1, 1.25, t),
        shadowScale: lerp(1, 1.12, t), shadowAlpha: lerp(0.34, 0.48, t),
      };
    }

    if (elapsed < 360) {
      const t = easeOutCubic(segment(elapsed, 180, 360));
      return {
        phase: "launch", rotationProgress: lerp(0.02, 0.13, t), lift: lerp(0, 0.62, t),
        scaleX: lerp(1.08, 0.93, t), scaleY: lerp(0.88, 1.13, t), scaleZ: lerp(1.04, 0.96, t),
        trailStrength: lerp(0.12, 0.76, t), pipStretch: lerp(1.25, 2.4, t), glow: lerp(1.25, 1.6, t),
        shadowScale: lerp(1.12, 0.76, t), shadowAlpha: lerp(0.48, 0.23, t),
      };
    }

    if (elapsed < 1950) {
      const t = easeInOutCubic(segment(elapsed, 360, 1950));
      return {
        phase: "flight", rotationProgress: lerp(0.13, 0.78, t), lift: Math.sin(t * Math.PI) * 0.34 + 0.62,
        scaleX: 1 + Math.sin(t * Math.PI * 4) * 0.035,
        scaleY: 1 - Math.sin(t * Math.PI * 4) * 0.045,
        scaleZ: 1 + Math.cos(t * Math.PI * 4) * 0.025,
        trailStrength: lerp(0.76, 1, Math.min(1, t * 2)), pipStretch: lerp(2.4, 3.1, Math.min(1, t * 2)),
        glow: 1.6, shadowScale: 0.7, shadowAlpha: 0.18,
      };
    }

    if (elapsed < 2500) {
      const t = easeInOutCubic(segment(elapsed, 1950, 2500));
      return {
        phase: "catch", rotationProgress: lerp(0.78, 1, t), lift: lerp(0.62, 0, t),
        scaleX: lerp(1, 1.02, t), scaleY: lerp(1, 0.98, t), scaleZ: 1,
        trailStrength: lerp(1, 0.36, t), pipStretch: lerp(3.1, 1.35, t), glow: lerp(1.6, 1.18, t),
        shadowScale: lerp(0.7, 1.13, t), shadowAlpha: lerp(0.18, 0.5, t),
      };
    }

    if (elapsed < 2820) {
      const raw = segment(elapsed, 2500, 2820);
      const t = easeOutCubic(raw);
      const bounce = Math.sin(raw * Math.PI);
      const contact = 1 - bounce;
      return {
        phase: "land", rotationProgress: 1, lift: bounce * 0.46,
        scaleX: 1 + contact * lerp(0.1, 0.04, raw),
        scaleY: 1 - contact * lerp(0.14, 0.06, raw),
        scaleZ: 1 + contact * lerp(0.04, 0.02, raw),
        trailStrength: lerp(0.36, 0.1, t), pipStretch: lerp(1.35, 1.05, t), glow: lerp(1.18, 1.05, t),
        shadowScale: lerp(1.13, 0.82, bounce), shadowAlpha: lerp(0.5, 0.26, bounce),
      };
    }

    const t = easeOutCubic(segment(elapsed, 2820, ROLL_DURATION_MS));
    return {
      phase: "settle", rotationProgress: 1, lift: 0,
      scaleX: lerp(1.04, 1, t), scaleY: lerp(0.94, 1, t), scaleZ: lerp(1.02, 1, t),
      trailStrength: lerp(0.1, 0, t), pipStretch: lerp(1.05, 1, t), glow: lerp(1.05, 1, t),
      shadowScale: lerp(1.13, 1, t), shadowAlpha: lerp(0.5, 0.34, t),
    };
  }

  function dragRotation(current, deltaX, deltaY) {
    return {
      x: current.x - deltaY * DRAG_DEGREES_PER_PX,
      y: current.y + deltaX * DRAG_DEGREES_PER_PX,
    };
  }

  function clampVelocity(velocity) {
    const speed = Math.hypot(velocity.x, velocity.y);
    if (speed <= MAX_VELOCITY_DEGREES_PER_MS) return velocity;
    const scale = MAX_VELOCITY_DEGREES_PER_MS / speed;
    return { x: velocity.x * scale, y: velocity.y * scale };
  }

  function stepInertia(rotation, velocity, deltaMs) {
    const frameMs = Math.min(32, Math.max(0, deltaMs));
    return {
      rotation: { x: rotation.x + velocity.x * frameMs, y: rotation.y + velocity.y * frameMs },
      velocity,
      moving: Math.hypot(velocity.x, velocity.y) > 0,
    };
  }

  function resultHoldDelay(random = Math.random) {
    const unit = Math.min(1, Math.max(0, random()));
    return Math.round(RESULT_HOLD_MIN_MS + unit * (RESULT_HOLD_MAX_MS - RESULT_HOLD_MIN_MS));
  }

  const remainingDelay = (dueAt, now) => (dueAt === null ? null : Math.max(0, dueAt - now));

  function resultRestRotation(face) {
    return { ...(RESULT_REST_ORIENTATIONS[face] || RESULT_REST_ORIENTATIONS[1]) };
  }

  function resultRestRotationAt(face, elapsedMs) {
    const base = resultRestRotation(face);
    return { x: base.x, y: base.y + Math.sin(Math.max(0, elapsedMs) / 2200) * 11 };
  }

  /* Idle drift around wherever the cube already is: elapsed is measured from the
     moment it went idle, so the drift opens at zero offset and the cube keeps
     the pose it was left in instead of snapping to one. */
  function idleRotationAt(elapsedMs, base = { x: IDLE_TILT_X, y: 24 }) {
    return {
      x: base.x + Math.sin(elapsedMs / 2300) * 4,
      y: base.y + Math.sin(elapsedMs / 2900) * 12,
    };
  }

  function rollRotationAt(fromFace, toFace, elapsedMs) {
    const progress = rollFrameAt(elapsedMs).rotationProgress;
    const from = resultRestRotation(fromFace);
    const to = resultRestRotation(toFace);
    return {
      x: from.x + (to.x + 1080 - from.x) * progress,
      y: from.y + (to.y - from.y) * progress,
    };
  }

  function interpolateRotation(from, to, progress) {
    const eased = 1 - (1 - clamp01(progress)) ** 3;
    return { x: from.x + (to.x - from.x) * eased, y: from.y + (to.y - from.y) * eased };
  }

  return {
    ROLL_DURATION_MS, IDLE_TILT_X, DRAG_DEGREES_PER_PX,
    rollFrameAt, dragRotation, clampVelocity, stepInertia, resultHoldDelay,
    remainingDelay, resultRestRotation, resultRestRotationAt, idleRotationAt,
    rollRotationAt, interpolateRotation,
  };
})();
