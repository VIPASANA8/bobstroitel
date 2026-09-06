/* CUBE renderer, from CASE8 src/features/cube/game/canvasCube.ts.
   Projects the six faces, plans what to paint, and paints it. Everything here
   is a pure function of a pose and a clock except renderCanvasCube, which is
   the only thing that touches a context. Types dropped, nothing else. */
window.Poker8CubeCanvas = (() => {
  "use strict";

  const FACE_COLORS = {
    1: "#ff3daf", 2: "#21e8ff", 3: "#56f08c",
    4: "#ffe24b", 5: "#ff8b38", 6: "#ad66ff",
  };

  /** Which of the nine slots of a face carry a pip, shared with the face picker
      so the two never disagree. */
  const PIP_SLOTS = {
    1: [5], 2: [1, 9], 3: [1, 5, 9],
    4: [1, 3, 7, 9], 5: [1, 3, 5, 7, 9], 6: [1, 3, 4, 6, 7, 9],
  };

  const FACES = [
    { face: 1, normal: { x: 0, y: 0, z: 1 }, corners: [{ x: -1, y: -1, z: 1 }, { x: 1, y: -1, z: 1 }, { x: 1, y: 1, z: 1 }, { x: -1, y: 1, z: 1 }], point: (u, v) => ({ x: u, y: v, z: 1 }) },
    { face: 2, normal: { x: 1, y: 0, z: 0 }, corners: [{ x: 1, y: -1, z: 1 }, { x: 1, y: -1, z: -1 }, { x: 1, y: 1, z: -1 }, { x: 1, y: 1, z: 1 }], point: (u, v) => ({ x: 1, y: v, z: -u }) },
    { face: 3, normal: { x: 0, y: -1, z: 0 }, corners: [{ x: -1, y: -1, z: -1 }, { x: 1, y: -1, z: -1 }, { x: 1, y: -1, z: 1 }, { x: -1, y: -1, z: 1 }], point: (u, v) => ({ x: u, y: -1, z: v }) },
    { face: 4, normal: { x: 0, y: 1, z: 0 }, corners: [{ x: -1, y: 1, z: 1 }, { x: 1, y: 1, z: 1 }, { x: 1, y: 1, z: -1 }, { x: -1, y: 1, z: -1 }], point: (u, v) => ({ x: u, y: 1, z: -v }) },
    { face: 5, normal: { x: -1, y: 0, z: 0 }, corners: [{ x: -1, y: -1, z: -1 }, { x: -1, y: -1, z: 1 }, { x: -1, y: 1, z: 1 }, { x: -1, y: 1, z: -1 }], point: (u, v) => ({ x: -1, y: v, z: u }) },
    { face: 6, normal: { x: 0, y: 0, z: -1 }, corners: [{ x: 1, y: -1, z: -1 }, { x: -1, y: -1, z: -1 }, { x: -1, y: 1, z: -1 }, { x: 1, y: 1, z: -1 }], point: (u, v) => ({ x: -u, y: v, z: -1 }) },
  ];

  const TRAIL_LIFETIME_MS = 240;
  const TRAIL_MAX_SAMPLES = 16;
  const LIFT_SCREEN_FACTOR = 0.19;

  function appendTrailSample(history, sample, now) {
    const fresh = history.filter(item => now - item.at <= TRAIL_LIFETIME_MS);
    const previous = fresh.length ? fresh[fresh.length - 1] : undefined;
    const next = !sample.startsTrail && previous
      && Math.hypot(sample.x - previous.x, sample.y - previous.y) < 1.2
      ? fresh
      : [...fresh, sample];
    return next.slice(-TRAIL_MAX_SAMPLES);
  }

  function pipCapsuleLength(screenSpeed, profileStretch) {
    return Math.min(profileStretch, 1 + Math.max(0, screenSpeed) * 1.8);
  }

  function smoothScreenVelocity(previous, current, oldVelocity, elapsedMs) {
    const elapsed = Math.min(50, Math.max(8, elapsedMs));
    return {
      x: oldVelocity.x * 0.58 + (current.x - previous.x) / elapsed * 0.42,
      y: oldVelocity.y * 0.58 + (current.y - previous.y) / elapsed * 0.42,
    };
  }

  function buildTrailSegments(samples, now, strength) {
    const passes = { rear: [], front: [] };
    for (let index = 1; index < samples.length; index += 1) {
      const from = samples[index - 1];
      const to = samples[index];
      if (to.startsTrail) continue;
      const life = Math.max(0, 1 - (now - to.at) / TRAIL_LIFETIME_MS) * strength;
      if (life <= 0) continue;
      const target = (from.depth + to.depth) / 2 < 0 ? passes.rear : passes.front;
      target.push({ from, to, strength: life });
    }
    return passes;
  }

  function pruneHiddenPipState(visible, now, histories, velocities, previous) {
    for (const id of previous.keys()) {
      if (visible.has(id)) continue;
      previous.delete(id);
    }
    for (const id of velocities.keys()) if (!visible.has(id)) velocities.delete(id);
    for (const [id, history] of histories) {
      const latest = history.length ? history[history.length - 1] : undefined;
      if (!visible.has(id) && (!latest || now - latest.at > TRAIL_LIFETIME_MS)) histories.delete(id);
    }
  }

  function rotatePoint(point, rotation) {
    const xRadians = rotation.x * Math.PI / 180;
    const yRadians = rotation.y * Math.PI / 180;
    const cosX = Math.cos(xRadians);
    const sinX = Math.sin(xRadians);
    const cosY = Math.cos(yRadians);
    const sinY = Math.sin(yRadians);
    const afterX = {
      x: point.x,
      y: point.y * cosX - point.z * sinX,
      z: point.y * sinX + point.z * cosX,
    };
    return {
      x: afterX.x * cosY + afterX.z * sinY,
      y: afterX.y,
      z: -afterX.x * sinY + afterX.z * cosY,
    };
  }

  function projectPoint(point, pose, viewport) {
    const rotated = rotatePoint({
      x: point.x * pose.scale.x,
      y: point.y * pose.scale.y,
      z: point.z * pose.scale.z,
    }, pose.rotation);
    const half = viewport.size / 2;
    const factor = viewport.perspective / (viewport.perspective - rotated.z * half);
    return {
      x: viewport.width / 2 + rotated.x * half * factor,
      y: viewport.height / 2 - pose.lift * viewport.size * LIFT_SCREEN_FACTOR + rotated.y * half * factor,
      depth: rotated.z,
    };
  }

  function polygonArea(points) {
    return Math.abs(points.reduce((sum, point, index) => {
      const next = points[(index + 1) % points.length];
      return sum + point.x * next.y - next.x * point.y;
    }, 0)) / 2;
  }

  function projectFace(definition, pose, viewport) {
    const points = definition.corners.map(corner => projectPoint(corner, pose, viewport));
    return {
      face: definition.face,
      color: FACE_COLORS[definition.face],
      points,
      depth: points.reduce((sum, point) => sum + point.depth, 0) / points.length,
      visible: rotatePoint(definition.normal, pose.rotation).z > 0.001,
      screenArea: polygonArea(points),
    };
  }

  function buildCubeGeometry(pose, viewport) {
    const faces = FACES.map(definition => projectFace(definition, pose, viewport))
      .sort((left, right) => left.depth - right.depth);
    const visibleFaces = new Set(faces.filter(face => face.visible).map(face => face.face));
    const pips = FACES.flatMap(definition => PIP_SLOTS[definition.face].map(slot => {
      const column = (slot - 1) % 3;
      const row = Math.floor((slot - 1) / 3);
      const projected = projectPoint(definition.point((column - 1) * 0.5, (row - 1) * 0.5), pose, viewport);
      return {
        ...projected,
        id: `${definition.face}-${slot}`,
        face: definition.face,
        color: FACE_COLORS[definition.face],
        visible: visibleFaces.has(definition.face),
      };
    }));
    return { faces, pips };
  }

  const SWEEP_TRAVEL_MS = 1000;
  const SWEEP_PERIOD_MS = 2600;
  const RECOLOR_TRAVEL_MS = 520;
  const RECOLOR_WASH_MS = 700;
  /* Three passes of the impulse ride the borrowed colour, then it lets go --
     timed to the pass that has just finished, so the wash happens in the quiet
     between passes and never cuts a ring in flight. */
  const RECOLOR_HOLD_MS = SWEEP_PERIOD_MS * 2 + SWEEP_TRAVEL_MS;
  /** As long again after the colour goes home, the round is let go of entirely. */
  const RESULT_CLEAR_MS = RECOLOR_HOLD_MS * 2;
  /** The accent eases out inside the last quiet gap before that. */
  const EMPHASIS_FADE_MS = 900;

  const sweepProgressAt = sinceLanded => (sinceLanded % SWEEP_PERIOD_MS) / SWEEP_TRAVEL_MS;

  function recolorProgressAt(sinceLanded) {
    if (sinceLanded < RECOLOR_TRAVEL_MS) return Math.max(0, sinceLanded / RECOLOR_TRAVEL_MS);
    const washed = sinceLanded - RECOLOR_HOLD_MS;
    return washed <= 0 ? 1 : Math.max(0, 1 - washed / RECOLOR_WASH_MS);
  }

  function emphasisProgressAt(sinceLanded) {
    const leaving = sinceLanded - (RESULT_CLEAR_MS - EMPHASIS_FADE_MS);
    if (leaving > 0) return Math.max(0, 1 - leaving / EMPHASIS_FADE_MS);
    return Math.min(1, sinceLanded / SWEEP_TRAVEL_MS);
  }

  function mixColor(from, to, amount) {
    if (from === to || amount <= 0) return from;
    if (amount >= 1) return to;
    const channel = (hex, index) => parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16);
    const blend = index => Math.round(channel(from, index) + (channel(to, index) - channel(from, index)) * amount);
    return `rgb(${blend(0)}, ${blend(1)}, ${blend(2)})`;
  }

  function shadowCommand(input, geometry) {
    const groundedPoints = geometry.faces.flatMap(face => face.points.map(point => ({
      x: point.x,
      y: point.y + input.pose.lift * input.viewport.size * LIFT_SCREEN_FACTOR,
    })));
    const left = Math.min(...groundedPoints.map(point => point.x));
    const right = Math.max(...groundedPoints.map(point => point.x));
    const bottom = Math.max(...groundedPoints.map(point => point.y));
    const silhouetteWidth = right - left;
    const radiusX = Math.max(input.viewport.size * 0.72, silhouetteWidth * 0.6) * input.roll.shadowScale;
    const radiusY = Math.max(input.viewport.size * 0.21, silhouetteWidth * 0.13) * input.roll.shadowScale;
    return {
      kind: "shadow",
      center: {
        x: (left + right) / 2,
        y: Math.min(input.viewport.height - radiusY * 0.7, bottom + radiusY * 0.2),
        depth: 0,
      },
      radiusX,
      radiusY,
      alpha: Math.max(0.36, input.roll.shadowAlpha),
    };
  }

  /* The impulse is measured along the surface of the cube, in cube units,
     starting at the centre of the result face: its own edge sits at 1, the far
     edge of a neighbour at 3, and the centre of the opposite face at 4, where
     the fronts that went around every side meet again. */
  const WAVE_REACH = 4;
  const WAVE_HALF = 0.55;
  /** Far corners of a neighbour: two units past the shared edge, one off its middle. */
  const NEIGHBOUR_FAR = Math.hypot(3, 1);

  /** Corner indices each face shares with its neighbour, so the impulse can
      cross onto that face's own plane. */
  const SHARED_EDGES = new Map(
    FACES.flatMap(face => FACES.flatMap(other => {
      if (face.face === other.face) return [];
      const shared = face.corners.flatMap((corner, index) => (
        other.corners.some(point => point.x === corner.x && point.y === corner.y && point.z === corner.z)
          ? [index]
          : []
      ));
      return shared.length === 2 ? [[`${face.face}-${other.face}`, shared]] : [];
    })),
  );

  const midpoint = (left, right) => ({ x: (left.x + right.x) / 2, y: (left.y + right.y) / 2 });
  const between = (from, to) => ({ x: to.x - from.x, y: to.y - from.y });

  /** The front seen from one edge of a face, with its source `behind` units
      back once the face is unfolded flat. */
  function edgeWave(face, shared, behind, near, far) {
    const rest = [0, 1, 2, 3].filter(index => !shared.includes(index));
    const edge = midpoint(face.points[shared[0]], face.points[shared[1]]);
    const across = between(edge, midpoint(face.points[rest[0]], face.points[rest[1]]));
    const along = between(face.points[shared[0]], face.points[shared[1]]);
    const unit = { x: across.x / 2, y: across.y / 2 };
    return {
      origin: { x: edge.x - unit.x * behind, y: edge.y - unit.y * behind },
      u: { x: along.x / 2, y: along.y / 2 },
      v: unit,
      near,
      far,
    };
  }

  const FACE_EDGES = [[0, 1], [1, 2], [2, 3], [3, 0]];

  /* Where the impulse comes from on one face. On the result face it is the face
     centre; on a neighbour it is the same source seen after unfolding that face
     flat -- one unit behind the edge the two share. The opposite face shares no
     edge and no single source: a front comes over each of its four edges, three
     units back apiece, and they meet in its middle. */
  function faceWaves(face, resultFace) {
    if (face.face === resultFace) {
      const [, second, third, fourth] = face.points;
      const centre = {
        x: face.points.reduce((sum, point) => sum + point.x, 0) / face.points.length,
        y: face.points.reduce((sum, point) => sum + point.y, 0) / face.points.length,
      };
      return [{
        origin: centre,
        u: between(centre, midpoint(second, third)),
        v: between(centre, midpoint(third, fourth)),
        near: 0,
        far: Math.SQRT2,
      }];
    }
    // ponytail: each frame is affine, so a corner three units out drifts up to
    // ~0.2 units against its neighbour under strong perspective; a homography
    // per face would close that.
    const shared = SHARED_EDGES.get(`${face.face}-${resultFace}`);
    if (shared) return [edgeWave(face, shared, 1, 1, NEIGHBOUR_FAR)];
    return FACE_EDGES.map(edge => edgeWave(face, edge, 3, 3, WAVE_REACH));
  }

  const waveAmount = (wave, radius) => Math.min(1, Math.max(0, (radius - wave.near) / (wave.far - wave.near)));

  /* Colour and emphasis every face carries right now: the impulse repaints the
     body into the result colour as it passes, lifting the result face and
     easing the rest down behind the front. */
  function faceAccents(faces, resultFace, recolor, emphasis = recolor) {
    const accents = new Map();
    if (resultFace === null || (recolor <= 0 && emphasis <= 0)) return accents;
    const painted = Math.min(1, recolor) * WAVE_REACH;
    const settled = Math.min(1, emphasis) * WAVE_REACH;
    for (const face of faces) {
      const [wave] = faceWaves(face, resultFace);
      const amount = radius => waveAmount(wave, radius);
      const shade = amount(settled);
      accents.set(face.face, {
        color: mixColor(FACE_COLORS[face.face], FACE_COLORS[resultFace], amount(painted)),
        emphasis: face.face === resultFace ? shade : -shade,
      });
    }
    return accents;
  }

  /** One ring of the result colour riding the impulse across every visible
      face, each around its own source. */
  function sweepCommands(faces, resultFace, progress) {
    if (progress < 0 || progress > 1) return [];
    const radius = progress * WAVE_REACH;
    const alpha = Math.min(1, (1 - Math.abs(progress * 2 - 1)) * 2.2);

    return faces.filter(face => face.visible).flatMap(face => (
      faceWaves(face, resultFace).flatMap(wave => {
        if (radius + WAVE_HALF < wave.near || radius - WAVE_HALF > wave.far) return [];
        // An edge-on face has no frame to draw the front through, and its
        // sliver of screen shows nothing anyway.
        if (Math.abs(wave.u.x * wave.v.y - wave.u.y * wave.v.x) < 1) return [];
        return [{
          kind: "sweep",
          face,
          color: FACE_COLORS[resultFace],
          alpha,
          wave,
          inner: Math.max(0, radius - WAVE_HALF),
          outer: radius + WAVE_HALF,
        }];
      })
    ));
  }

  function pulseCommands(pips, faces, progress, resultFace) {
    if (progress < 0 || progress > 1) return [];
    return pips
      .filter(pip => pip.visible && (resultFace === null || pip.face === resultFace))
      .flatMap(pip => {
        const face = faces.find(item => item.face === pip.face);
        return face ? [{ kind: "pulse", pip, face, progress }] : [];
      });
  }

  function buildRenderPlan(input) {
    const geometry = buildCubeGeometry(input.pose, input.viewport);
    const resultFace = input.resultFace ?? null;
    const accents = faceAccents(geometry.faces, resultFace, input.recolorProgress ?? 0, input.emphasisProgress);
    const accentOf = face => accents.get(face) || { color: FACE_COLORS[face], emphasis: 0 };
    const toneOf = face => accentOf(face).color;
    const rear = [];
    const front = [];
    const pips = [];

    for (const pip of geometry.pips.filter(item => item.visible || input.histories.has(item.id))) {
      const velocity = input.velocities.get(pip.id) || { x: 0, y: 0 };
      const color = toneOf(pip.face);
      const passes = buildTrailSegments(input.histories.get(pip.id) || [], input.now, input.roll.trailStrength);
      if (!pip.visible) {
        const segments = [...passes.rear, ...passes.front];
        if (segments.length) rear.push({ kind: "rear-trail", color, segments });
        continue;
      }
      if (passes.rear.length) rear.push({ kind: "rear-trail", color, segments: passes.rear });
      if (passes.front.length) front.push({
        face: pip.face,
        command: { kind: "front-trail", color, segments: passes.front },
      });
      pips.push({
        face: pip.face,
        command: {
          kind: "pip",
          pip,
          color,
          velocity,
          stretch: pipCapsuleLength(Math.hypot(velocity.x, velocity.y), input.roll.pipStretch),
          glow: input.roll.glow,
        },
      });
    }

    // Faces come back sorted from far to near, so the last visible one is what
    // the cube shows in front.
    const visible = geometry.faces.filter(face => face.visible);
    const frontFace = visible.length ? visible[visible.length - 1] : null;
    const pulses = pulseCommands(geometry.pips, geometry.faces, input.pulseProgress, resultFace);
    const sweeps = resultFace === null
      ? []
      : sweepCommands(geometry.faces, resultFace, input.sweepProgress ?? 2);

    return {
      geometry,
      viewport: input.viewport,
      commands: [
        shadowCommand(input, geometry),
        ...rear,
        ...geometry.faces
          .filter(face => face.visible)
          .flatMap((face, index) => {
            const accent = accentOf(face.face);
            return [
              { kind: "face", face, color: accent.color, light: 0.58 + index * 0.16, emphasis: accent.emphasis },
              ...sweeps.filter(command => command.face.face === face.face),
              ...front.filter(item => item.face === face.face).map(item => item.command),
              ...pips.filter(item => item.face === face.face).map(item => item.command),
              ...pulses.filter(command => command.pip.face === face.face),
            ];
          }),
        // The result face owns the brightest lines on the cube, so nothing
        // painted after it may dim them -- but only while it is the face in
        // front. Turned aside it sits behind another one, and repainting its
        // outline on top would draw it straight through the cube.
        ...(frontFace !== null && frontFace.face === resultFace
          ? [{
            kind: "edge",
            face: frontFace,
            color: accentOf(frontFace.face).color,
            emphasis: accentOf(frontFace.face).emphasis,
          }]
          : []),
      ],
    };
  }

  function roundedPolygonPath(context, points, radius) {
    const corners = points.map((point, index) => {
      const previous = points[(index + points.length - 1) % points.length];
      const next = points[(index + 1) % points.length];
      const previousLength = Math.hypot(previous.x - point.x, previous.y - point.y);
      const nextLength = Math.hypot(next.x - point.x, next.y - point.y);
      const inset = Math.min(radius, previousLength * 0.12, nextLength * 0.12);
      return {
        point,
        start: {
          x: point.x + (previous.x - point.x) / previousLength * inset,
          y: point.y + (previous.y - point.y) / previousLength * inset,
        },
        end: {
          x: point.x + (next.x - point.x) / nextLength * inset,
          y: point.y + (next.y - point.y) / nextLength * inset,
        },
      };
    });
    context.beginPath();
    context.moveTo(corners[0].start.x, corners[0].start.y);
    for (const corner of corners) {
      context.lineTo(corner.start.x, corner.start.y);
      context.quadraticCurveTo(corner.point.x, corner.point.y, corner.end.x, corner.end.y);
    }
    context.closePath();
  }

  function drawShadow(context, command) {
    context.save();
    context.translate(command.center.x, command.center.y);
    context.scale(1, command.radiusY / command.radiusX);
    const gradient = context.createRadialGradient(0, 0, 0, 0, 0, command.radiusX);
    gradient.addColorStop(0, `rgba(86, 104, 114, ${command.alpha * 0.65})`);
    gradient.addColorStop(0.62, `rgba(48, 58, 64, ${command.alpha * 0.28})`);
    gradient.addColorStop(1, "rgba(48, 58, 64, 0)");
    context.fillStyle = gradient;
    context.beginPath();
    context.arc(0, 0, command.radiusX, 0, Math.PI * 2);
    context.fill();
    context.restore();

    context.save();
    context.translate(command.center.x, command.center.y - command.radiusY * 0.12);
    context.scale(1, command.radiusY / command.radiusX * 0.45);
    const contactRadius = command.radiusX * 0.56;
    const contact = context.createRadialGradient(0, 0, 0, 0, 0, contactRadius);
    contact.addColorStop(0, `rgba(0, 0, 0, ${command.alpha * 1.35})`);
    contact.addColorStop(0.58, `rgba(0, 0, 0, ${command.alpha * 0.7})`);
    contact.addColorStop(1, "rgba(0, 0, 0, 0)");
    context.fillStyle = contact;
    context.beginPath();
    context.arc(0, 0, contactRadius, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  function drawTrail(context, command) {
    context.save();
    context.lineCap = "round";
    context.lineJoin = "round";
    // The wide translucent pass is the glow. Canvas shadows here cost more than
    // the whole cube on a phone, and there are dozens of segments in flight, so
    // the halo is painted rather than blurred.
    for (const pass of [{ width: 20, alpha: 0.13 }, { width: 3, alpha: 0.9 }]) {
      context.lineWidth = pass.width;
      context.strokeStyle = command.color;
      for (const segment of command.segments) {
        context.globalAlpha = pass.alpha * segment.strength;
        context.beginPath();
        context.moveTo(segment.from.x, segment.from.y);
        context.lineTo(segment.to.x, segment.to.y);
        context.stroke();
      }
    }
    context.restore();
  }

  function graphiteFaceTones(light) {
    const top = Math.round(30 + light * 12);
    const bottom = Math.round(13 + light * 7);
    return {
      top: `rgb(${top}, ${top + 6}, ${top + 11})`,
      bottom: `rgb(${bottom}, ${bottom + 5}, ${bottom + 9})`,
    };
  }

  const PLAIN_STYLE = { lightScale: 1, edgeAlpha: 0.82, edgeWidth: 2, edgeBlur: 9 };
  const ACCENT_STYLE = { lightScale: 1.1, edgeAlpha: 1, edgeWidth: 2.8, edgeBlur: 19 };
  const DIM_STYLE = { lightScale: 0.48, edgeAlpha: 0.3, edgeWidth: 1.5, edgeBlur: 3 };

  /** -1 fully dimmed, 0 untouched, 1 fully accented: the impulse slides a face
      between them instead of switching. */
  function emphasisStyle(emphasis) {
    const target = emphasis < 0 ? DIM_STYLE : ACCENT_STYLE;
    const amount = Math.min(1, Math.abs(emphasis));
    const slide = key => PLAIN_STYLE[key] + (target[key] - PLAIN_STYLE[key]) * amount;
    return {
      lightScale: slide("lightScale"),
      edgeAlpha: slide("edgeAlpha"),
      edgeWidth: slide("edgeWidth"),
      edgeBlur: slide("edgeBlur"),
    };
  }

  /** Strokes the neon line of the path already on the context: the colour pass,
      then the white inner highlight. */
  function strokeFaceEdge(context, color, style) {
    context.lineJoin = "round";
    context.lineWidth = style.edgeWidth;
    context.strokeStyle = color;
    context.shadowColor = color;
    context.shadowBlur = style.edgeBlur;
    context.globalAlpha = style.edgeAlpha;
    context.stroke();
    context.shadowBlur = 0;
    context.lineWidth = 0.7;
    context.strokeStyle = "rgba(255, 255, 255, 0.28)";
    context.globalAlpha = 0.55 * style.edgeAlpha;
    context.stroke();
  }

  function drawEdge(context, command) {
    context.save();
    roundedPolygonPath(context, command.face.points, 7);
    // Clipped to its own face: the line keeps the brightest word on the shared
    // edges without its glow spilling over the faces around it, which reads as
    // the result face showing through them.
    context.clip();
    strokeFaceEdge(context, command.color, emphasisStyle(command.emphasis));
    context.restore();
  }

  function drawFace(context, command) {
    const { face, light } = command;
    const style = emphasisStyle(command.emphasis);
    const tones = graphiteFaceTones(light * style.lightScale);
    const gradient = context.createLinearGradient(face.points[0].x, face.points[0].y, face.points[2].x, face.points[2].y);
    gradient.addColorStop(0, tones.top);
    gradient.addColorStop(1, tones.bottom);

    context.save();
    roundedPolygonPath(context, face.points, 7);
    context.globalAlpha = 1;
    context.fillStyle = gradient;
    context.fill();
    context.save();
    context.clip();
    const left = Math.min(...face.points.map(point => point.x));
    const top = Math.min(...face.points.map(point => point.y));
    const width = Math.max(...face.points.map(point => point.x)) - left;
    const height = Math.max(...face.points.map(point => point.y)) - top;
    context.fillStyle = "rgba(255, 255, 255, 0.035)";
    for (let index = 0; index < 10; index += 1) {
      const xHash = Math.sin((face.face * 17 + index) * 12.9898) * 43758.5453;
      const yHash = Math.sin((face.face * 29 + index) * 78.233) * 43758.5453;
      context.fillRect(
        left + (xHash - Math.floor(xHash)) * width,
        top + (yHash - Math.floor(yHash)) * height,
        1,
        1,
      );
    }
    context.restore();
    strokeFaceEdge(context, command.color, style);
    context.restore();
  }

  function drawSweep(context, command) {
    const { face, wave } = command;
    context.save();
    roundedPolygonPath(context, face.points, 7);
    context.clip();
    context.globalCompositeOperation = "lighter";
    context.globalAlpha = command.alpha;
    // Draw the front in the face's own frame: a round wave there is the ellipse
    // the tilted face actually shows.
    context.transform(wave.u.x, wave.u.y, wave.v.x, wave.v.y, wave.origin.x, wave.origin.y);
    const gradient = context.createRadialGradient(0, 0, command.inner, 0, 0, command.outer);
    gradient.addColorStop(0, `${command.color}00`);
    gradient.addColorStop(0.5, `${command.color}b0`);
    gradient.addColorStop(1, `${command.color}00`);
    context.fillStyle = gradient;
    // Everything past the ring is transparent, so painting its own square is
    // both enough and the least work.
    context.fillRect(-command.outer, -command.outer, command.outer * 2, command.outer * 2);
    context.restore();
  }

  function drawPip(context, command) {
    const radius = 6.4 * Math.max(0.78, 1 + command.pip.depth * 0.08);
    const speed = Math.hypot(command.velocity.x, command.velocity.y);
    const direction = speed > 0.01
      ? { x: command.velocity.x / speed, y: command.velocity.y / speed }
      : { x: 0, y: 0 };
    const tail = radius * (command.stretch - 1) * 2.2;
    const from = {
      x: command.pip.x - direction.x * tail,
      y: command.pip.y - direction.y * tail,
    };

    // At rest the tail is zero, and a zero-length stroke with a round cap is a
    // dot on Chrome but nothing on iOS WebKit -- the pips vanish or flicker. So
    // a still pip is a filled circle; only a moving one, which has a real
    // length, is stroked into a capsule.
    const moving = Math.hypot(command.pip.x - from.x, command.pip.y - from.y) > 0.5;

    const dab = width => {
      context.lineWidth = width;
      context.beginPath();
      if (moving) {
        context.moveTo(from.x, from.y);
        context.lineTo(command.pip.x, command.pip.y);
        context.stroke();
      } else {
        context.arc(command.pip.x, command.pip.y, width / 2, 0, Math.PI * 2);
        context.fill();
      }
    };

    context.save();
    context.lineCap = "round";
    context.strokeStyle = command.color;
    context.fillStyle = command.color;
    context.shadowColor = command.color;
    context.globalAlpha = 0.38;
    context.shadowBlur = 18 * command.glow;
    dab(radius * 2.15);
    context.globalAlpha = 1;
    context.shadowBlur = 8 * command.glow;
    dab(radius * 1.35);
    context.restore();
  }

  function drawPulse(context, command) {
    const radius = 8 + command.progress * 20;
    context.save();
    // Held inside its own face: an expanding ring is wider than the face it
    // belongs to and would otherwise spill past the cube's silhouette.
    roundedPolygonPath(context, command.face.points, 7);
    context.clip();
    context.globalAlpha = (1 - command.progress) * 0.7;
    context.strokeStyle = command.pip.color;
    context.shadowColor = command.pip.color;
    context.shadowBlur = 12;
    context.lineWidth = 2.4 * (1 - command.progress) + 0.5;
    context.beginPath();
    context.arc(command.pip.x, command.pip.y, radius, 0, Math.PI * 2);
    context.stroke();
    context.restore();
  }

  function renderCanvasCube(context, plan) {
    context.clearRect(0, 0, plan.viewport.width, plan.viewport.height);
    for (const command of plan.commands) {
      if (command.kind === "shadow") drawShadow(context, command);
      else if (command.kind === "rear-trail" || command.kind === "front-trail") drawTrail(context, command);
      else if (command.kind === "face") drawFace(context, command);
      else if (command.kind === "edge") drawEdge(context, command);
      else if (command.kind === "sweep") drawSweep(context, command);
      else if (command.kind === "pip") drawPip(context, command);
      else drawPulse(context, command);
    }
  }

  return {
    FACE_COLORS, PIP_SLOTS, RESULT_CLEAR_MS,
    appendTrailSample, buildCubeGeometry, buildRenderPlan, pruneHiddenPipState,
    emphasisProgressAt, recolorProgressAt, renderCanvasCube, smoothScreenVelocity,
    sweepProgressAt,
  };
})();
