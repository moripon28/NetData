(() => {
  "use strict";

  const COLORS = {
    mint: [0.612, 1, 0.808, 1],
    cyan: [0.298, 0.906, 0.859, 1],
    violet: [0.655, 0.545, 0.98, 1],
    orange: [1, 0.714, 0.361, 1],
    danger: [1, 0.4, 0.478, 1],
    muted: [0.34, 0.43, 0.4, 1],
  };

  const TAU = Math.PI * 2;
  const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
  const INITIAL_YAW = 0.26;
  const INITIAL_PITCH = 0.48;
  const MIN_PITCH = -0.85;
  const MAX_PITCH = 1.05;
  const LABEL_MARGIN = 10;
  const LABEL_GAP = 7;
  const LABEL_RESERVED_SELECTORS = [
    ".topology-scene-meta",
    ".llm-flavor-stream",
    ".topology-inspector",
    ".topology-legend",
  ];

  function statusColor(node) {
    const status = String(node.status || "unknown").toLowerCase();
    if (["error", "critical", "anomaly"].includes(status)) return COLORS.danger;
    if (["warning", "degraded", "checking", "learning"].includes(status)) return COLORS.orange;
    if (["offline", "unreachable", "disabled", "unknown"].includes(status)) return COLORS.muted;
    if (node.role === "qnap") return COLORS.violet;
    if (["gateway", "exporter"].includes(node.role)) return COLORS.cyan;
    return COLORS.mint;
  }

  function layoutNodes(nodes) {
    const groups = { core: [], infrastructure: [], telemetry: [], devices: [] };
    nodes.forEach((node) => {
      if (node.role === "core") groups.core.push(node);
      else if (["gateway", "qnap"].includes(node.role)) groups.infrastructure.push(node);
      else if (["agent", "exporter"].includes(node.role)) groups.telemetry.push(node);
      else groups.devices.push(node);
    });

    groups.core.forEach((node) => { node.position = [0, 0, 0]; });
    const place = (items, radius, phase, verticalScale) => {
      items.forEach((node, index) => {
        const angle = phase + (index / Math.max(1, items.length)) * TAU;
        node.position = [
          Math.cos(angle) * radius,
          Math.sin(angle * 2 + phase) * verticalScale,
          Math.sin(angle) * radius * 0.68,
        ];
      });
    };
    place(groups.infrastructure, 2.15, -0.62, 0.48);
    place(groups.telemetry, 3.05, 0.3, 0.78);
    place(groups.devices, 3.85, -0.1, 1.05);
    return nodes;
  }

  function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(shader) || "Unknown shader compilation error";
      gl.deleteShader(shader);
      throw new Error(message);
    }
    return shader;
  }

  function createProgram(gl, vertexSource, fragmentSource) {
    const program = gl.createProgram();
    gl.attachShader(program, createShader(gl, gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, createShader(gl, gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || "WebGL link failed");
    return program;
  }

  function create({ canvas, labelLayer, onSelect, onModeChange }) {
    if (!canvas || !labelLayer) return null;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let nodes = [];
    let selectedId = null;
    let frame = 0;
    let lastFrameAt = 0;
    let yawOffset = INITIAL_YAW;
    let pitchOffset = INITIAL_PITCH;
    let dragStart = null;
    let dragDistance = 0;
    let projectedNodes = [];
    const labels = new Map();
    const gl = canvas.getContext("webgl", { alpha: true, antialias: true, premultipliedAlpha: false, powerPreference: "high-performance" });
    const context2d = gl ? null : canvas.getContext("2d");
    let lineProgram = null;
    let pointProgram = null;
    let lineBuffer = null;
    let pointBuffer = null;

    if (gl) {
      const lineVertex = `
        attribute vec2 a_position;
        attribute vec4 a_color;
        varying vec4 v_color;
        void main() { gl_Position = vec4(a_position, 0.0, 1.0); v_color = a_color; }
      `;
      const lineFragment = `
        precision mediump float;
        varying vec4 v_color;
        void main() { gl_FragColor = v_color; }
      `;
      const pointVertex = `
        attribute vec2 a_position;
        attribute float a_size;
        attribute vec4 a_color;
        varying vec4 v_color;
        void main() { gl_Position = vec4(a_position, 0.0, 1.0); gl_PointSize = a_size; v_color = a_color; }
      `;
      const pointFragment = `
        precision mediump float;
        varying vec4 v_color;
        void main() {
          float distanceFromCenter = length(gl_PointCoord - vec2(0.5));
          float edge = 1.0 - smoothstep(0.28, 0.5, distanceFromCenter);
          float core = 1.0 - smoothstep(0.0, 0.17, distanceFromCenter);
          gl_FragColor = vec4(v_color.rgb, v_color.a * (edge * 0.46 + core * 0.84));
        }
      `;
      try {
        lineProgram = createProgram(gl, lineVertex, lineFragment);
        pointProgram = createProgram(gl, pointVertex, pointFragment);
        lineBuffer = gl.createBuffer();
        pointBuffer = gl.createBuffer();
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      } catch (error) {
        console.warn("WebGL topology initialization failed", error);
      }
    }

    const webglReady = Boolean(gl && lineProgram && pointProgram);
    onModeChange?.(webglReady ? "webgl" : "fallback");

    function dimensions() {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(1.5, window.devicePixelRatio || 1);
      const pixelWidth = Math.max(1, Math.floor(rect.width * dpr));
      const pixelHeight = Math.max(1, Math.floor(rect.height * dpr));
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
      }
      if (webglReady) gl.viewport(0, 0, pixelWidth, pixelHeight);
      return { width: rect.width, height: rect.height, dpr };
    }

    function rotateWorld(position, yaw, pitch) {
      const yawCosine = Math.cos(yaw);
      const yawSine = Math.sin(yaw);
      const x = position[0] * yawCosine - position[2] * yawSine;
      const z = position[0] * yawSine + position[2] * yawCosine;
      const pitchCosine = Math.cos(pitch);
      const pitchSine = Math.sin(pitch);
      return [x, position[1] * pitchCosine - z * pitchSine, position[1] * pitchSine + z * pitchCosine];
    }

    function project(position, view, size) {
      const world = rotateWorld(position, view.yaw, view.pitch);
      const cameraDistance = 8.2;
      const depth = cameraDistance - world[2];
      const focal = 2.25;
      const aspect = Math.max(0.55, size.width / Math.max(1, size.height));
      const x = (world[0] * focal / depth) / aspect;
      const y = world[1] * focal / depth;
      return {
        x, y,
        screenX: (x * 0.5 + 0.5) * size.width,
        screenY: (0.5 - y * 0.5) * size.height,
        depth,
        scale: clamp(cameraDistance / depth, 0.55, 1.8),
        visible: depth > 1 && Math.abs(x) < 1.2 && Math.abs(y) < 1.2,
      };
    }

    function appendLine(target, first, second, color, alpha = 1) {
      if (!first.visible || !second.visible) return;
      target.push(first.x, first.y, color[0], color[1], color[2], alpha, second.x, second.y, color[0], color[1], color[2], alpha);
    }

    function appendScreenRing(target, projected, radiusPixels, color, alpha, size) {
      const segments = 28;
      for (let index = 0; index < segments; index += 1) {
        const start = index / segments * TAU;
        const end = (index + 1) / segments * TAU;
        const xScale = 2 / Math.max(1, size.width);
        const yScale = 2 / Math.max(1, size.height);
        const first = { x: projected.x + Math.cos(start) * radiusPixels * xScale, y: projected.y + Math.sin(start) * radiusPixels * yScale, visible: true };
        const second = { x: projected.x + Math.cos(end) * radiusPixels * xScale, y: projected.y + Math.sin(end) * radiusPixels * yScale, visible: true };
        appendLine(target, first, second, color, alpha);
      }
    }

    function buildScene(now, size) {
      const view = {
        yaw: yawOffset + (reducedMotion.matches ? 0 : now * 0.000035),
        pitch: pitchOffset,
      };
      const lines = [];
      const points = [];
      const ringColor = COLORS.cyan;

      const addWorldRing = (radius, axis, alpha, phase = 0) => {
        const segments = 96;
        for (let index = 0; index < segments; index += 1) {
          const angles = [(index / segments) * TAU + phase, ((index + 1) / segments) * TAU + phase];
          const worldPoints = angles.map((angle) => {
            if (axis === "xy") return [Math.cos(angle) * radius, Math.sin(angle) * radius, 0];
            if (axis === "yz") return [0, Math.cos(angle) * radius, Math.sin(angle) * radius];
            return [Math.cos(angle) * radius, 0, Math.sin(angle) * radius];
          });
          appendLine(lines, project(worldPoints[0], view, size), project(worldPoints[1], view, size), ringColor, alpha);
        }
      };

      addWorldRing(1.02, "xy", 0.14);
      addWorldRing(1.02, "yz", 0.11);
      addWorldRing(1.02, "xz", 0.18);
      addWorldRing(1.42, "xz", 0.12, now * 0.00008);
      addWorldRing(2.15, "xz", 0.075);
      addWorldRing(3.08, "xz", 0.055, 0.18);
      addWorldRing(3.86, "xz", 0.035, -0.16);

      [-0.62, -0.31, 0.31, 0.62].forEach((latitude) => {
        const radius = Math.cos(latitude) * 1.02;
        const y = Math.sin(latitude) * 1.02;
        const segments = 54;
        for (let index = 0; index < segments; index += 1) {
          const start = index / segments * TAU;
          const end = (index + 1) / segments * TAU;
          appendLine(lines, project([Math.cos(start) * radius, y, Math.sin(start) * radius], view, size), project([Math.cos(end) * radius, y, Math.sin(end) * radius], view, size), COLORS.mint, 0.055);
        }
      });

      projectedNodes = nodes.map((node) => ({ node, projected: project(node.position, view, size) }));
      const coreProjection = project([0, 0, 0], view, size);

      projectedNodes.forEach(({ node, projected }, index) => {
        const color = statusColor(node);
        if (node.role !== "core") appendLine(lines, coreProjection, projected, color, node.status === "offline" ? 0.08 : 0.19);

        if (node.role !== "core" && !["offline", "unreachable", "disabled"].includes(String(node.status).toLowerCase())) {
          const particleCount = node.role === "device" ? 1 : 2;
          for (let particleIndex = 0; particleIndex < particleCount; particleIndex += 1) {
            const progress = ((now * (0.0001 + particleIndex * 0.000025) + index * 0.173 + particleIndex * 0.41) % 1);
            const world = node.position.map((value) => value * progress);
            const particle = project(world, view, size);
            points.push(particle.x, particle.y, 5.5 * particle.scale, color[0], color[1], color[2], 0.72);
          }
        }

        const baseSize = node.role === "core" ? 48 : node.role === "gateway" ? 25 : node.role === "device" ? 13 : 18;
        points.push(projected.x, projected.y, baseSize * 1.85 * projected.scale, color[0], color[1], color[2], 0.13);
        points.push(projected.x, projected.y, baseSize * projected.scale, color[0], color[1], color[2], 0.92);
        if (node.id === selectedId) appendScreenRing(lines, projected, baseSize * 0.72 * projected.scale, color, 0.78, size);
      });

      const scanY = Math.sin(now * 0.00045) * 0.88;
      const scanRadius = Math.sqrt(Math.max(0.1, 1.02 * 1.02 - scanY * scanY));
      const segments = 48;
      for (let index = 0; index < segments; index += 1) {
        const start = index / segments * TAU;
        const end = (index + 1) / segments * TAU;
        appendLine(lines, project([Math.cos(start) * scanRadius, scanY, Math.sin(start) * scanRadius], view, size), project([Math.cos(end) * scanRadius, scanY, Math.sin(end) * scanRadius], view, size), COLORS.cyan, 0.34);
      }

      return { lines, points };
    }

    function drawWebgl(scene, size) {
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.useProgram(lineProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, lineBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(scene.lines), gl.DYNAMIC_DRAW);
      const linePosition = gl.getAttribLocation(lineProgram, "a_position");
      const lineColor = gl.getAttribLocation(lineProgram, "a_color");
      gl.enableVertexAttribArray(linePosition);
      gl.enableVertexAttribArray(lineColor);
      gl.vertexAttribPointer(linePosition, 2, gl.FLOAT, false, 24, 0);
      gl.vertexAttribPointer(lineColor, 4, gl.FLOAT, false, 24, 8);
      gl.drawArrays(gl.LINES, 0, scene.lines.length / 6);

      gl.useProgram(pointProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, pointBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(scene.points), gl.DYNAMIC_DRAW);
      const pointPosition = gl.getAttribLocation(pointProgram, "a_position");
      const pointSize = gl.getAttribLocation(pointProgram, "a_size");
      const pointColor = gl.getAttribLocation(pointProgram, "a_color");
      gl.enableVertexAttribArray(pointPosition);
      gl.enableVertexAttribArray(pointSize);
      gl.enableVertexAttribArray(pointColor);
      gl.vertexAttribPointer(pointPosition, 2, gl.FLOAT, false, 28, 0);
      gl.vertexAttribPointer(pointSize, 1, gl.FLOAT, false, 28, 8);
      gl.vertexAttribPointer(pointColor, 4, gl.FLOAT, false, 28, 12);
      gl.drawArrays(gl.POINTS, 0, scene.points.length / 7);
    }

    function drawFallback(scene, size) {
      if (!context2d) return;
      context2d.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
      context2d.clearRect(0, 0, size.width, size.height);
      context2d.lineWidth = 1;
      for (let index = 0; index < scene.lines.length; index += 12) {
        const x1 = (scene.lines[index] * 0.5 + 0.5) * size.width;
        const y1 = (0.5 - scene.lines[index + 1] * 0.5) * size.height;
        const x2 = (scene.lines[index + 6] * 0.5 + 0.5) * size.width;
        const y2 = (0.5 - scene.lines[index + 7] * 0.5) * size.height;
        context2d.strokeStyle = `rgba(${scene.lines[index + 2] * 255},${scene.lines[index + 3] * 255},${scene.lines[index + 4] * 255},${scene.lines[index + 5]})`;
        context2d.beginPath(); context2d.moveTo(x1, y1); context2d.lineTo(x2, y2); context2d.stroke();
      }
      for (let index = 0; index < scene.points.length; index += 7) {
        const x = (scene.points[index] * 0.5 + 0.5) * size.width;
        const y = (0.5 - scene.points[index + 1] * 0.5) * size.height;
        const radius = scene.points[index + 2] * 0.32;
        context2d.fillStyle = `rgba(${scene.points[index + 3] * 255},${scene.points[index + 4] * 255},${scene.points[index + 5] * 255},${scene.points[index + 6]})`;
        context2d.beginPath(); context2d.arc(x, y, radius, 0, TAU); context2d.fill();
      }
    }

    function intersectionArea(first, second, padding = 0) {
      const width = Math.min(first.right + padding, second.right + padding) - Math.max(first.left - padding, second.left - padding);
      const height = Math.min(first.bottom + padding, second.bottom + padding) - Math.max(first.top - padding, second.top - padding);
      return width > 0 && height > 0 ? width * height : 0;
    }

    function reservedLabelRects(stageRect) {
      return LABEL_RESERVED_SELECTORS.flatMap((selector) => {
        const element = interactionSurface.querySelector(selector);
        if (!element || element.hidden || getComputedStyle(element).display === "none") return [];
        const rect = element.getBoundingClientRect();
        return [{
          left: rect.left - stageRect.left,
          top: rect.top - stageRect.top,
          right: rect.right - stageRect.left,
          bottom: rect.bottom - stageRect.top,
        }];
      });
    }

    function labelCandidates(anchor, width, height, size) {
      const angles = [0, -Math.PI / 4, Math.PI / 4, Math.PI, -Math.PI * 3 / 4, Math.PI * 3 / 4, -Math.PI / 2, Math.PI / 2];
      const candidates = [];
      const seen = new Set();
      for (let ring = 0; ring < 7; ring += 1) {
        angles.forEach((angle) => {
          const horizontalDistance = LABEL_GAP + width / 2 + ring * 30;
          const verticalDistance = LABEL_GAP + height / 2 + ring * 24;
          const rawX = anchor.x + Math.cos(angle) * horizontalDistance - width / 2;
          const rawY = anchor.y + Math.sin(angle) * verticalDistance - height / 2;
          const x = clamp(rawX, LABEL_MARGIN, Math.max(LABEL_MARGIN, size.width - LABEL_MARGIN - width));
          const y = clamp(rawY, LABEL_MARGIN, Math.max(LABEL_MARGIN, size.height - LABEL_MARGIN - height));
          const key = `${Math.round(x)}:${Math.round(y)}`;
          if (seen.has(key)) return;
          seen.add(key);
          candidates.push({
            x, y,
            edgePenalty: Math.abs(rawX - x) + Math.abs(rawY - y),
            distance: Math.hypot(x + width / 2 - anchor.x, y + height / 2 - anchor.y),
          });
        });
      }
      return candidates;
    }

    function findLabelPlacement(anchor, width, height, size, occupied, reserved, previous) {
      let best = null;
      labelCandidates(anchor, width, height, size).forEach((candidate) => {
        const rect = { left: candidate.x, top: candidate.y, right: candidate.x + width, bottom: candidate.y + height };
        const occupiedOverlap = occupied.reduce((total, item) => total + intersectionArea(rect, item, LABEL_GAP), 0);
        const reservedOverlap = reserved.reduce((total, item) => total + intersectionArea(rect, item, LABEL_GAP + 2), 0);
        const movement = previous ? Math.hypot(candidate.x - previous.x, candidate.y - previous.y) : 0;
        const score = occupiedOverlap * 900 + reservedOverlap * 1500 + candidate.edgePenalty * 30 + candidate.distance + movement * 0.08;
        if (!best || score < best.score) best = { ...candidate, rect, score };
      });
      return best;
    }

    function updateLabelLeader(label, placement, anchor, width, height) {
      const centerX = placement.x + width / 2;
      const centerY = placement.y + height / 2;
      const deltaX = anchor.x - centerX;
      const deltaY = anchor.y - centerY;
      const normalizedDistance = Math.max(Math.abs(deltaX) / Math.max(1, width / 2), Math.abs(deltaY) / Math.max(1, height / 2));
      const edgeScale = normalizedDistance > 1 ? 1 / normalizedDistance : 1;
      const edgeX = centerX + deltaX * edgeScale;
      const edgeY = centerY + deltaY * edgeScale;
      const leaderX = anchor.x - edgeX;
      const leaderY = anchor.y - edgeY;
      label.style.setProperty("--leader-left", `${edgeX - placement.x}px`);
      label.style.setProperty("--leader-top", `${edgeY - placement.y}px`);
      label.style.setProperty("--leader-length", `${Math.hypot(leaderX, leaderY)}px`);
      label.style.setProperty("--leader-angle", `${Math.atan2(leaderY, leaderX)}rad`);
    }

    function updateLabelPositions(size) {
      const stageRect = interactionSurface.getBoundingClientRect();
      const ordered = projectedNodes
        .filter(({ projected }) => projected.visible)
        .sort((first, second) => {
          if (first.node.id === selectedId) return -1;
          if (second.node.id === selectedId) return 1;
          if (first.node.role === "core") return -1;
          if (second.node.role === "core") return 1;
          return first.projected.depth - second.projected.depth;
        });

      projectedNodes.forEach(({ node, projected }) => {
        const label = labels.get(node.id);
        if (!label) return;
        label.hidden = !projected.visible;
        label.classList.toggle("is-back", projected.depth > 8.45 && node.id !== selectedId);
      });

      const reserved = reservedLabelRects(stageRect);
      const occupied = [];
      const measured = ordered.map(({ node, projected }) => {
        const label = labels.get(node.id);
        if (!label || label.hidden) return null;
        const width = label.offsetWidth;
        const height = label.offsetHeight;
        return width > 0 && height > 0 ? { node, projected, label, width, height } : null;
      }).filter(Boolean);

      measured.forEach(({ node, projected, label, width, height }) => {
        const anchor = { x: projected.screenX, y: projected.screenY };
        const placement = findLabelPlacement(anchor, width, height, size, occupied, reserved, label._layoutPosition);
        if (!placement) return;
        label._layoutPosition = { x: placement.x, y: placement.y };
        label.style.left = `${placement.x}px`;
        label.style.top = `${placement.y}px`;
        label.style.zIndex = String(node.id === selectedId ? 1100 : Math.round(1000 - projected.depth * 50));
        updateLabelLeader(label, placement, anchor, width, height);
        occupied.push(placement.rect);
      });
    }

    function render(now) {
      const fps = reducedMotion.matches ? 12 : 30;
      if (!document.hidden && now - lastFrameAt >= 1000 / fps) {
        const size = dimensions();
        const scene = buildScene(now, size);
        if (webglReady) drawWebgl(scene, size); else drawFallback(scene, size);
        updateLabelPositions(size);
        lastFrameAt = now;
      }
      frame = window.requestAnimationFrame(render);
    }

    function select(id, notify = true) {
      const node = nodes.find((item) => item.id === id);
      if (!node) return;
      selectedId = id;
      labels.forEach((label, labelId) => label.classList.toggle("selected", labelId === id));
      if (notify) onSelect?.(node);
    }

    function buildLabels() {
      const activeIds = new Set(nodes.map((node) => node.id));
      labels.forEach((label, id) => {
        if (!activeIds.has(id)) { label.remove(); labels.delete(id); }
      });
      nodes.forEach((node) => {
        let label = labels.get(node.id);
        if (!label) {
          label = document.createElement("button");
          label.type = "button";
          label.addEventListener("click", (event) => {
            event.stopPropagation();
            if (dragDistance >= 5) { event.preventDefault(); return; }
            select(label.dataset.nodeId);
          });
          labels.set(node.id, label);
          labelLayer.append(label);
        }
        label.dataset.nodeId = node.id;
        label.type = "button";
        label.className = "topology-node-label";
        if (node.id === selectedId) label.classList.add("selected");
        if (node.groupCount > 1) label.classList.add("is-group");
        if (["offline", "unreachable", "disabled", "unknown"].includes(String(node.status).toLowerCase())) label.classList.add("is-offline");
        if (["warning", "degraded", "checking", "learning"].includes(String(node.status).toLowerCase())) label.classList.add("is-warning");
        label.setAttribute("aria-label", `${node.title} の情報を表示`);
        label.replaceChildren();

        const title = document.createElement("span");
        title.className = "node-label-title";
        const strong = document.createElement("strong");
        strong.textContent = node.title;
        const stateDot = document.createElement("i");
        title.append(strong, stateDot);
        label.append(title);

        const subtitle = document.createElement("small");
        subtitle.textContent = node.subtitle || node.role.toUpperCase();
        label.append(subtitle);

        if (node.metrics?.length) {
          const metrics = document.createElement("span");
          metrics.className = "node-label-metrics";
          node.metrics.slice(0, 2).forEach((metric) => {
            const item = document.createElement("span");
            item.append(document.createTextNode(`${metric.label} `));
            const value = document.createElement("b");
            value.textContent = metric.value;
            item.append(value);
            metrics.append(item);
          });
          label.append(metrics);
        }

      });
    }

    function setNodes(nextNodes) {
      nodes = layoutNodes(nextNodes.map((node) => ({ ...node, metrics: [...(node.metrics || [])] })));
      if (!nodes.some((node) => node.id === selectedId)) selectedId = nodes.find((node) => node.role === "core")?.id || nodes[0]?.id || null;
      buildLabels();
      if (selectedId) select(selectedId);
    }

    const interactionSurface = canvas.parentElement || canvas;

    function beginPointerInteraction(event) {
      if (event.button !== undefined && event.button !== 0) return;
      const label = event.target?.closest?.(".topology-node-label");
      if (event.target !== canvas && !label) return;
      const captureTarget = label || canvas;
      dragStart = {
        x: event.clientX,
        y: event.clientY,
        yaw: yawOffset,
        pitch: pitchOffset,
        pointerId: event.pointerId,
        nodeId: label?.dataset.nodeId || null,
        captureTarget,
      };
      dragDistance = 0;
      interactionSurface.classList.add("is-dragging");
      captureTarget.setPointerCapture?.(event.pointerId);
    }

    function movePointerInteraction(event) {
      if (!dragStart || event.pointerId !== dragStart.pointerId) return;
      const deltaX = event.clientX - dragStart.x;
      const deltaY = event.clientY - dragStart.y;
      dragDistance = Math.max(dragDistance, Math.hypot(deltaX, deltaY));
      yawOffset = dragStart.yaw + deltaX * 0.006;
      pitchOffset = clamp(dragStart.pitch + deltaY * 0.005, MIN_PITCH, MAX_PITCH);
      event.preventDefault();
    }

    function endPointerInteraction(event) {
      if (!dragStart || event.pointerId !== dragStart.pointerId) return;
      const completedDrag = dragStart;
      if (dragDistance < 5 && !completedDrag.nodeId) {
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const nearest = projectedNodes
          .map((item) => ({ ...item, distance: Math.hypot(item.projected.screenX - x, item.projected.screenY - y) }))
          .filter((item) => item.distance < 30)
          .sort((first, second) => first.distance - second.distance)[0];
        if (nearest) select(nearest.node.id);
      }
      dragStart = null;
      interactionSurface.classList.remove("is-dragging");
      completedDrag.captureTarget.releasePointerCapture?.(event.pointerId);
      window.setTimeout(() => { if (!dragStart) dragDistance = 0; }, 0);
    }

    function cancelPointerInteraction(event) {
      if (!dragStart || event.pointerId !== dragStart.pointerId) return;
      dragStart = null;
      dragDistance = 0;
      interactionSurface.classList.remove("is-dragging");
    }

    interactionSurface.addEventListener("pointerdown", beginPointerInteraction);
    window.addEventListener("pointermove", movePointerInteraction, { passive: false });
    window.addEventListener("pointerup", endPointerInteraction);
    window.addEventListener("pointercancel", cancelPointerInteraction);

    frame = window.requestAnimationFrame(render);
    return {
      setNodes,
      select,
      get mode() { return webglReady ? "webgl" : "fallback"; },
      destroy() {
        window.cancelAnimationFrame(frame);
        interactionSurface.removeEventListener("pointerdown", beginPointerInteraction);
        window.removeEventListener("pointermove", movePointerInteraction);
        window.removeEventListener("pointerup", endPointerInteraction);
        window.removeEventListener("pointercancel", cancelPointerInteraction);
        labelLayer.replaceChildren();
      },
    };
  }

  window.NetPulseTopology3D = { create };
})();
