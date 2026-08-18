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
  const INITIAL_DISTANCE = 8.2;
  const MIN_DISTANCE = 6.4;
  const MAX_DISTANCE = 12.8;
  const LABEL_RESERVED_SELECTORS = [
    ".topology-scene-meta",
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

  function mixColor(first, second, amount) {
    const ratio = clamp(amount, 0, 1);
    return first.map((value, index) => index === 3 ? 1 : value + (second[index] - value) * ratio);
  }

  function trafficColor(level) {
    const intensity = clamp(Number(level) || 0, 0, 1);
    if (intensity < 0.35) return mixColor(COLORS.mint, COLORS.cyan, intensity / 0.35);
    if (intensity < 0.68) return mixColor(COLORS.cyan, COLORS.violet, (intensity - 0.35) / 0.33);
    if (intensity < 0.86) return mixColor(COLORS.violet, COLORS.orange, (intensity - 0.68) / 0.18);
    return mixColor(COLORS.orange, COLORS.danger, (intensity - 0.86) / 0.14);
  }

  function trafficBand(level, rate) {
    if (!(Number(rate) > 0)) return "idle";
    if (level < 0.35) return "low";
    if (level < 0.68) return "active";
    if (level < 0.86) return "high";
    return "surge";
  }

  function colorCss(color) {
    return color.slice(0, 3).map((value) => Math.round(value * 255)).join(",");
  }

  function compactRateLabel(value) {
    return String(value || "0 bps").replace(/\.0 (?=[KMGT]bps$)/, " ").replace(/\s*bps$/, "").replace(/\s+/g, "");
  }

  function layoutNodes(nodes) {
    const groups = { core: [], infrastructure: [], telemetry: [], devices: [] };
    nodes.forEach((node) => {
      if (node.role === "gateway") groups.core.push(node);
      else if (["core", "qnap"].includes(node.role)) groups.infrastructure.push(node);
      else if (["agent", "exporter"].includes(node.role)) groups.telemetry.push(node);
      else groups.devices.push(node);
    });

    groups.core.forEach((node) => { node.position = [0, 0, 0]; node.orbit = 0; node.isHub = true; });
    const place = (items, radius, phase, verticalScale) => {
      items.forEach((node, index) => {
        const angle = phase + (index / Math.max(1, items.length)) * TAU;
        node.position = [
          Math.cos(angle) * radius,
          Math.sin(angle * 2 + phase) * verticalScale,
          Math.sin(angle) * radius * 0.68,
        ];
        node.orbit = angle;
        node.isHub = false;
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

  function createSphereMesh(latitudeSegments = 8, longitudeSegments = 12) {
    const positions = [];
    const normals = [];
    const indices = [];
    for (let latitude = 0; latitude <= latitudeSegments; latitude += 1) {
      const theta = latitude / latitudeSegments * Math.PI;
      for (let longitude = 0; longitude <= longitudeSegments; longitude += 1) {
        const phi = longitude / longitudeSegments * TAU;
        const normal = [Math.cos(phi) * Math.sin(theta), Math.cos(theta), Math.sin(phi) * Math.sin(theta)];
        positions.push(...normal);
        normals.push(...normal);
      }
    }
    for (let latitude = 0; latitude < latitudeSegments; latitude += 1) {
      for (let longitude = 0; longitude < longitudeSegments; longitude += 1) {
        const first = latitude * (longitudeSegments + 1) + longitude;
        const second = first + longitudeSegments + 1;
        indices.push(first, second, first + 1, second, second + 1, first + 1);
      }
    }
    return { positions, normals, indices };
  }

  function createOctahedronMesh() {
    const triangles = [
      [[0, 1, 0], [1, 0, 0], [0, 0, 1]], [[0, 1, 0], [0, 0, 1], [-1, 0, 0]],
      [[0, 1, 0], [-1, 0, 0], [0, 0, -1]], [[0, 1, 0], [0, 0, -1], [1, 0, 0]],
      [[0, -1, 0], [0, 0, 1], [1, 0, 0]], [[0, -1, 0], [-1, 0, 0], [0, 0, 1]],
      [[0, -1, 0], [0, 0, -1], [-1, 0, 0]], [[0, -1, 0], [1, 0, 0], [0, 0, -1]],
    ];
    const positions = [];
    const normals = [];
    const indices = [];
    triangles.forEach((triangle, triangleIndex) => {
      const first = triangle[1].map((value, index) => value - triangle[0][index]);
      const second = triangle[2].map((value, index) => value - triangle[0][index]);
      const normal = [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
      ];
      const length = Math.hypot(...normal) || 1;
      triangle.forEach((position) => {
        positions.push(...position);
        normals.push(...normal.map((value) => value / length));
      });
      indices.push(triangleIndex * 3, triangleIndex * 3 + 1, triangleIndex * 3 + 2);
    });
    return { positions, normals, indices };
  }

  function create({ canvas, labelLayer, onSelect, onModeChange, onFrameStats }) {
    if (!canvas || !labelLayer) return null;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let nodes = [];
    let selectedId = null;
    let frame = 0;
    let lastFrameAt = 0;
    let lastStatsAt = 0;
    let renderedFrames = 0;
    let yawOffset = INITIAL_YAW;
    let pitchOffset = INITIAL_PITCH;
    let cameraDistance = INITIAL_DISTANCE;
    let dragStart = null;
    let dragDistance = 0;
    let projectedNodes = [];
    let cardMode = "all";
    let cardLimit = 5;
    let cardVisibleIds = new Set();
    const labels = new Map();
    const ALWAYS_VISIBLE_ROLES = new Set(["core", "gateway", "qnap", "device-group"]);
    const gl = canvas.getContext("webgl", { alpha: true, antialias: true, premultipliedAlpha: false, powerPreference: "high-performance" });
    const context2d = gl ? null : canvas.getContext("2d");
    let lineProgram = null;
    let pointProgram = null;
    let meshProgram = null;
    let lineBuffer = null;
    let pointBuffer = null;
    const meshBuffers = {};

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
      const meshVertex = `
        attribute vec3 a_position;
        attribute vec3 a_normal;
        uniform vec3 u_center;
        uniform vec3 u_scale;
        uniform vec2 u_viewRotation;
        uniform float u_spin;
        uniform float u_cameraDistance;
        uniform float u_focal;
        uniform float u_aspect;
        varying vec3 v_normal;
        varying vec3 v_viewPosition;
        void main() {
          float objectCosine = cos(u_spin);
          float objectSine = sin(u_spin);
          vec3 local = a_position * u_scale;
          local = vec3(local.x * objectCosine - local.z * objectSine, local.y, local.x * objectSine + local.z * objectCosine);
          vec3 world = local + u_center;
          float yawCosine = cos(u_viewRotation.x);
          float yawSine = sin(u_viewRotation.x);
          vec3 yawed = vec3(world.x * yawCosine - world.z * yawSine, world.y, world.x * yawSine + world.z * yawCosine);
          float pitchCosine = cos(u_viewRotation.y);
          float pitchSine = sin(u_viewRotation.y);
          vec3 viewed = vec3(yawed.x, yawed.y * pitchCosine - yawed.z * pitchSine, yawed.y * pitchSine + yawed.z * pitchCosine);
          vec3 normal = vec3(a_normal.x * objectCosine - a_normal.z * objectSine, a_normal.y, a_normal.x * objectSine + a_normal.z * objectCosine);
          normal = vec3(normal.x * yawCosine - normal.z * yawSine, normal.y, normal.x * yawSine + normal.z * yawCosine);
          normal = vec3(normal.x, normal.y * pitchCosine - normal.z * pitchSine, normal.y * pitchSine + normal.z * pitchCosine);
          float depth = max(0.5, u_cameraDistance - viewed.z);
          float normalizedDepth = clamp((depth - 1.0) / 16.0, 0.0, 1.0) * 2.0 - 1.0;
          gl_Position = vec4(viewed.x * u_focal / u_aspect, viewed.y * u_focal, normalizedDepth * depth, depth);
          v_normal = normalize(normal);
          v_viewPosition = vec3(viewed.xy, -depth);
        }
      `;
      const meshFragment = `
        precision mediump float;
        uniform vec3 u_color;
        uniform float u_alpha;
        uniform float u_emissive;
        uniform float u_time;
        varying vec3 v_normal;
        varying vec3 v_viewPosition;
        void main() {
          vec3 normal = normalize(v_normal);
          vec3 viewDirection = normalize(-v_viewPosition);
          vec3 lightDirection = normalize(vec3(-0.45, 0.78, 0.62));
          float diffuse = max(dot(normal, lightDirection), 0.0);
          float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 2.35);
          float scan = 0.8 + sin(u_time * 1.7 + v_viewPosition.y * 8.0) * 0.2;
          vec3 lit = u_color * (0.14 + diffuse * 0.52 + u_emissive * scan) + u_color * rim * 1.35;
          gl_FragColor = vec4(lit, u_alpha * (0.6 + rim * 0.4));
        }
      `;
      try {
        lineProgram = createProgram(gl, lineVertex, lineFragment);
        pointProgram = createProgram(gl, pointVertex, pointFragment);
        meshProgram = createProgram(gl, meshVertex, meshFragment);
        lineBuffer = gl.createBuffer();
        pointBuffer = gl.createBuffer();
        const uploadMesh = (name, source) => {
          const mesh = { position: gl.createBuffer(), normal: gl.createBuffer(), index: gl.createBuffer(), count: source.indices.length };
          gl.bindBuffer(gl.ARRAY_BUFFER, mesh.position);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(source.positions), gl.STATIC_DRAW);
          gl.bindBuffer(gl.ARRAY_BUFFER, mesh.normal);
          gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(source.normals), gl.STATIC_DRAW);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.index);
          gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(source.indices), gl.STATIC_DRAW);
          meshBuffers[name] = mesh;
        };
        uploadMesh("sphere", createSphereMesh());
        uploadMesh("octahedron", createOctahedronMesh());
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.enable(gl.DEPTH_TEST);
        gl.depthFunc(gl.LEQUAL);
      } catch (error) {
        console.warn("WebGL topology initialization failed", error);
      }
    }

    const webglReady = Boolean(gl && lineProgram && pointProgram && meshProgram);
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
      const depth = view.distance - world[2];
      const focal = view.focal;
      const aspect = Math.max(0.55, size.width / Math.max(1, size.height));
      const x = (world[0] * focal / depth) / aspect;
      const y = world[1] * focal / depth;
      return {
        x, y,
        screenX: (x * 0.5 + 0.5) * size.width,
        screenY: (0.5 - y * 0.5) * size.height,
        depth,
        scale: clamp(view.distance / depth, 0.55, 1.8),
        visible: depth > 1 && Math.abs(x) < 1.2 && Math.abs(y) < 1.2,
      };
    }

    function appendLine(target, first, second, color, alpha = 1) {
      if (!first.visible || !second.visible) return;
      target.push(first.x, first.y, color[0], color[1], color[2], alpha, second.x, second.y, color[0], color[1], color[2], alpha);
    }

    function appendTrafficGlow(target, first, second, color, intensity, size) {
      if (!first.visible || !second.visible) return;
      const strength = clamp(Number(intensity) || 0, 0, 1);
      appendLine(target, first, second, color, 0.2 + strength * 0.64);
      if (strength < 0.08) return;
      const deltaX = second.x - first.x;
      const deltaY = second.y - first.y;
      const length = Math.hypot(deltaX, deltaY) || 1;
      const spread = 0.7 + strength * 2.5;
      const offsetX = (-deltaY / length) * spread * 2 / Math.max(1, size.width);
      const offsetY = (deltaX / length) * spread * 2 / Math.max(1, size.height);
      [-1, 1].forEach((direction) => {
        appendLine(
          target,
          { ...first, x: first.x + offsetX * direction, y: first.y + offsetY * direction },
          { ...second, x: second.x + offsetX * direction, y: second.y + offsetY * direction },
          color,
          0.035 + strength * 0.16,
        );
      });
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
        distance: cameraDistance,
        focal: size.width <= 650 ? 1.45 : size.width <= 920 ? 1.9 : 2.25,
      };
      const lines = [];
      const points = [];
      const meshInstances = [];
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

      for (let coordinate = -4.5; coordinate <= 4.5; coordinate += 0.75) {
        const alpha = Math.abs(coordinate % 3) < 0.01 ? 0.085 : 0.027;
        appendLine(lines, project([coordinate, -1.9, -4.5], view, size), project([coordinate, -1.9, 4.5], view, size), COLORS.cyan, alpha);
        appendLine(lines, project([-4.5, -1.9, coordinate], view, size), project([4.5, -1.9, coordinate], view, size), COLORS.cyan, alpha);
      }

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
      const projectedById = new Map(projectedNodes.map((item) => [item.node.id, item]));
      const coreProjection = project([0, 0, 0], view, size);

      projectedNodes.forEach(({ node, projected }, index) => {
        const color = statusColor(node);
        const offline = ["offline", "unreachable", "disabled", "unknown"].includes(String(node.status).toLowerCase());
        const activity = offline ? 0.02 : clamp(Number(node.activityLevel) || 0.12, 0.05, 1);
        if (!node.isHub) appendLine(lines, coreProjection, projected, color, offline ? 0.055 : 0.12);

        const trafficTarget = node.trafficTargetId ? projectedById.get(node.trafficTargetId) : null;
        if (trafficTarget && node.trafficMeasured && !offline) {
          const level = clamp(Number(node.trafficLevel) || 0, 0, 1);
          const flowColor = trafficColor(level);
          appendTrafficGlow(lines, projected, trafficTarget.projected, flowColor, level, size);
          const rx = Math.max(0, Number(node.rxBps) || 0);
          const tx = Math.max(0, Number(node.txBps) || 0);
          const total = rx + tx;
          const addParticles = (rate, from, to, directionOffset) => {
            if (!(rate > 0) || !(total > 0)) return;
            const share = rate / total;
            const particleCount = 1 + Math.round(level * 3 * share);
            const speed = 0.00011 + level * 0.00052;
            for (let particleIndex = 0; particleIndex < particleCount; particleIndex += 1) {
              const progress = reducedMotion.matches
                ? (particleIndex + 1) / (particleCount + 1)
                : (now * speed + index * 0.173 + particleIndex / particleCount + directionOffset) % 1;
              const world = from.position.map((value, axis) => value + (to.position[axis] - value) * progress);
              const particle = project(world, view, size);
              points.push(particle.x, particle.y, (5 + level * 8) * particle.scale, flowColor[0], flowColor[1], flowColor[2], 0.52 + level * 0.42);
            }
          };
          addParticles(tx, node, trafficTarget.node, 0);
          addParticles(rx, trafficTarget.node, node, 0.47);
        }

        const baseSize = node.role === "gateway" ? 25 : node.role === "device" ? 13 : 18;
        points.push(projected.x, projected.y, baseSize * 1.85 * projected.scale, color[0], color[1], color[2], 0.13);
        points.push(projected.x, projected.y, baseSize * projected.scale, color[0], color[1], color[2], 0.92);
        if (node.id === selectedId) appendScreenRing(lines, projected, baseSize * 0.72 * projected.scale, color, 0.78, size);

        const selected = node.id === selectedId;
        const pulse = 1 + (reducedMotion.matches ? 0 : Math.sin(now * (0.0012 + activity * 0.0018) + index) * 0.06);
        const baseScale = node.role === "gateway" ? 0.45 : node.role === "qnap" ? 0.39 : ["agent", "core", "exporter"].includes(node.role) ? 0.31 : node.role === "device-group" ? 0.4 : 0.24;
        const scale = baseScale * pulse * (selected ? 1.25 : 1);
        meshInstances.push({
          mesh: ["core", "gateway", "device-group"].includes(node.role) ? "sphere" : "octahedron",
          center: node.position,
          scale: node.role === "gateway" ? [scale * 1.45, scale * 0.32, scale * 1.45] : node.role === "qnap" ? [scale * 1.15, scale * 0.75, scale] : [scale, scale, scale],
          spin: node.orbit + now * (reducedMotion.matches ? 0 : 0.00036) * (0.7 + index * 0.025),
          color,
          alpha: offline ? 0.2 : selected ? 0.96 : 0.72,
          emissive: selected ? 0.82 : 0.34 + activity * 0.38,
        });
      });

      const scanY = Math.sin(now * 0.00045) * 0.88;
      const scanRadius = Math.sqrt(Math.max(0.1, 1.02 * 1.02 - scanY * scanY));
      const segments = 48;
      for (let index = 0; index < segments; index += 1) {
        const start = index / segments * TAU;
        const end = (index + 1) / segments * TAU;
        appendLine(lines, project([Math.cos(start) * scanRadius, scanY, Math.sin(start) * scanRadius], view, size), project([Math.cos(end) * scanRadius, scanY, Math.sin(end) * scanRadius], view, size), COLORS.cyan, 0.34);
      }

      return { lines, points, meshInstances, view };
    }

    function drawMesh(instance, scene, size, now) {
      const mesh = meshBuffers[instance.mesh];
      gl.useProgram(meshProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.position);
      const position = gl.getAttribLocation(meshProgram, "a_position");
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.normal);
      const normal = gl.getAttribLocation(meshProgram, "a_normal");
      gl.enableVertexAttribArray(normal);
      gl.vertexAttribPointer(normal, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.index);
      const uniform = (name) => gl.getUniformLocation(meshProgram, name);
      gl.uniform3fv(uniform("u_center"), instance.center);
      gl.uniform3fv(uniform("u_scale"), instance.scale);
      gl.uniform2f(uniform("u_viewRotation"), scene.view.yaw, scene.view.pitch);
      gl.uniform1f(uniform("u_spin"), instance.spin);
      gl.uniform1f(uniform("u_cameraDistance"), scene.view.distance);
      gl.uniform1f(uniform("u_focal"), scene.view.focal);
      gl.uniform1f(uniform("u_aspect"), Math.max(0.55, size.width / Math.max(1, size.height)));
      gl.uniform3fv(uniform("u_color"), instance.color.slice(0, 3));
      gl.uniform1f(uniform("u_alpha"), instance.alpha);
      gl.uniform1f(uniform("u_emissive"), instance.emissive);
      gl.uniform1f(uniform("u_time"), now * 0.001);
      gl.drawElements(gl.TRIANGLES, mesh.count, gl.UNSIGNED_SHORT, 0);
    }

    function drawWebgl(scene, size, now) {
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

      gl.enable(gl.DEPTH_TEST);
      gl.depthMask(true);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      scene.meshInstances.forEach((instance) => drawMesh(instance, scene, size, now));

      gl.disable(gl.DEPTH_TEST);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
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
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.enable(gl.DEPTH_TEST);
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
      const appendCandidate = (rawX, rawY, edgePenalty = 0) => {
        const x = clamp(rawX, LABEL_MARGIN, Math.max(LABEL_MARGIN, size.width - LABEL_MARGIN - width));
        const y = clamp(rawY, LABEL_MARGIN, Math.max(LABEL_MARGIN, size.height - LABEL_MARGIN - height));
        const key = `${Math.round(x)}:${Math.round(y)}`;
        if (seen.has(key)) return;
        seen.add(key);
        candidates.push({
          x, y,
          edgePenalty: edgePenalty + Math.abs(rawX - x) + Math.abs(rawY - y),
          distance: Math.hypot(x + width / 2 - anchor.x, y + height / 2 - anchor.y),
        });
      };
      for (let ring = 0; ring < 7; ring += 1) {
        angles.forEach((angle) => {
          const horizontalDistance = LABEL_GAP + width / 2 + ring * 30;
          const verticalDistance = LABEL_GAP + height / 2 + ring * 24;
          const rawX = anchor.x + Math.cos(angle) * horizontalDistance - width / 2;
          const rawY = anchor.y + Math.sin(angle) * verticalDistance - height / 2;
          appendCandidate(rawX, rawY);
        });
      }
      const availableWidth = Math.max(0, size.width - LABEL_MARGIN * 2 - width);
      const availableHeight = Math.max(0, size.height - LABEL_MARGIN * 2 - height);
      for (let row = 0; row < 7; row += 1) {
        for (let column = 0; column < 5; column += 1) {
          appendCandidate(
            LABEL_MARGIN + availableWidth * column / 4,
            LABEL_MARGIN + availableHeight * row / 6,
            4,
          );
        }
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
        const collidesWithCard = occupiedOverlap > 0;
        const collidesWithReserved = reservedOverlap > 0;
        const score = occupiedOverlap * 1400 + reservedOverlap * 1800 + candidate.edgePenalty * 30 + candidate.distance + movement * 2.2;
        if (
          !best
          || Number(collidesWithCard) < Number(best.collidesWithCard)
          || (collidesWithCard === best.collidesWithCard && Number(collidesWithReserved) < Number(best.collidesWithReserved))
          || (collidesWithCard === best.collidesWithCard && collidesWithReserved === best.collidesWithReserved && score < best.score)
        ) {
          best = { ...candidate, rect, score, collidesWithCard, collidesWithReserved };
        }
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
          if (first.node.isHub) return -1;
          if (second.node.isHub) return 1;
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
        if (webglReady) drawWebgl(scene, size, now); else drawFallback(scene, size);
        updateLabelPositions(size);
        renderedFrames += 1;
        if (!lastStatsAt) lastStatsAt = now;
        if (now - lastStatsAt >= 1000) {
          onFrameStats?.({ fps: Math.round(renderedFrames * 1000 / (now - lastStatsAt)), objects: nodes.length, distance: cameraDistance });
          renderedFrames = 0;
          lastStatsAt = now;
        }
        lastFrameAt = now;
      }
      frame = window.requestAnimationFrame(render);
    }

    function computeCardVisibleIds() {
      if (cardMode !== "top") return new Set(nodes.map((node) => node.id));
      const visible = new Set(nodes.filter((node) => ALWAYS_VISIBLE_ROLES.has(node.role)).map((node) => node.id));
      const ranked = [...nodes].sort((first, second) => (Number(second.activityLevel) || 0) - (Number(first.activityLevel) || 0) || String(first.id).localeCompare(String(second.id)));
      ranked.slice(0, Math.max(1, cardLimit)).forEach((node) => visible.add(node.id));
      if (selectedId) visible.add(selectedId);
      return visible;
    }

    function syncCardVisibility() {
      labels.forEach((label, id) => label.classList.toggle("is-card-hidden", !cardVisibleIds.has(id)));
    }

    function setCardConfig(mode, limit) {
      cardMode = mode === "top" ? "top" : "all";
      cardLimit = Math.min(32, Math.max(1, Math.round(Number(limit) || cardLimit)));
      cardVisibleIds = computeCardVisibleIds();
      syncCardVisibility();
    }

    function select(id, notify = true) {
      const node = nodes.find((item) => item.id === id);
      if (!node) return;
      selectedId = id;
      cardVisibleIds.add(id);
      labels.get(id)?.classList.remove("is-card-hidden");
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
        if (!cardVisibleIds.has(node.id)) label.classList.add("is-card-hidden");
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

        const glance = document.createElement("span");
        glance.className = "node-label-glance";
        const linkType = document.createElement("span");
        linkType.textContent = node.trafficMeasured ? (node.linkType || "LOCAL") : `${node.linkType || "DISCOVERY"} LINK`;
        const socketCount = document.createElement("b");
        socketCount.textContent = node.socketCount == null ? "SOCKETS —" : `${node.socketCount} SOCK`;

        if (node.trafficMeasured) {
          const rate = Math.max(0, Number(node.rxBps) || 0) + Math.max(0, Number(node.txBps) || 0);
          const level = clamp(Number(node.trafficLevel) || 0, 0, 1);
          const flowColor = trafficColor(level);
          const flow = document.createElement("span");
          flow.className = "node-flow-readout";
          flow.dataset.trafficBand = trafficBand(level, rate);
          flow.style.setProperty("--flow-color", colorCss(flowColor));
          flow.textContent = `${compactRateLabel(node.trafficRateLabel)} · ${node.socketCount == null ? "S—" : `${node.socketCount}S`}`;
          glance.append(linkType, flow);
          label.append(glance);

          const activity = document.createElement("span");
          activity.className = "node-traffic-meter";
          activity.dataset.trafficBand = trafficBand(level, rate);
          activity.style.setProperty("--traffic", `${Math.max(3, Math.round(level * 100))}%`);
          activity.style.setProperty("--flow-color", colorCss(flowColor));
          activity.append(document.createElement("i"));
          label.append(activity);
        } else {
          glance.append(linkType, socketCount);
          label.append(glance);
        }

        if (node.metrics?.length) {
          const metrics = document.createElement("span");
          metrics.className = "node-label-metrics";
          node.metrics.slice(0, 3).forEach((metric) => {
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
      cardVisibleIds = computeCardVisibleIds();
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

    function zoomCamera(event) {
      if (event.target !== canvas) return;
      cameraDistance = clamp(cameraDistance + event.deltaY * 0.008, MIN_DISTANCE, MAX_DISTANCE);
      event.preventDefault();
    }

    function resetCamera() {
      yawOffset = INITIAL_YAW;
      pitchOffset = INITIAL_PITCH;
      cameraDistance = INITIAL_DISTANCE;
    }

    interactionSurface.addEventListener("pointerdown", beginPointerInteraction);
    window.addEventListener("pointermove", movePointerInteraction, { passive: false });
    window.addEventListener("pointerup", endPointerInteraction);
    window.addEventListener("pointercancel", cancelPointerInteraction);
    canvas.addEventListener("wheel", zoomCamera, { passive: false });
    canvas.addEventListener("dblclick", resetCamera);

    frame = window.requestAnimationFrame(render);
    return {
      setNodes,
      select,
      setCardConfig,
      resetCamera,
      get mode() { return webglReady ? "webgl" : "fallback"; },
      destroy() {
        window.cancelAnimationFrame(frame);
        interactionSurface.removeEventListener("pointerdown", beginPointerInteraction);
        window.removeEventListener("pointermove", movePointerInteraction);
        window.removeEventListener("pointerup", endPointerInteraction);
        window.removeEventListener("pointercancel", cancelPointerInteraction);
        canvas.removeEventListener("wheel", zoomCamera);
        canvas.removeEventListener("dblclick", resetCamera);
        labelLayer.replaceChildren();
      },
    };
  }

  window.NetPulseTopology3D = { create };
})();
