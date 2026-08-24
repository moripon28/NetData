(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const elements = {
    connection: $("connectionPill"), clock: $("clock"), subnet: $("subnetLabel"), gateway: $("gatewayLabel"),
    gatewayLatency: $("gatewayLatency"), healthScore: $("healthScore"), healthRing: $("healthRing"),
    healthMessage: $("healthMessage"), online: $("onlineDevices"), total: $("totalDevices"),
    packetLoss: $("packetLoss"), interface: $("interfaceName"), uptime: $("uptime"),
    down: $("downloadRate"), up: $("uploadRate"), temperature: $("temperature"),
    trafficTabs: $("trafficTabs"), trafficSourceCount: $("trafficSourceCount"),
    trafficScope: $("trafficScope"), trafficAxisStart: $("trafficAxisStart"),
    cpu: $("cpuValue"), cpuBar: $("cpuBar"), cpuDetail: $("cpuDetail"),
    memory: $("memoryValue"), memoryBar: $("memoryBar"), memoryDetail: $("memoryDetail"),
    disk: $("diskValue"), diskBar: $("diskBar"), diskDetail: $("diskDetail"),
    deviceRows: $("deviceRows"), eventList: $("eventList"), eventCount: $("eventCount"),
    search: $("deviceSearch"), topology: $("topologyCanvas"), traffic: $("trafficCanvas"),
    topologyStage: $("topologyStage"), topologyLabelLayer: $("topologyLabelLayer"),
    topologyRenderMode: $("topologyRenderMode"), topologyNodeCount: $("topologyNodeCount"),
    topologyNodeRole: $("topologyNodeRole"), topologyNodeTitle: $("topologyNodeTitle"),
    topologyNodeSubtitle: $("topologyNodeSubtitle"), topologyNodeState: $("topologyNodeState"),
    topologyNodeMetrics: $("topologyNodeMetrics"), topologyNodeDescription: $("topologyNodeDescription"),
    topologyProfileButton: $("topologyProfileButton"),
    topologyTrafficFlux: $("topologyTrafficFlux"), topologySocketCount: $("topologySocketCount"),
    topologyProcessCount: $("topologyProcessCount"), topologyLatencyReadout: $("topologyLatencyReadout"),
    topologyFrameRate: $("topologyFrameRate"), topologyObjectCount: $("topologyObjectCount"),
    topologyCardSettingsButton: $("topologyCardSettingsButton"), topologyCardSettingsDialog: $("topologyCardSettingsDialog"),
    topologyCardSettingsForm: $("topologyCardSettingsForm"), topologyCardSettingsClose: $("topologyCardSettingsClose"),
    topologyCardSettingsCancel: $("topologyCardSettingsCancel"), topologyCardMode: $("topologyCardMode"),
    topologyCardLimit: $("topologyCardLimit"), topologyCardSettingsStatus: $("topologyCardSettingsStatus"),
    llmFlavorStream: $("llmFlavorStream"), llmFlavorScope: $("llmFlavorScope"),
    llmFlavorViewport: $("llmFlavorViewport"), llmFlavorContent: $("llmFlavorContent"),
    llmFlavorCursor: $("llmFlavorCursor"), llmFlavorStatus: $("llmFlavorStatus"),
    dialog: $("deviceDialog"), form: $("deviceForm"), dialogIp: $("dialogIp"), dialogName: $("dialogName"),
    dialogType: $("dialogType"), dialogTrusted: $("dialogTrusted"),
    connectivityStatus: $("connectivityStatus"), lanProbeCount: $("lanProbeCount"), lanLatency: $("lanLatency"),
    connectivityDetail: $("connectivityDetail"), exporterStatus: $("exporterStatus"),
    exporterHosts: $("exporterHosts"), exporterLatency: $("exporterLatency"),
    exporterDetail: $("exporterDetail"), qnapStatus: $("qnapStatus"), qnapDisks: $("qnapDisks"),
    qnapTemperature: $("qnapTemperature"), qnapDetail: $("qnapDetail"),
    agentCount: $("agentCount"), agentNodes: $("agentNodes"),
    agentDetail: $("agentDetail"), agentSetupButton: $("agentSetupButton"), agentSetupDialog: $("agentSetupDialog"),
    agentSetupClose: $("agentSetupClose"), agentSetupTokenStatus: $("agentSetupTokenStatus"),
    windowsInstallCommand: $("windowsInstallCommand"), linuxInstallCommand: $("linuxInstallCommand"),
    windowsUninstallCommand: $("windowsUninstallCommand"), linuxUninstallCommand: $("linuxUninstallCommand"),
    agentManageButton: $("agentManageButton"), agentManageDialog: $("agentManageDialog"),
    agentManageClose: $("agentManageClose"), agentManageList: $("agentManageList"), agentManageStatus: $("agentManageStatus"),
    agentDeleteDialog: $("agentDeleteDialog"), agentDeleteForm: $("agentDeleteForm"),
    agentDeleteClose: $("agentDeleteClose"), agentDeleteCancel: $("agentDeleteCancel"),
    agentDeleteName: $("agentDeleteName"), agentDeleteAddress: $("agentDeleteAddress"), agentDeleteId: $("agentDeleteId"),
    agentDeleteStatus: $("agentDeleteStatus"), agentDeleteConfirm: $("agentDeleteConfirm"),
    anomalyStatus: $("anomalyStatus"), learningBar: $("learningBar"),
    learningProgress: $("learningProgress"), anomalyDetail: $("anomalyDetail"),
    llmSettingsButton: $("llmSettingsButton"), llmRunButton: $("llmRunButton"),
    llmReportHistory: $("llmReportHistory"), llmReportStatus: $("llmReportStatus"),
    llmReportTime: $("llmReportTime"), llmReportModel: $("llmReportModel"), llmReportContent: $("llmReportContent"),
    llmSettingsDialog: $("llmSettingsDialog"), llmSettingsForm: $("llmSettingsForm"),
    llmSettingsClose: $("llmSettingsClose"), llmSettingsCancel: $("llmSettingsCancel"),
    llmEnabled: $("llmEnabled"), llmBaseUrl: $("llmBaseUrl"), llmModel: $("llmModel"),
    llmSystemPrompt: $("llmSystemPrompt"),
    llmModelOptions: $("llmModelOptions"), llmLoadModels: $("llmLoadModels"),
    llmInterval: $("llmInterval"), llmLookback: $("llmLookback"), llmApiKey: $("llmApiKey"),
    llmFlavorScopeSelect: $("llmFlavorScopeSelect"),
    llmClearApiKey: $("llmClearApiKey"), llmSettingsStatus: $("llmSettingsStatus"),
    notifySettingsButton: $("notifySettingsButton"),
    notifySettingsDialog: $("notifySettingsDialog"), notifySettingsForm: $("notifySettingsForm"),
    notifySettingsClose: $("notifySettingsClose"), notifySettingsCancel: $("notifySettingsCancel"),
    notifyEnabled: $("notifyEnabled"), notifyServerUrl: $("notifyServerUrl"), notifyTopic: $("notifyTopic"),
    notifyPriority: $("notifyPriority"), notifyWebhookUrl: $("notifyWebhookUrl"), notifyWebhookToken: $("notifyWebhookToken"),
    notifyCooldown: $("notifyCooldown"), notifyClearToken: $("notifyClearToken"),
    notifySettingsStatus: $("notifySettingsStatus"), notifyTestButton: $("notifyTestButton"),
    themeSettingsButton: $("themeSettingsButton"), themeDialog: $("themeDialog"), themeClose: $("themeClose"),
    themeColorMeta: document.querySelector('meta[name="theme-color"]'),
    trafficSummaryDaily: $("trafficSummaryDaily"), trafficSummaryRanking: $("trafficSummaryRanking"),
    trafficSummaryDaysLabel: $("trafficSummaryDaysLabel"), trafficSummaryRankLabel: $("trafficSummaryRankLabel"),
  };

  const topologyCardsKey = "netpulse.topologyCards";
  const topologyCardLimits = 10;
  const state = {
    snapshot: null, devices: [], rx: [], tx: [], filter: "all", search: "", selectedIp: null,
    trafficSelection: "all", trafficSources: [], trafficSeries: {}, trafficTabSignature: "", trafficWindowMinutes: 5,
    topologyNodes: [], topologyScene: null, selectedTopologyNode: null,
    topologyCardSettings: loadTopologyCardSettings(),
    socket: null, reconnectTimer: null, reports: [], llmSettings: null, agents: [], selectedAgent: null,
    flavorSignature: "", flavorGeneration: 0,
  };
  const fontSizeKey = "netpulse.fontSize";
  const fontSizes = new Set(["small", "medium", "large", "xlarge"]);
  const fontSizeButtons = [...document.querySelectorAll("[data-font-size]")];
  const maxPoints = 60;
  const topologyNodeLimit = 18;
  const offlineGroupMinimum = 4;
  function loadTopologyCardSettings() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(topologyCardsKey) || "null");
      const mode = parsed && (parsed.mode === "top" || parsed.mode === "all") ? parsed.mode : "top";
      const limit = Math.min(topologyCardLimits, Math.max(1, Math.round(Number(parsed && parsed.limit) || 5)));
      return { mode, limit };
    } catch (_) { return { mode: "top", limit: 5 }; }
  }
  const inactiveTopologyStatuses = new Set(["offline", "unreachable", "unknown", "disabled"]);
  const typeIcons = { router: "⌁", computer: "▣", phone: "▯", tablet: "▭", tv: "▰", iot: "◇", server: "▤", printer: "▥", camera: "◉", game: "✦", unknown: "?" };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
  const renderMarkdownInline = (value) => escapeHtml(value)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  function renderMarkdown(source) {
    const blocks = [];
    let listType = null;
    let paragraph = [];
    let quote = [];
    const flushParagraph = () => {
      if (!paragraph.length) return;
      blocks.push(`<p>${paragraph.map(renderMarkdownInline).join("<br>")}</p>`);
      paragraph = [];
    };
    const flushQuote = () => {
      if (!quote.length) return;
      blocks.push(`<blockquote>${quote.map(renderMarkdownInline).join("<br>")}</blockquote>`);
      quote = [];
    };
    const closeList = () => {
      if (!listType) return;
      blocks.push(`</${listType}>`);
      listType = null;
    };
    const flushAll = () => { flushParagraph(); flushQuote(); closeList(); };
    for (const rawLine of String(source ?? "").split(/\r?\n/)) {
      const trimmed = rawLine.trim();
      if (!trimmed) { flushAll(); continue; }
      const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        flushAll();
        blocks.push(`<h${heading[1].length}>${renderMarkdownInline(heading[2])}</h${heading[1].length}>`);
        continue;
      }
      if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(trimmed)) { flushAll(); blocks.push("<hr>"); continue; }
      const blockquote = trimmed.match(/^>\s?(.*)$/);
      if (blockquote) {
        flushParagraph(); closeList();
        quote.push(blockquote[1]);
        continue;
      }
      const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
      const unordered = ordered ? null : trimmed.match(/^[-*]\s+(.+)$/);
      if (ordered || unordered) {
        const type = ordered ? "ol" : "ul";
        flushParagraph(); flushQuote();
        if (listType !== type) { closeList(); blocks.push(`<${type}>`); listType = type; }
        blocks.push(`<li>${renderMarkdownInline((ordered || unordered)[1])}</li>`);
        continue;
      }
      flushQuote(); closeList();
      paragraph.push(trimmed);
    }
    flushAll();
    return blocks.join("");
  }
  const clamp = (value, min, max) => Math.max(min, Math.min(max, Number(value) || 0));
  const formatRate = (bytes) => {
    const bits = Math.max(0, Number(bytes) || 0) * 8;
    if (bits >= 1e9) return `${(bits / 1e9).toFixed(2)} Gbps`;
    if (bits >= 1e6) return `${(bits / 1e6).toFixed(bits >= 1e8 ? 0 : 1)} Mbps`;
    if (bits >= 1e3) return `${(bits / 1e3).toFixed(1)} Kbps`;
    return `${bits.toFixed(0)} bps`;
  };
  const formatBytes = (bytes) => {
    const value = Number(bytes) || 0;
    if (value >= 1e12) return `${(value / 1e12).toFixed(1)} TB`;
    if (value >= 1e9) return `${(value / 1e9).toFixed(1)} GB`;
    if (value >= 1e6) return `${(value / 1e6).toFixed(1)} MB`;
    return `${(value / 1e3).toFixed(0)} KB`;
  };
  const formatDuration = (seconds) => {
    const value = Number(seconds) || 0;
    const days = Math.floor(value / 86400);
    const hours = Math.floor((value % 86400) / 3600);
    return days ? `${days}D ${hours}H` : `${hours}H ${Math.floor((value % 3600) / 60)}M`;
  };
  const relativeTime = (timestamp) => {
    const seconds = Math.max(0, Date.now() / 1000 - Number(timestamp || 0));
    if (seconds < 10) return "NOW";
    if (seconds < 60) return `${Math.floor(seconds)}S AGO`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}M AGO`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}H AGO`;
    return `${Math.floor(seconds / 86400)}D AGO`;
  };
  const formatDateTime = (timestamp) => timestamp ? new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium", timeStyle: "short" }).format(new Date(Number(timestamp) * 1000)) : "—";
  const finiteNumber = (value) => value == null || value === "" || !Number.isFinite(Number(value)) ? null : Number(value);
  const metric = (label, value) => value == null || value === "" ? null : ({ label, value: String(value) });
  const percentMetric = (label, value) => {
    const number = finiteNumber(value);
    return number == null ? null : metric(label, `${number.toFixed(number >= 10 ? 0 : 1)}%`);
  };
  const temperatureMetric = (label, value) => {
    const number = finiteNumber(value);
    return number == null ? null : metric(label, `${number.toFixed(0)}°C`);
  };
  const compactMetrics = (...values) => values.filter(Boolean);

  function applyFontSize(requestedSize, persist = true) {
    const size = fontSizes.has(requestedSize) ? requestedSize : "medium";
    document.documentElement.dataset.fontSize = size;
    fontSizeButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.fontSize === size)));
    if (persist) {
      try { localStorage.setItem(fontSizeKey, size); } catch (_) { /* Storage can be disabled. */ }
    }
    window.dispatchEvent(new Event("resize"));
  }

  applyFontSize(document.documentElement.dataset.fontSize || "medium", false);
  fontSizeButtons.forEach((button) => button.addEventListener("click", () => applyFontSize(button.dataset.fontSize)));

  const themeKey = "netpulse.theme";
  const themeChoices = ["dark", "bright", "light", "midnight", "amber", "forest", "ocean", "sakura", "nebula", "solar", "mono"];
  const themeSwatchButtons = [...document.querySelectorAll("[data-theme-choice]")];

  function cssVarColor(name, fallback) {
    try {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
    } catch (_) { return fallback; }
  }

  function withAlpha(color, alpha) {
    const value = String(color || "");
    const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
    if (hex) {
      let digits = hex[1];
      if (digits.length === 3) digits = [...digits].map((char) => char + char).join("");
      return `rgba(${parseInt(digits.slice(0, 2), 16)},${parseInt(digits.slice(2, 4), 16)},${parseInt(digits.slice(4, 6), 16)},${alpha})`;
    }
    const rgb = value.match(/^rgb\(([^)]+)\)/);
    if (rgb) {
      const parts = rgb[1].split(/[\s,/]+/).filter(Boolean);
      return `rgba(${parts.slice(0, 3).join(",")},${alpha})`;
    }
    return value;
  }

  function applyTheme(requestedTheme, persist = true) {
    const theme = themeChoices.includes(requestedTheme) ? requestedTheme : "dark";
    document.documentElement.dataset.theme = theme;
    themeSwatchButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme)));
    if (persist) {
      try { localStorage.setItem(themeKey, theme); } catch (_) { /* Storage can be disabled. */ }
    }
    if (elements.themeColorMeta) elements.themeColorMeta.setAttribute("content", cssVarColor("--bg", "#050a09"));
    state.topologyScene?.refreshColors();
    drawTraffic();
  }

  applyTheme(document.documentElement.dataset.theme || "dark", false);
  themeSwatchButtons.forEach((button) => button.addEventListener("click", () => applyTheme(button.dataset.themeChoice)));

  async function apiError(response) {
    try {
      const body = await response.json();
      return body.detail || `HTTP ${response.status}`;
    } catch (_) { return `HTTP ${response.status}`; }
  }

  function setConnection(mode) {
    elements.connection.className = `live-pill ${mode}`;
    elements.connection.querySelector("b").textContent = mode === "connected" ? "LIVE" : mode === "disconnected" ? "RECONNECTING" : "CONNECTING";
  }

  const trafficKindLabels = { aggregate: "TOTAL", local: "RASPBERRY PI", agent: "AGENT", prometheus: "EXPORTER" };

  function trafficFallback(snapshot) {
    const network = snapshot.network || {};
    const local = {
      id: "local", label: "Raspberry Pi 5", kind: "local",
      status: network.interface && network.interface !== "detecting" ? "online" : "checking",
      rx_bps: Number(network.rx_bps) || 0, tx_bps: Number(network.tx_bps) || 0,
      observed_at: snapshot.generated_at,
    };
    return {
      total: { ...local, id: "all", label: "すべての端末", kind: "aggregate" },
      sources: [local], source_count: 1, online_source_count: local.status === "online" ? 1 : 0,
    };
  }

  function renderTrafficTabs() {
    const signature = state.trafficSources.map((source) => `${source.id}|${source.label}|${source.kind}|${source.status}`).join(";");
    if (signature !== state.trafficTabSignature) {
      const previousScroll = elements.trafficTabs.scrollLeft;
      const fragment = document.createDocumentFragment();
      state.trafficSources.forEach((source) => {
        const button = document.createElement("button");
        const status = ["online", "offline", "checking"].includes(source.status) ? source.status : "checking";
        button.type = "button";
        button.className = `traffic-tab ${source.kind === "aggregate" ? "aggregate " : ""}${status}`;
        button.dataset.sourceId = source.id;
        button.setAttribute("role", "tab");
        button.setAttribute("aria-controls", "trafficCanvas");
        button.title = `${source.label} · ${trafficKindLabels[source.kind] || source.kind}`;
        const dot = document.createElement("i");
        dot.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.textContent = source.kind === "aggregate" ? "ALL" : source.label;
        button.append(dot, label);
        fragment.append(button);
      });
      elements.trafficTabs.replaceChildren(fragment);
      elements.trafficTabs.scrollLeft = previousScroll;
      state.trafficTabSignature = signature;
    }
    elements.trafficTabs.querySelectorAll("[role=tab]").forEach((button) => {
      const selected = button.dataset.sourceId === state.trafficSelection;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    });
  }

  function syncTrafficView() {
    let source = state.trafficSources.find((item) => item.id === state.trafficSelection);
    if (!source) {
      state.trafficSelection = "all";
      source = state.trafficSources.find((item) => item.id === "all");
    }
    const samples = state.trafficSeries[state.trafficSelection] || [];
    state.rx = samples.map((sample) => Number(sample.rx_bps) || 0);
    state.tx = samples.map((sample) => Number(sample.tx_bps) || 0);
    elements.down.textContent = formatRate(source?.rx_bps);
    elements.up.textContent = formatRate(source?.tx_bps);
    const kind = trafficKindLabels[source?.kind] || "TELEMETRY";
    elements.trafficScope.textContent = source?.kind === "aggregate" ? "すべての計測端末の合計" : `${source?.label || "端末"} · ${kind}`;
    elements.trafficScope.parentElement.querySelector("span").textContent = source?.kind === "aggregate"
      ? "取得できている端末を集計"
      : source?.status === "online" ? "リアルタイム受信中" : source?.status === "offline" ? "オフライン · 履歴を表示" : "取得待ち";
    elements.traffic.setAttribute("aria-label", `${source?.label || "端末"}の直近の受信・送信速度グラフ`);
    renderTrafficTabs();
    drawTraffic();
  }

  function applyTrafficSnapshot(payload, append = true) {
    const total = payload?.total;
    const sources = Array.isArray(payload?.sources) ? payload.sources : [];
    if (!total) return;
    state.trafficSources = [total, ...sources];
    if (!state.trafficSources.some((source) => source.id === state.trafficSelection)) state.trafficSelection = "all";
    elements.trafficSourceCount.textContent = `${payload.online_source_count || 0} / ${payload.source_count || sources.length} LIVE`;
    if (append) {
      const timestamp = Number(total.observed_at) || Date.now() / 1000;
      state.trafficSources.forEach((source) => {
        const series = state.trafficSeries[source.id] || (state.trafficSeries[source.id] = []);
        const point = { ts: timestamp, rx_bps: Number(source.rx_bps) || 0, tx_bps: Number(source.tx_bps) || 0 };
        if (series.length && Math.abs(Number(series[series.length - 1].ts) - timestamp) < 0.25) series[series.length - 1] = point;
        else series.push(point);
        if (series.length > maxPoints) series.splice(0, series.length - maxPoints);
      });
    }
    syncTrafficView();
  }

  function loadTrafficHistory(payload) {
    state.trafficWindowMinutes = Number(payload.minutes) || 2;
    state.trafficSeries = {};
    Object.entries(payload.series || {}).forEach(([sourceId, samples]) => {
      state.trafficSeries[sourceId] = Array.isArray(samples) ? samples.slice(-maxPoints) : [];
    });
    elements.trafficAxisStart.textContent = state.trafficWindowMinutes === 1 ? "60 SEC AGO" : `${state.trafficWindowMinutes} MIN AGO`;
    applyTrafficSnapshot(payload, false);
  }

  function selectTrafficSource(sourceId, focus = false) {
    if (!state.trafficSources.some((source) => source.id === sourceId)) return;
    state.trafficSelection = sourceId;
    syncTrafficView();
    const selected = [...elements.trafficTabs.querySelectorAll("[role=tab]")].find((button) => button.dataset.sourceId === sourceId);
    selected?.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    if (focus) selected?.focus();
  }

  function applySnapshot(snapshot) {
    state.snapshot = snapshot;
    state.devices = snapshot.devices || [];
    const system = snapshot.system || {};
    const network = snapshot.network || {};
    const summary = snapshot.summary || {};
    const health = clamp(summary.health_score, 0, 100);

    elements.subnet.textContent = `SUBNET · ${summary.subnet || "NOT DETECTED"}`;
    elements.gateway.textContent = network.gateway || "NOT SET";
    elements.gatewayLatency.textContent = network.gateway_latency_ms == null ? "NO RESPONSE" : `${Number(network.gateway_latency_ms).toFixed(1)} ms`;
    elements.healthScore.textContent = health || "—";
    elements.healthRing.style.strokeDashoffset = String(414.69 * (1 - health / 100));
    elements.healthRing.style.stroke = health >= 85 ? cssVarColor("--mint", "#9cffce") : health >= 65 ? cssVarColor("--orange", "#ffb65c") : cssVarColor("--danger", "#ff667a");
    elements.healthMessage.textContent = health >= 90 ? "すべての信号は良好です。" : health >= 75 ? "おおむね安定しています。" : health > 0 ? "注意が必要な信号があります。" : "テレメトリを取得しています…";
    elements.online.textContent = summary.online_devices ?? 0;
    elements.total.textContent = ` / ${summary.total_devices ?? 0}`;
    elements.packetLoss.textContent = `${Number(network.packet_loss_percent || 0).toFixed(1)}%`;
    elements.interface.textContent = String(network.interface || "—").toUpperCase();
    elements.uptime.textContent = formatDuration(system.uptime_seconds);
    elements.temperature.textContent = system.temperature_c == null ? "N/A" : `${Number(system.temperature_c).toFixed(1)}°C`;

    updateMetric("cpu", system.cpu_percent, `LOAD ${Number(system.load_1m || 0).toFixed(2)} / ${Number(system.load_5m || 0).toFixed(2)}`);
    updateMetric("memory", system.memory_percent, `${formatBytes(system.memory_used)} / ${formatBytes(system.memory_total)}`);
    updateMetric("disk", system.disk_percent, `${formatBytes(system.disk_used)} / ${formatBytes(system.disk_total)}`);

    applyTrafficSnapshot(snapshot.traffic || trafficFallback(snapshot));
    renderDevices();
    renderEvents(snapshot.events || []);
    renderHorizon(snapshot);
    updateTopologyNodes();
  }

  function updateMetric(name, value, detail) {
    const percent = clamp(value, 0, 100);
    elements[name].textContent = `${percent.toFixed(1)}%`;
    elements[`${name}Bar`].style.width = `${percent}%`;
    elements[`${name}Bar`].style.background = percent >= 90 ? cssVarColor("--danger", "#ff667a") : percent >= 75 ? cssVarColor("--orange", "#ffb65c") : `linear-gradient(90deg, ${cssVarColor("--cyan", "#4ce7db")}, ${cssVarColor("--mint", "#9cffce")})`;
    elements[`${name}Detail`].textContent = detail;
  }

  function renderDevices() {
    const query = state.search.toLowerCase();
    const filtered = state.devices.filter((device) => {
      const text = `${device.display_name || ""} ${device.hostname || ""} ${device.ip || ""} ${device.mac || ""}`.toLowerCase();
      const filterMatch = state.filter === "all" || (state.filter === "unknown" ? !device.is_trusted : device.status === state.filter);
      return filterMatch && (!query || text.includes(query));
    });
    if (!filtered.length) {
      elements.deviceRows.innerHTML = '<p class="device-empty">条件に一致する端末はありません。</p>';
      return;
    }
    elements.deviceRows.innerHTML = filtered.map((device) => {
      const name = device.display_name || device.hostname || `Device ${String(device.ip).split(".").pop()}`;
      const kind = device.device_type || "unknown";
      const latency = device.latency_ms == null ? "—" : `${Number(device.latency_ms).toFixed(1)} ms`;
      return `<article class="device-card" data-ip="${escapeHtml(device.ip)}">
        <div class="device-identity"><span class="device-icon">${typeIcons[kind] || "?"}</span><div>${escapeHtml(name)}${device.is_trusted ? '<span class="trusted">✓ TRUSTED</span>' : ""}<small>${escapeHtml(device.mac || "MAC UNKNOWN")}</small></div></div>
        <div class="device-card-data">
          <span class="mono">${escapeHtml(device.ip)}</span><span class="type-tag">${escapeHtml(kind)}</span>
          <span class="mono">${latency}</span><span class="mono">${relativeTime(device.last_seen)}</span>
          <span class="status ${device.status === "online" ? "online" : "offline"}"><i></i>${escapeHtml(String(device.status || "unknown").toUpperCase())}</span>
        </div>
      </article>`;
    }).join("");
  }

  function renderEvents(events) {
    elements.eventCount.textContent = `${events.length} EVENTS`;
    if (!events.length) {
      elements.eventList.innerHTML = '<p class="empty-events">イベントを待っています…</p>';
      return;
    }
    elements.eventList.innerHTML = events.slice(0, 9).map((event) => `<article class="event-item ${escapeHtml(event.severity)}">
      <i class="event-dot"></i><div class="event-copy"><strong>${escapeHtml(event.title)}</strong><span>${escapeHtml(event.detail)}</span></div><time class="event-time">${relativeTime(event.ts)}</time>
    </article>`).join("");
  }

  function renderLLMReport(report) {
    if (!report) {
      const configured = Boolean(state.llmSettings?.model);
      setMiniStatus(elements.llmReportStatus, state.llmSettings?.enabled ? "waiting" : configured ? "configured" : "disabled");
      elements.llmReportTime.textContent = "報告はまだありません";
      elements.llmReportModel.textContent = configured ? `${state.llmSettings.model} · 最初の分析を待っています。` : "LLMを設定すると監視結果を分析します。";
      elements.llmReportContent.textContent = configured ? "ANALYZE NOW で現在までの監視結果をすぐ分析できます。" : "右上の LLM SETTINGS からOpenAI互換のローカルLLMを設定してください。";
      return;
    }
    setMiniStatus(elements.llmReportStatus, report.status === "completed" ? "completed" : "error");
    elements.llmReportTime.textContent = formatDateTime(report.created_at);
    elements.llmReportModel.textContent = `${report.model} · ${report.context?.sample_count || 0} samples · ${report.context?.trigger === "scheduled" ? "scheduled" : "manual"}`;
    if (report.status === "completed") {
      elements.llmReportContent.innerHTML = renderMarkdown(report.content);
    } else {
      elements.llmReportContent.textContent = `分析に失敗しました: ${report.error || "原因不明"}`;
    }
  }

  function flavorTranscript(payload) {
    const reports = [...(payload.items || [])].reverse();
    if (!reports.length) {
      return ":: NO ARCHIVED LLM TRANSMISSIONS\n:: BUFFER STANDING BY\n:: RUN ANALYSIS TO ESTABLISH SIGNAL";
    }
    return reports.map((report, index) => {
      const sequence = String(index + 1).padStart(2, "0");
      const stamp = formatDateTime(report.created_at).replace(/\s+/g, " ");
      return `// TRACE ${sequence} · ${stamp}\n// MODEL ${report.model || "LOCAL"}\n${String(report.content || "").trim()}`;
    }).join("\n\n▓▒░ LINK CONTINUES ░▒▓\n\n");
  }

  function renderLLMFlavorStream(payload) {
    const items = payload.items || [];
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const signature = `${payload.scope}:${reducedMotion}:${items.map((report) => `${report.id}:${report.content?.length || 0}`).join(",")}`;
    elements.llmFlavorScope.textContent = String(payload.label || "直近3回分").toUpperCase();
    elements.llmFlavorStatus.textContent = items.length ? `${items.length} TRANSMISSIONS` : "BUFFER STANDING BY";
    if (signature === state.flavorSignature) return;
    state.flavorSignature = signature;
    state.flavorGeneration += 1;
    const generation = state.flavorGeneration;
    const transcript = flavorTranscript(payload);
    elements.llmFlavorStream.classList.toggle("reduced-motion", reducedMotion);
    elements.llmFlavorCursor.hidden = reducedMotion;

    if (reducedMotion) {
      elements.llmFlavorContent.textContent = transcript;
      elements.llmFlavorViewport.scrollTop = 0;
      return;
    }

    const characters = Array.from(transcript);
    const textNode = document.createTextNode("");
    elements.llmFlavorContent.replaceChildren(textNode);
    elements.llmFlavorViewport.scrollTop = 0;
    let position = 0;
    const typeNext = () => {
      if (generation !== state.flavorGeneration) return;
      if (position >= characters.length) {
        window.setTimeout(() => {
          if (generation !== state.flavorGeneration) return;
          textNode.data = "";
          position = 0;
          elements.llmFlavorViewport.scrollTop = 0;
          window.setTimeout(typeNext, 500);
        }, 4500);
        return;
      }
      const character = characters[position];
      textNode.appendData(character);
      position += 1;
      elements.llmFlavorViewport.scrollTop = elements.llmFlavorViewport.scrollHeight;
      const pause = character === "\n" ? 85 : /[。！？]/.test(character) ? 120 : 16;
      window.setTimeout(typeNext, pause);
    };
    window.setTimeout(typeNext, 350);
  }

  async function loadLLMSettings() {
    const response = await fetch("/api/v1/llm/settings");
    if (!response.ok) throw new Error(await apiError(response));
    state.llmSettings = await response.json();
    return state.llmSettings;
  }

  async function loadLLMReports() {
    try {
      const [settings, response, flavorResponse] = await Promise.all([
        loadLLMSettings(), fetch("/api/v1/llm/reports?limit=20"), fetch("/api/v1/llm/flavor-reports"),
      ]);
      if (!response.ok) throw new Error(await apiError(response));
      if (!flavorResponse.ok) throw new Error(await apiError(flavorResponse));
      const payload = await response.json();
      const flavorPayload = await flavorResponse.json();
      state.reports = payload.items || [];
      elements.llmRunButton.disabled = Boolean(payload.running);
      elements.llmRunButton.textContent = payload.running ? "ANALYZING…" : "ANALYZE NOW";
      elements.llmReportHistory.innerHTML = '<option value="">LATEST REPORT</option>' + state.reports.map((report) => `<option value="${report.id}">${escapeHtml(formatDateTime(report.created_at))} · ${escapeHtml(report.status.toUpperCase())}</option>`).join("");
      renderLLMReport(state.reports[0]);
      renderLLMFlavorStream(flavorPayload);
      if (!state.reports.length && settings.enabled) setMiniStatus(elements.llmReportStatus, "waiting");
    } catch (error) {
      console.warn("LLM report load failed", error);
      setMiniStatus(elements.llmReportStatus, "error");
      elements.llmReportContent.textContent = `LLM報告を読み込めません: ${error.message}`;
    }
  }

  function ensureSelectValue(select, value) {
    const normalized = String(value);
    if (![...select.options].some((option) => option.value === normalized)) {
      select.add(new Option(`${normalized}分`, normalized));
    }
    select.value = normalized;
  }

  async function openLLMSettings() {
    elements.llmSettingsStatus.textContent = "設定を読み込んでいます…";
    elements.llmSettingsDialog.showModal();
    try {
      const settings = await loadLLMSettings();
      elements.llmEnabled.checked = Boolean(settings.enabled);
      elements.llmBaseUrl.value = settings.base_url || "";
      elements.llmModel.value = settings.model || "";
      elements.llmSystemPrompt.value = settings.system_prompt || "";
      ensureSelectValue(elements.llmInterval, settings.interval_minutes);
      ensureSelectValue(elements.llmLookback, settings.lookback_minutes);
      elements.llmFlavorScopeSelect.value = settings.flavor_scope || "last_3";
      elements.llmApiKey.value = "";
      elements.llmClearApiKey.checked = false;
      elements.llmSettingsStatus.textContent = settings.api_key_configured ? "APIキーは暗号化して設定済みです。変更する場合だけ入力してください。" : "APIキーは未設定です。";
    } catch (error) { elements.llmSettingsStatus.textContent = `設定を読み込めません: ${error.message}`; }
  }

  async function loadNotifySettings() {
    const response = await fetch("/api/v1/notify/settings");
    if (!response.ok) throw new Error(await apiError(response));
    return response.json();
  }

  async function openNotifySettings() {
    elements.notifySettingsStatus.textContent = "設定を読み込んでいます…";
    elements.notifySettingsDialog.showModal();
    try {
      const settings = await loadNotifySettings();
      elements.notifyEnabled.checked = Boolean(settings.enabled);
      elements.notifyServerUrl.value = settings.server_url || "";
      elements.notifyTopic.value = settings.topic || "";
      ensureSelectValue(elements.notifyPriority, String(settings.priority));
      elements.notifyWebhookUrl.value = settings.webhook_url || "";
      elements.notifyWebhookToken.value = "";
      ensureSelectValue(elements.notifyCooldown, String(settings.cooldown_minutes));
      elements.notifyClearToken.checked = false;
      elements.notifySettingsStatus.textContent = settings.webhook_token_configured ? "Webhookトークンは暗号化して設定済みです。変更する場合だけ入力してください。" : "";
    } catch (error) { elements.notifySettingsStatus.textContent = `設定を読み込めません: ${error.message}`; }
  }

  async function loadTrafficSummary(days) {
    const range = Math.min(31, Math.max(1, Math.round(Number(days) || 7)));
    try {
      const [dailyResponse, rankResponse] = await Promise.all([
        fetch(`/api/v1/summary/daily?days=${range}`),
        fetch("/api/v1/summary/ranking?hours=24&limit=5"),
      ]);
      if (!dailyResponse.ok) throw new Error(await apiError(dailyResponse));
      if (!rankResponse.ok) throw new Error(await apiError(rankResponse));
      const dailyPayload = await dailyResponse.json();
      const rankPayload = await rankResponse.json();
      renderTrafficSummary(dailyPayload, rankPayload, range);
    } catch (error) {
      elements.trafficSummaryDaily.innerHTML = `<li class="summary-item error"><span>—</span><span class="summary-value">${escapeHtml(error.message)}</span></li>`;
      elements.trafficSummaryRanking.innerHTML = "<li class='summary-rank-item'>読み込めませんでした</li>";
    }
  }

  function renderTrafficSummary(dailyPayload, rankPayload, range) {
    const days = dailyPayload.days || [];
    elements.trafficSummaryDaysLabel.textContent = `LAST ${range} DAYS`;
    if (!days.length) {
      elements.trafficSummaryDaily.innerHTML = "<li class=\"summary-item empty\">データがありません</li>";
    } else {
      elements.trafficSummaryDaily.innerHTML = days.map((day) => {
        const date = new Date(day.day + "T00:00:00");
        const hours = day.peak_hour == null ? "—" : `${String(day.peak_hour).padStart(2, "0")}時台`;
        return `<li class="summary-item"><span>${escapeHtml(new Intl.DateTimeFormat("ja-JP", { month: "short", day: "numeric" }).format(date))} · ${escapeHtml(hours)}</span><span class="summary-value">${escapeHtml(formatBytes(day.total_bytes))}<small> ↓${escapeHtml(formatBytes(day.rx_bytes))} ↑${escapeHtml(formatBytes(day.tx_bytes))}</small></span></li>`;
      }).join("");
    }
    const items = rankPayload.items || [];
    elements.trafficSummaryRankLabel.textContent = `LAST ${Number(rankPayload.hours) || 24}H`;
    if (!items.length) {
      elements.trafficSummaryRanking.innerHTML = "<li class='summary-rank-item empty'>データがありません</li>";
    } else {
      elements.trafficSummaryRanking.innerHTML = items.map((item, index) => `<li class="summary-rank-item"><span class="rank-index">${index + 1}</span><span class="rank-name">${escapeHtml(item.label)}</span><span class="rank-value">${escapeHtml(formatBytes(item.total_bytes))}</span></li>`).join("");
    }
  }

  function setMiniStatus(element, value) {
    const status = String(value || "unknown").toLowerCase();
    element.className = `mini-status ${status}`;
    element.textContent = status.toUpperCase();
  }

  function renderHorizon(snapshot) {
    const connectivity = snapshot.connectivity || { status: "checking", checks: [] };
    setMiniStatus(elements.connectivityStatus, connectivity.lan_status || "disabled");
    const lanChecks = (connectivity.checks || []).filter((item) => String(item.check_type || "").startsWith("lan_"));
    const successfulChecks = lanChecks.filter((item) => item.success).length;
    elements.lanProbeCount.textContent = `${successfulChecks} / ${lanChecks.length}`;
    elements.lanLatency.textContent = connectivity.lan_latency_ms == null ? "—" : `${Number(connectivity.lan_latency_ms).toFixed(1)} ms`;
    elements.connectivityDetail.textContent = connectivity.lan_status === "online" ? `${lanChecks.length}件のLAN内サービスが正常です。` : connectivity.lan_status === "disabled" ? "LANプローブは未設定です。" : `${lanChecks.length}件中${successfulChecks}件が応答しています。`;

    const exporters = snapshot.exporters || { status: "disabled", online: 0, total: 0, items: [] };
    setMiniStatus(elements.exporterStatus, exporters.status);
    elements.exporterHosts.textContent = `${exporters.online || 0} / ${exporters.total || 0}`;
    const successfulExporters = (exporters.items || []).filter((item) => item.status === "online");
    const averageScrape = successfulExporters.length
      ? successfulExporters.reduce((sum, item) => sum + Number(item.duration_ms || 0), 0) / successfulExporters.length
      : null;
    elements.exporterLatency.textContent = averageScrape == null ? "—" : `${averageScrape.toFixed(0)} ms`;
    if (exporters.status === "ok") {
      elements.exporterDetail.textContent = `${exporters.online}台のホストメトリクスを直接収集中です。`;
    } else if (exporters.status === "degraded" || exporters.status === "error") {
      const failed = (exporters.items || []).filter((item) => item.status !== "online").map((item) => item.name).slice(0, 2);
      elements.exporterDetail.textContent = `${failed.join("、") || "Exporter"}から取得できません。`;
    } else {
      elements.exporterDetail.textContent = "node_exporter / windows_exporterの設定を待っています。";
    }

    const snmp = snapshot.snmp || { status: "disabled", details: [] };
    const qnapTargets = (snmp.details || []).filter((item) => item.profile === "qnap");
    const qnap = qnapTargets[0];
    const qnapStatus = qnap?.status === "degraded" || snmp.status === "degraded" ? "degraded" : qnap ? "online" : snmp.profile === "qnap" ? snmp.status : "disabled";
    setMiniStatus(elements.qnapStatus, qnapStatus);
    const disks = qnap?.disks || [];
    const healthyStates = new Set(["good", "ready", "normal", "ok", "active", "optimal"]);
    const healthyDisks = disks.filter((disk) => healthyStates.has(String(disk.status || "").toLowerCase())).length;
    const temperatures = disks.map((disk) => Number(disk.temperature_celsius)).filter(Number.isFinite);
    elements.qnapDisks.textContent = `${healthyDisks} / ${disks.length}`;
    elements.qnapTemperature.textContent = temperatures.length ? `${Math.max(...temperatures).toFixed(0)}°C` : "—";
    if (qnap) {
      const identity = qnap.identity || {};
      const storageSummary = `${qnap.raids?.length || 0} RAID · ${qnap.storage_pools?.length || 0} POOL · ${qnap.volumes?.length || 0} VOL`;
      elements.qnapDetail.textContent = `${identity.hostname || identity.model || "QNAP"} · ${storageSummary}${qnap.warnings?.length ? ` · ${qnap.warnings.length}件の注意` : ""}`;
    } else if (snmp.profile === "qnap" && ["unreachable", "error"].includes(snmp.status)) {
      elements.qnapDetail.textContent = "QNAPへ接続できません。SNMPv3のユーザー・認証方式・CBC-DES設定を確認してください。";
    } else {
      elements.qnapDetail.textContent = "QNAP SNMPv3プロファイルの設定を待っています。";
    }

    const agents = snapshot.agents || { online: 0, total: 0, items: [] };
    state.agents = agents.items || [];
    elements.agentCount.textContent = `${agents.online || 0} / ${agents.total || 0}`;
    elements.agentCount.className = `mini-status ${(agents.online || 0) > 0 ? "online" : agents.configured ? "checking" : "disabled"}`;
    if (agents.items?.length) {
      elements.agentNodes.innerHTML = agents.items.slice(0, 4).map((agent) => `<span class="agent-node ${agent.status === "online" ? "" : "offline"}"><i></i>${escapeHtml(agent.hostname)} · ${Number(agent.cpu_percent || 0).toFixed(0)}%</span>`).join("");
      const measuredSockets = agents.items.filter((agent) => agent.status === "online" && finiteNumber(agent.socket_count) != null).reduce((total, agent) => total + Number(agent.socket_count), 0);
      elements.agentDetail.textContent = `${agents.online}台がオンライン。CPU・メモリ・ディスク${measuredSockets ? `・${measuredSockets}ソケット` : ""}を受信中です。`;
    } else {
      elements.agentNodes.innerHTML = '<span class="agent-empty">Windows/Linuxエージェントを待っています。</span>';
      elements.agentDetail.textContent = agents.configured ? "登録トークンは準備済みです。" : "サーバー側の登録トークンが未設定です。";
    }
    elements.agentSetupTokenStatus.textContent = agents.configured
      ? "登録トークンはサーバー側で設定済みです。実行時に値を1回入力します。"
      : "先にRaspberry Pi上の .env に32文字以上の AGENT_TOKEN を設定し、NetPulseを再作成してください。";
    elements.agentSetupTokenStatus.classList.toggle("warning", !agents.configured);
    renderAgentManager();

    const insights = snapshot.insights || { status: "learning", learning_progress: 0, active: [] };
    setMiniStatus(elements.anomalyStatus, insights.status);
    const progress = clamp(insights.learning_progress, 0, 100);
    elements.learningBar.style.width = `${progress}%`;
    elements.learningProgress.textContent = `${progress}%`;
    if (insights.status === "anomaly" && insights.active?.length) {
      elements.anomalyDetail.textContent = `${insights.active[0].label}に通常と異なる動きを検出しました。`;
    } else if (insights.status === "normal") {
      elements.anomalyDetail.textContent = "現在の値は学習した通常パターン内です。";
    } else if (insights.status === "disabled") {
      elements.anomalyDetail.textContent = "異常学習は無効です。";
    } else {
      elements.anomalyDetail.textContent = "この時間帯の通常パターンを学習中です。";
    }
  }

  function topologyStatusClass(status) {
    const value = String(status || "unknown").toLowerCase();
    if (["error", "critical", "anomaly"].includes(value)) return "error";
    if (["warning", "degraded", "checking", "learning"].includes(value)) return "warning";
    if (["offline", "unreachable", "disabled", "unknown"].includes(value)) return "offline";
    return "online";
  }

  function topologyActivity(node) {
    if (topologyStatusClass(node.status) === "offline") return 0.03;
    const traffic = node.trafficMeasured ? topologyTrafficLevel(node.rxBps, node.txBps) : 0;
    const cpu = clamp((finiteNumber(node.cpuPercent) || 0) / 100, 0, 1);
    const sockets = clamp(Math.log10(Math.max(0, finiteNumber(node.socketCount) || 0) + 1) / 2.5, 0, 1);
    return clamp(0.08 + traffic * 0.55 + cpu * 0.22 + sockets * 0.15, 0.08, 1);
  }

  function topologyLoadLevel(node) {
    const weighted = [
      [finiteNumber(node.cpuPercent), 0.5],
      [finiteNumber(node.memoryPercent), 0.3],
      [finiteNumber(node.diskPercent), 0.2],
    ].filter(([value]) => value != null);
    if (!weighted.length) return null;
    const [total, scale] = weighted.reduce(
      ([sum, weightTotal], [value, weight]) => [sum + clamp(value, 0, 100) * weight, weightTotal + weight],
      [0, 0],
    );
    return scale ? clamp(total / (scale * 100), 0, 1) : null;
  }

  function topologyTrafficLevel(rxBps, txBps) {
    const rate = Math.max(0, finiteNumber(rxBps) || 0) + Math.max(0, finiteNumber(txBps) || 0);
    if (!rate) return 0;
    return clamp((Math.log10(rate) - 3) / 5, 0.04, 1);
  }

  function topologyTraffic(rxBps, txBps) {
    const measured = finiteNumber(rxBps) != null || finiteNumber(txBps) != null;
    const rx = Math.max(0, finiteNumber(rxBps) || 0);
    const tx = Math.max(0, finiteNumber(txBps) || 0);
    return {
      rxBps: rx,
      txBps: tx,
      trafficMeasured: measured,
      trafficLevel: measured ? topologyTrafficLevel(rx, tx) : 0,
      trafficRateLabel: measured ? formatRate(rx + tx) : "—",
    };
  }

  function renderTopologyInspector(node) {
    if (!node) return;
    state.selectedTopologyNode = node;
    elements.topologyNodeRole.textContent = `${String(node.role || "node").toUpperCase()} NODE`;
    elements.topologyNodeTitle.textContent = node.title || "UNKNOWN NODE";
    elements.topologyNodeSubtitle.textContent = node.subtitle || "—";
    const statusClass = topologyStatusClass(node.status);
    elements.topologyNodeState.className = `node-state ${statusClass}`;
    elements.topologyNodeState.textContent = String(node.status || "unknown").toUpperCase();
    elements.topologyNodeMetrics.replaceChildren();
    (node.metrics?.length ? node.metrics : [metric("STATUS", String(node.status || "unknown").toUpperCase())]).slice(0, 9).forEach((item) => {
      const wrapper = document.createElement("span");
      const label = document.createElement("small");
      const value = document.createElement("b");
      label.textContent = item.label;
      value.textContent = item.value;
      wrapper.append(label, value);
      elements.topologyNodeMetrics.append(wrapper);
    });
    const routeNote = node.trafficTargetId
      ? ` GATEWAYへ向かう発光ルートは、このノードで取得したNIC受信＋送信速度（${node.trafficRateLabel}）を表し、宛先別通信量ではありません。`
      : "";
    elements.topologyNodeDescription.textContent = `${node.description || "このノードから取得できる監視値を表示しています。"}${node.linkType && node.role !== "core" ? ` 観測経路: ${node.linkType}。` : ""}${routeNote}`;
    elements.topologyProfileButton.hidden = node.kind !== "device" || !node.ip;
  }

  function applyTopologyCardSettings() {
    const { mode, limit } = state.topologyCardSettings;
    state.topologyScene?.setCardConfig(mode, limit);
    elements.topologyCardSettingsButton.textContent = mode === "all" ? "CARDS: ALL" : `CARDS: TOP ${limit}`;
  }

  function syncTopologyCardLimitField() {
    elements.topologyCardLimit.disabled = elements.topologyCardMode.value === "all";
  }

  function openTopologyCardSettings() {
    const { mode, limit } = state.topologyCardSettings;
    elements.topologyCardMode.value = mode;
    elements.topologyCardLimit.value = String(limit);
    syncTopologyCardLimitField();
    elements.topologyCardSettingsStatus.textContent = "";
    elements.topologyCardSettingsDialog.showModal();
  }

  function closeTopologyCardSettings() {
    elements.topologyCardSettingsDialog.close();
  }

  function updateTopologyNodes() {
    const snapshot = state.snapshot || {};
    const system = snapshot.system || {};
    const network = snapshot.network || {};
    const summary = snapshot.summary || {};
    const nodes = [];
    const representedIps = new Set(network.ip_address ? [network.ip_address] : []);
    const health = finiteNumber(summary.health_score);
    const coreStatus = health == null ? "checking" : health >= 85 ? "online" : health >= 65 ? "degraded" : "error";
    const coreTraffic = topologyTraffic(network.rx_bps, network.tx_bps);

    nodes.push({
      id: "core:rp5", role: "core", kind: "system", status: coreStatus,
      title: "RP5 OBSERVER", subtitle: `${String(network.interface || "LOCAL NODE").toUpperCase()} · ${summary.subnet || "SUBNET DETECTING"}`,
      linkType: "LOCAL", socketCount: finiteNumber(system.socket_count), cpuPercent: finiteNumber(system.cpu_percent),
      memoryPercent: finiteNumber(system.memory_percent), diskPercent: finiteNumber(system.disk_percent),
      ...coreTraffic,
      metrics: compactMetrics(
        percentMetric("CPU", system.cpu_percent), percentMetric("MEM", system.memory_percent),
        percentMetric("DISK", system.disk_percent), temperatureMetric("TEMP", system.temperature_c),
        metric("RX", formatRate(network.rx_bps)), metric("TX", formatRate(network.tx_bps)),
        metric("LOAD 1M", finiteNumber(system.load_1m) == null ? "—" : Number(system.load_1m).toFixed(2)),
        metric("PROCESSES", finiteNumber(system.process_count) == null ? "—" : String(system.process_count)),
        metric("SOCKETS", finiteNumber(system.socket_count) == null ? "—" : String(system.socket_count)),
        metric("ESTAB", finiteNumber(system.established_socket_count) == null ? "—" : String(system.established_socket_count)),
        metric("LISTEN", finiteNumber(system.listening_socket_count) == null ? "—" : String(system.listening_socket_count)),
      ),
      description: "NetPulseを実行するRaspberry Pi 5です。システム負荷、プロセス数、この監視ノード自身のNIC通信量、INETソケット集計を表示しています。",
    });

    if (network.gateway) {
      representedIps.add(network.gateway);
      const snmpMetrics = snapshot.snmp?.metrics || {};
      const gatewayOnline = network.gateway_latency_ms != null;
      nodes.push({
        id: `gateway:${network.gateway}`, role: "gateway", kind: "gateway", status: gatewayOnline ? "online" : "offline",
        title: "NETWORK GATEWAY", subtitle: network.gateway,
        linkType: Object.keys(snmpMetrics).length ? "SNMP" : "ICMP", rxBps: finiteNumber(snmpMetrics.wan_rx_bps) || 0, txBps: finiteNumber(snmpMetrics.wan_tx_bps) || 0,
        trafficMeasured: false, trafficLevel: 0, trafficRateLabel: "—",
        metrics: compactMetrics(
          metric("LATENCY", network.gateway_latency_ms == null ? "NO RESPONSE" : `${Number(network.gateway_latency_ms).toFixed(1)} ms`),
          metric("LOSS", `${Number(network.packet_loss_percent || 0).toFixed(1)}%`),
          snmpMetrics.wan_rx_bps == null ? null : metric("WAN RX", formatRate(snmpMetrics.wan_rx_bps)),
          snmpMetrics.wan_tx_bps == null ? null : metric("WAN TX", formatRate(snmpMetrics.wan_tx_bps)),
        ),
        description: "デフォルトゲートウェイの到達性です。各監視ノードからここへ集まる発光ルートは端末側NICの合計通信量を示します。GATEWAYより先の経路は描画しません。WAN通信量はルーターSNMPで取得できた場合だけカード内に表示します。",
      });
    }

    (snapshot.snmp?.details || []).filter((item) => item.profile === "qnap").slice(0, 2).forEach((qnap, index) => {
      const qnapSystem = qnap.system || {};
      const identity = qnap.identity || {};
      const memoryTotal = finiteNumber(qnapSystem.memory_total_bytes);
      const memoryUsed = finiteNumber(qnapSystem.memory_used_bytes);
      const memoryPercent = memoryTotal && memoryUsed != null ? memoryUsed / memoryTotal * 100 : null;
      const diskTemperatures = (qnap.disks || []).map((disk) => finiteNumber(disk.temperature_celsius)).filter((value) => value != null);
      const warnings = qnap.warnings?.length || 0;
      if (qnap.target) representedIps.add(qnap.target);
      nodes.push({
        id: `qnap:${qnap.target || index}`, role: "qnap", kind: "qnap", status: warnings ? "degraded" : (qnap.status || "online"),
        title: identity.hostname || identity.model || "QNAP NAS", subtitle: [identity.model, qnap.target].filter(Boolean).join(" · "),
        linkType: "SNMP", rxBps: 0, txBps: 0, cpuPercent: finiteNumber(qnapSystem.cpu_percent), memoryPercent,
        metrics: compactMetrics(
          percentMetric("CPU", qnapSystem.cpu_percent), percentMetric("MEM", memoryPercent),
          temperatureMetric("CPU TEMP", qnapSystem.cpu_temperature_celsius),
          temperatureMetric("DISK TEMP", diskTemperatures.length ? Math.max(...diskTemperatures) : null),
          metric("DISKS", String(qnap.disks?.length || 0)), metric("WARN", String(warnings)),
        ),
        description: `${qnap.raids?.length || 0} RAID、${qnap.storage_pools?.length || 0}プール、${qnap.volumes?.length || 0}ボリュームをSNMPで観測しています。`,
      });
    });

    const appendHostNode = (host, role, index) => {
      const ip = host.source_ip || host.metadata?.hostname || "";
      if (ip) representedIps.add(ip);
      nodes.push({
        id: `${role}:${host.node_id || host.hostname || index}`, role, kind: "host", status: host.status || "unknown",
        title: host.hostname || host.node_id || role.toUpperCase(),
        subtitle: [host.os_name, ip].filter(Boolean).join(" · "),
        linkType: role === "agent" ? "AGENT" : "PROM", cpuPercent: finiteNumber(host.cpu_percent),
        memoryPercent: finiteNumber(host.memory_percent), diskPercent: finiteNumber(host.disk_percent),
        socketCount: finiteNumber(host.socket_count), ...topologyTraffic(host.rx_bps, host.tx_bps),
        metrics: compactMetrics(
          percentMetric("CPU", host.cpu_percent), percentMetric("MEM", host.memory_percent),
          percentMetric("DISK", host.disk_percent), temperatureMetric("TEMP", host.temperature_c),
          metric("RX", formatRate(host.rx_bps)), metric("TX", formatRate(host.tx_bps)),
          metric("LOAD 1M", finiteNumber(host.load_1m) == null ? null : Number(host.load_1m).toFixed(2)),
          metric("PROCESSES", finiteNumber(host.process_count) == null ? null : String(host.process_count)),
          metric("SOCKETS", finiteNumber(host.socket_count) == null ? "—" : String(host.socket_count)),
          metric("ESTAB", finiteNumber(host.established_socket_count) == null ? "—" : String(host.established_socket_count)),
          metric("LISTEN", finiteNumber(host.listening_socket_count) == null ? "—" : String(host.listening_socket_count)),
        ),
        description: role === "agent" ? "署名付きホストエージェントから受信した負荷・プロセス数・INETソケットなどの集計です。接続先アドレスや通信内容は収集しません。" : "Prometheus Exporterから取得したホストメトリクスです。Exporterが公開している場合だけ負荷・プロセス数・ソケット集計を表示します。",
      });
    };
    const orderedHosts = (items) => [...items].sort((first, second) => Number(inactiveTopologyStatuses.has(String(first.status || "unknown").toLowerCase())) - Number(inactiveTopologyStatuses.has(String(second.status || "unknown").toLowerCase())) || String(first.node_id || "").localeCompare(String(second.node_id || "")));
    orderedHosts(snapshot.agents?.items || []).slice(0, 6).forEach((host, index) => appendHostNode(host, "agent", index));
    orderedHosts(snapshot.exporters?.nodes || []).slice(0, 6).forEach((host, index) => appendHostNode(host, "exporter", index));

    const topologyDevices = [...state.devices]
      .filter((device) => !representedIps.has(device.ip))
      .sort((first, second) => Number(inactiveTopologyStatuses.has(String(first.status || "unknown").toLowerCase())) - Number(inactiveTopologyStatuses.has(String(second.status || "unknown").toLowerCase())) || String(first.ip).localeCompare(String(second.ip)));
    const inactiveDevices = topologyDevices.filter((device) => inactiveTopologyStatuses.has(String(device.status || "unknown").toLowerCase()));
    const activeDevices = topologyDevices.filter((device) => !inactiveTopologyStatuses.has(String(device.status || "unknown").toLowerCase()));
    const inactiveHostNodes = nodes.filter((node) => ["agent", "exporter"].includes(node.role) && inactiveTopologyStatuses.has(String(node.status || "unknown").toLowerCase()));
    const inactiveCandidates = [...inactiveHostNodes, ...inactiveDevices];
    const shouldGroupInactive = inactiveCandidates.length >= offlineGroupMinimum;

    if (shouldGroupInactive) {
      const inactiveHostIds = new Set(inactiveHostNodes.map((node) => node.id));
      for (let index = nodes.length - 1; index >= 0; index -= 1) {
        if (inactiveHostIds.has(nodes[index].id)) nodes.splice(index, 1);
      }
    }

    const remainingSlots = Math.max(0, topologyNodeLimit - nodes.length - (shouldGroupInactive ? 1 : 0));
    const individualDevices = (shouldGroupInactive ? activeDevices : topologyDevices).slice(0, remainingSlots);

    individualDevices.forEach((device) => {
      nodes.push({
        id: `device:${device.ip}`, role: "device", kind: "device", status: device.status || "unknown", ip: device.ip,
        title: device.display_name || device.hostname || device.ip, subtitle: `${String(device.device_type || "unknown").toUpperCase()} · ${device.ip}`,
        linkType: "DISCOVERY", rxBps: 0, txBps: 0,
        metrics: compactMetrics(
          metric("LATENCY", device.latency_ms == null ? "—" : `${Number(device.latency_ms).toFixed(1)} ms`),
          metric("SEEN", relativeTime(device.last_seen)), metric("TRUST", device.is_trusted ? "TRUSTED" : "UNSET"),
        ),
        description: "LAN探索で検出した端末です。CPUやメモリはエージェントまたはExporterを導入した場合だけ取得できます。",
      });
    });

    if (shouldGroupInactive) {
      const statusCounts = inactiveCandidates.reduce((counts, node) => {
        const status = String(node.status || "unknown").toLowerCase();
        counts[status] = (counts[status] || 0) + 1;
        return counts;
      }, {});
      const otherCount = inactiveCandidates.length - (statusCounts.offline || 0);
      nodes.push({
        id: "group:inactive-devices", role: "device-group", kind: "device-group", status: "offline",
        title: `INACTIVE DEVICES ×${inactiveCandidates.length}`,
        subtitle: "OFFLINE · UNREACHABLE · UNKNOWN",
        linkType: "DISCOVERY", rxBps: 0, txBps: 0,
        metrics: compactMetrics(
          metric("COUNT", String(inactiveCandidates.length)),
          metric("OFFLINE", String(statusCounts.offline || 0)),
          metric("OTHER", String(otherCount)),
        ),
        groupCount: inactiveCandidates.length,
        description: `${inactiveCandidates.length}台のオフライン・到達不能・状態不明の端末・監視ホストをまとめて表示しています。個別の状態は下の接続端末一覧とAGENT FLEETで確認できます。`,
      });
    }

    const gatewayNode = nodes.find((node) => node.role === "gateway");
    const activeNodes = nodes.map((node) => {
      const trafficTargetId = gatewayNode && node.role !== "gateway" && node.trafficMeasured ? gatewayNode.id : null;
      return { ...node, trafficTargetId, activityLevel: topologyActivity(node), loadLevel: topologyLoadLevel(node) };
    });
    state.topologyNodes = activeNodes;
    const liveCount = activeNodes.filter((node) => topologyStatusClass(node.status) === "online").length;
    const totalCount = activeNodes.reduce((total, node) => total + Math.max(1, Number(node.groupCount) || 1), 0);
    const groupedCount = activeNodes.reduce((total, node) => total + (Number(node.groupCount) || 0), 0);
    const liveSocketNodes = activeNodes.filter((node) => topologyStatusClass(node.status) === "online" && finiteNumber(node.socketCount) != null);
    const socketCount = liveSocketNodes.reduce((total, node) => total + Number(node.socketCount), 0);
    const processCount = Math.max(0, Number(system.process_count) || 0) + [...(snapshot.agents?.items || []), ...(snapshot.exporters?.nodes || [])].filter((host) => host.status === "online").reduce((total, host) => total + Math.max(0, Number(host.process_count) || 0), 0);
    const aggregateTraffic = snapshot.traffic?.total || {};
    const currentRate = Math.max(0, Number(aggregateTraffic.rx_bps) || 0) + Math.max(0, Number(aggregateTraffic.tx_bps) || 0);
    const observationLinkCount = Math.max(0, activeNodes.length - 1);
    const trafficRouteCount = activeNodes.filter((node) => node.trafficTargetId && topologyStatusClass(node.status) !== "offline").length;
    elements.topologyNodeCount.textContent = `${liveCount} LIVE / ${totalCount} NODES · ${observationLinkCount} OBS · ${trafficRouteCount} TRAFFIC${groupedCount ? ` · ${groupedCount} GROUPED` : ""}`;
    elements.topologyTrafficFlux.textContent = formatRate(currentRate);
    elements.topologySocketCount.textContent = liveSocketNodes.length ? String(socketCount) : "—";
    elements.topologyProcessCount.textContent = processCount ? String(processCount) : "—";
    elements.topologyLatencyReadout.textContent = network.gateway_latency_ms == null ? "—" : `${Number(network.gateway_latency_ms).toFixed(1)} ms`;
    state.topologyScene?.setNodes(activeNodes);
  }

  function sizeCanvas(canvas) {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.floor(rect.width * dpr));
    const height = Math.max(1, Math.floor(rect.height * dpr));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const context = canvas.getContext("2d");
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { context, width: rect.width, height: rect.height };
  }

  function drawTraffic() {
    const { context: ctx, width, height } = sizeCanvas(elements.traffic);
    ctx.clearRect(0, 0, width, height);
    const chartMint = cssVarColor("--mint", "#9cffce");
    const chartViolet = cssVarColor("--violet", "#a78bfa");
    const padding = { x: 10, y: 12 }, chartWidth = width - padding.x * 2, chartHeight = height - padding.y * 2;
    ctx.strokeStyle = withAlpha(chartMint, 0.07); ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i += 1) { const y = padding.y + chartHeight * i / 4; ctx.beginPath(); ctx.moveTo(padding.x, y); ctx.lineTo(width - padding.x, y); ctx.stroke(); }
    const maximum = Math.max(1024, ...state.rx, ...state.tx) * 1.18;
    const drawSeries = (values, color, fill) => {
      if (values.length < 2) return;
      const points = values.map((value, index) => ({ x: padding.x + chartWidth * index / (maxPoints - 1), y: padding.y + chartHeight * (1 - value / maximum) }));
      ctx.beginPath(); ctx.moveTo(points[0].x, points[0].y);
      points.slice(1).forEach((point, index) => { const previous = points[index]; const middle = (previous.x + point.x) / 2; ctx.bezierCurveTo(middle, previous.y, middle, point.y, point.x, point.y); });
      if (fill) { const gradient = ctx.createLinearGradient(0, padding.y, 0, height); gradient.addColorStop(0, fill); gradient.addColorStop(1, "transparent"); ctx.lineTo(points[points.length - 1].x, height - padding.y); ctx.lineTo(points[0].x, height - padding.y); ctx.closePath(); ctx.fillStyle = gradient; ctx.fill(); }
      ctx.beginPath(); ctx.moveTo(points[0].x, points[0].y); points.slice(1).forEach((point, index) => { const previous = points[index]; const middle = (previous.x + point.x) / 2; ctx.bezierCurveTo(middle, previous.y, middle, point.y, point.x, point.y); });
      ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.shadowBlur = 6; ctx.shadowColor = color; ctx.stroke(); ctx.shadowBlur = 0;
    };
    drawSeries(state.rx, chartMint, withAlpha(chartMint, 0.12));
    drawSeries(state.tx, chartViolet, withAlpha(chartViolet, 0.06));
  }

  async function loadInitial() {
    try {
      const [snapshotResponse, trafficResponse] = await Promise.all([fetch("/api/v1/snapshot"), fetch("/api/v1/traffic?minutes=2&points=60")]);
      if (!snapshotResponse.ok || !trafficResponse.ok) throw new Error("API unavailable");
      loadTrafficHistory(await trafficResponse.json());
      applySnapshot(await snapshotResponse.json());
    } catch (error) { console.warn("Initial telemetry load failed", error); }
  }

  function connect() {
    window.clearTimeout(state.reconnectTimer);
    setConnection("connecting");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}/ws/live`);
    state.socket = socket;
    socket.addEventListener("open", () => setConnection("connected"));
    socket.addEventListener("message", (event) => { try { applySnapshot(JSON.parse(event.data)); } catch (error) { console.warn("Invalid live payload", error); } });
    socket.addEventListener("close", () => { setConnection("disconnected"); state.reconnectTimer = window.setTimeout(connect, 3000); });
    socket.addEventListener("error", () => socket.close());
  }

  async function pollSnapshot() {
    // Browsers cannot attach an Authorization header to a WebSocket, so while the
    // live socket is unavailable (e.g. when basic auth is enabled) fall back to
    // polling the REST snapshot. Same-origin fetch still sends the browser's
    // Basic credentials, so the UI keeps updating after login.
    if (state.socket?.readyState === WebSocket.OPEN) return;
    try {
      const response = await fetch("/api/v1/snapshot");
      if (!response.ok) return;
      applySnapshot(await response.json());
    } catch (error) { console.warn("Snapshot poll failed", error); }
  }

  function openDevice(ip) {
    const device = state.devices.find((item) => item.ip === ip);
    if (!device) return;
    state.selectedIp = ip;
    elements.dialogIp.textContent = ip;
    elements.dialogName.value = device.display_name || "";
    elements.dialogType.value = device.device_type || "unknown";
    elements.dialogTrusted.checked = Boolean(device.is_trusted);
    elements.dialog.showModal();
  }

  function openAgentSetup() {
    const server = window.location.origin.replace(/\/$/, "");
    elements.windowsInstallCommand.textContent = `$u='${server}'; $p=Join-Path $env:TEMP 'netpulse-install.ps1'; Invoke-WebRequest "$u/agent/install-windows.ps1" -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Server $u`;
    elements.linuxInstallCommand.textContent = `curl -fsSL '${server}/agent/install-linux.sh' -o /tmp/netpulse-install.sh && sudo sh /tmp/netpulse-install.sh '${server}'`;
    elements.windowsUninstallCommand.textContent = `$u='${server}'; $p=Join-Path $env:TEMP 'netpulse-uninstall.ps1'; Invoke-WebRequest "$u/agent/uninstall-windows.ps1" -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p`;
    elements.linuxUninstallCommand.textContent = `curl -fsSL '${server}/agent/uninstall-linux.sh' -o /tmp/netpulse-uninstall.sh && sudo sh /tmp/netpulse-uninstall.sh`;
    setAgentSetupMode("install");
    elements.agentSetupDialog.showModal();
  }

  function setAgentSetupMode(mode) {
    document.querySelectorAll("[data-agent-setup-mode]").forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.agentSetupMode === mode));
    });
    document.querySelectorAll("[data-agent-setup-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.agentSetupPanel !== mode;
    });
  }

  function renderAgentManager() {
    elements.agentManageButton.disabled = state.agents.length === 0;
    if (!state.agents.length) {
      elements.agentManageList.innerHTML = '<span class="agent-empty">登録済みエージェントはありません。</span>';
      return;
    }
    elements.agentManageList.innerHTML = state.agents.map((agent) => {
      const online = agent.status === "online";
      const address = agent.source_ip && agent.source_ip !== "unknown" ? agent.source_ip : "IP不明";
      return `<article class="agent-manage-row">
        <span class="agent-manager-state ${online ? "online" : "offline"}"><i></i>${online ? "ONLINE" : "OFFLINE"}</span>
        <div class="agent-manager-identity"><strong>${escapeHtml(agent.hostname)}</strong><span>${escapeHtml(address)} · ${relativeTime(agent.last_seen)}</span><code>${escapeHtml(agent.node_id)}</code></div>
        <button class="agent-remove-button" type="button" data-agent-id="${escapeHtml(agent.node_id)}">DELETE</button>
      </article>`;
    }).join("");
  }

  function openAgentManager() {
    elements.agentManageStatus.textContent = "";
    renderAgentManager();
    elements.agentManageDialog.showModal();
  }

  function openAgentDelete(nodeId) {
    const agent = state.agents.find((item) => item.node_id === nodeId);
    if (!agent) return;
    state.selectedAgent = agent;
    elements.agentDeleteName.textContent = agent.hostname || agent.node_id;
    elements.agentDeleteAddress.textContent = agent.source_ip && agent.source_ip !== "unknown" ? agent.source_ip : "IPアドレス不明";
    elements.agentDeleteId.textContent = agent.node_id;
    elements.agentDeleteStatus.textContent = "";
    elements.agentDeleteConfirm.disabled = false;
    elements.agentDeleteDialog.showModal();
  }

  function closeAgentDelete() {
    elements.agentDeleteDialog.close();
    state.selectedAgent = null;
  }

  async function deleteSelectedAgent(event) {
    event.preventDefault();
    const agent = state.selectedAgent;
    if (!agent) return;
    elements.agentDeleteConfirm.disabled = true;
    elements.agentDeleteStatus.textContent = "削除しています…";
    try {
      const response = await fetch(`/api/v1/agents/${encodeURIComponent(agent.node_id)}`, { method: "DELETE" });
      if (!response.ok) throw new Error(await apiError(response));
      const result = await response.json();
      closeAgentDelete();
      const snapshotResponse = await fetch("/api/v1/snapshot");
      if (snapshotResponse.ok) applySnapshot(await snapshotResponse.json());
      elements.agentManageStatus.textContent = `${result.hostname} を削除しました。保存済み通信履歴 ${result.deleted_traffic_samples || 0} 件も削除済みです。`;
    } catch (error) {
      elements.agentDeleteStatus.textContent = `削除できません: ${error.message}`;
      elements.agentDeleteConfirm.disabled = false;
    }
  }

  async function copyAgentCommand(button) {
    const target = $(button.dataset.copyTarget);
    if (!target) return;
    const command = target.textContent;
    let copied = false;
    try {
      if (!navigator.clipboard) throw new Error("Clipboard API unavailable");
      await navigator.clipboard.writeText(command);
      copied = true;
    } catch (_error) {
      const textarea = document.createElement("textarea");
      textarea.value = command;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      copied = document.execCommand("copy");
      textarea.remove();
    }
    if (!copied) {
      const range = document.createRange();
      range.selectNodeContents(target);
      window.getSelection()?.removeAllRanges();
      window.getSelection()?.addRange(range);
    }
    button.textContent = copied ? "COPIED" : "SELECT TEXT";
    window.setTimeout(() => { button.textContent = "COPY"; }, copied ? 1200 : 2200);
  }

  elements.search.addEventListener("input", (event) => { state.search = event.target.value; renderDevices(); });
  document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active"); state.filter = button.dataset.filter; renderDevices();
  }));
  elements.deviceRows.addEventListener("click", (event) => { const row = event.target.closest("[data-ip]"); if (row) openDevice(row.dataset.ip); });
  elements.trafficTabs.addEventListener("click", (event) => {
    const tab = event.target.closest("[role=tab]");
    if (tab) selectTrafficSource(tab.dataset.sourceId);
  });
  elements.trafficTabs.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = [...elements.trafficTabs.querySelectorAll("[role=tab]")];
    if (!tabs.length) return;
    const current = Math.max(0, tabs.indexOf(event.target.closest("[role=tab]")));
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
      : (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    selectTrafficSource(tabs[next].dataset.sourceId, true);
  });
  elements.topologyProfileButton.addEventListener("click", () => {
    if (state.selectedTopologyNode?.ip) openDevice(state.selectedTopologyNode.ip);
  });
  elements.topologyCardSettingsButton.addEventListener("click", openTopologyCardSettings);
  elements.topologyCardSettingsClose.addEventListener("click", closeTopologyCardSettings);
  elements.topologyCardSettingsCancel.addEventListener("click", closeTopologyCardSettings);
  elements.topologyCardMode.addEventListener("change", syncTopologyCardLimitField);
  elements.topologyCardSettingsForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const settings = {
      mode: elements.topologyCardMode.value === "top" ? "top" : "all",
      limit: Math.min(topologyCardLimits, Math.max(1, Number(elements.topologyCardLimit.value) || 1)),
    };
    state.topologyCardSettings = settings;
    try { localStorage.setItem(topologyCardsKey, JSON.stringify(settings)); } catch (_) { /* Storage can be disabled. */ }
    applyTopologyCardSettings();
    elements.topologyCardSettingsStatus.textContent = "設定を保存しました。星図に即適用されました。";
    window.setTimeout(closeTopologyCardSettings, 650);
  });
  elements.agentSetupButton.addEventListener("click", openAgentSetup);
  document.querySelectorAll("[data-agent-setup-mode]").forEach((button) => button.addEventListener("click", () => setAgentSetupMode(button.dataset.agentSetupMode)));
  elements.agentManageButton.addEventListener("click", openAgentManager);
  elements.agentManageClose.addEventListener("click", () => elements.agentManageDialog.close());
  elements.agentManageList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-agent-id]");
    if (button) openAgentDelete(button.dataset.agentId);
  });
  elements.agentDeleteForm.addEventListener("submit", deleteSelectedAgent);
  elements.agentDeleteClose.addEventListener("click", closeAgentDelete);
  elements.agentDeleteCancel.addEventListener("click", closeAgentDelete);
  document.querySelectorAll(".agent-copy-button").forEach((button) => button.addEventListener("click", () => copyAgentCommand(button)));
  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedIp) return;
    const response = await fetch(`/api/v1/devices/${encodeURIComponent(state.selectedIp)}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: elements.dialogName.value.trim() || null, device_type: elements.dialogType.value, is_trusted: elements.dialogTrusted.checked }),
    });
    if (response.ok) { const updated = await response.json(); state.devices = state.devices.map((item) => item.ip === updated.ip ? { ...item, ...updated, is_trusted: Boolean(updated.is_trusted) } : item); renderDevices(); updateTopologyNodes(); elements.dialog.close(); }
  });

  elements.llmSettingsButton.addEventListener("click", openLLMSettings);
  elements.llmSettingsClose.addEventListener("click", () => elements.llmSettingsDialog.close());
  elements.llmSettingsCancel.addEventListener("click", () => elements.llmSettingsDialog.close());
  elements.llmReportHistory.addEventListener("change", () => {
    const selected = state.reports.find((report) => String(report.id) === elements.llmReportHistory.value);
    renderLLMReport(selected || state.reports[0]);
  });
  elements.llmLoadModels.addEventListener("click", async () => {
    elements.llmLoadModels.disabled = true;
    elements.llmSettingsStatus.textContent = "モデル一覧を取得しています…";
    const payload = { base_url: elements.llmBaseUrl.value.trim() };
    if (elements.llmApiKey.value) payload.api_key = elements.llmApiKey.value;
    try {
      const response = await fetch("/api/v1/llm/models", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await apiError(response));
      const body = await response.json();
      elements.llmModelOptions.innerHTML = (body.models || []).map((model) => `<option value="${escapeHtml(model.id)}">${escapeHtml(model.display_name || model.id)}</option>`).join("");
      elements.llmSettingsStatus.textContent = `${body.models.length}件の生成モデルを取得しました。候補にないモデルも手入力できます。`;
    } catch (error) { elements.llmSettingsStatus.textContent = `${error.message} モデル名は手入力できます。`; }
    finally { elements.llmLoadModels.disabled = false; }
  });
  elements.llmSettingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      enabled: elements.llmEnabled.checked,
      base_url: elements.llmBaseUrl.value.trim(),
      model: elements.llmModel.value.trim(),
      system_prompt: elements.llmSystemPrompt.value.trim(),
      interval_minutes: Number(elements.llmInterval.value),
      lookback_minutes: Number(elements.llmLookback.value),
      flavor_scope: elements.llmFlavorScopeSelect.value,
    };
    if (elements.llmClearApiKey.checked) payload.api_key = "";
    else if (elements.llmApiKey.value) payload.api_key = elements.llmApiKey.value;
    elements.llmSettingsStatus.textContent = "設定を保存しています…";
    try {
      const response = await fetch("/api/v1/llm/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await apiError(response));
      state.llmSettings = await response.json();
      elements.llmSettingsStatus.textContent = "設定を保存しました。引用範囲はすぐ表示に反映されます。";
      window.setTimeout(() => elements.llmSettingsDialog.close(), 650);
      await loadLLMReports();
    } catch (error) { elements.llmSettingsStatus.textContent = `保存できません: ${error.message}`; }
  });
  elements.llmRunButton.addEventListener("click", async () => {
    elements.llmRunButton.disabled = true;
    elements.llmRunButton.textContent = "ANALYZING…";
    setMiniStatus(elements.llmReportStatus, "running");
    elements.llmReportContent.textContent = "監視データを集約し、ローカルLLMで分析しています…";
    try {
      const response = await fetch("/api/v1/llm/reports/run", { method: "POST" });
      if (!response.ok) throw new Error(await apiError(response));
      await response.json();
      await loadLLMReports();
    } catch (error) {
      setMiniStatus(elements.llmReportStatus, "error");
      elements.llmReportContent.textContent = `分析できません: ${error.message}`;
    } finally {
      elements.llmRunButton.disabled = false;
      elements.llmRunButton.textContent = "ANALYZE NOW";
    }
  });

  state.topologyScene = window.NetPulseTopology3D?.create({
    canvas: elements.topology,
    labelLayer: elements.topologyLabelLayer,
    onSelect: renderTopologyInspector,
    onModeChange: (mode) => {
      const fallback = mode !== "webgl";
      elements.topologyRenderMode.className = `render-mode${fallback ? " fallback" : ""}`;
      elements.topologyRenderMode.textContent = fallback ? "2D · SAFE MODE" : "WEBGL 3D · ACTIVE";
    },
    onFrameStats: ({ fps, objects }) => {
      elements.topologyFrameRate.textContent = `${fps} FPS`;
      elements.topologyObjectCount.textContent = `${objects} OBJECTS`;
    },
  }) || null;
  if (!state.topologyScene) {
    elements.topologyRenderMode.className = "render-mode fallback";
    elements.topologyRenderMode.textContent = "RENDERER · OFFLINE";
  }
  applyTopologyCardSettings();

  elements.notifySettingsButton.addEventListener("click", openNotifySettings);
  elements.notifySettingsClose.addEventListener("click", () => elements.notifySettingsDialog.close());
  elements.notifySettingsCancel.addEventListener("click", () => elements.notifySettingsDialog.close());
  elements.themeSettingsButton.addEventListener("click", () => elements.themeDialog.showModal());
  elements.themeClose.addEventListener("click", () => elements.themeDialog.close());
  elements.notifyTestButton.addEventListener("click", async () => {
    elements.notifyTestButton.disabled = true;
    elements.notifySettingsStatus.textContent = "テスト通知を送信しています…";
    try {
      const response = await fetch("/api/v1/notify/test", { method: "POST" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || await apiError(response));
      elements.notifySettingsStatus.textContent = body.message || "テスト通知を送信しました。";
    } catch (error) { elements.notifySettingsStatus.textContent = `テスト送信できません: ${error.message}`; }
    finally { elements.notifyTestButton.disabled = false; }
  });
  elements.notifySettingsForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      enabled: elements.notifyEnabled.checked,
      server_url: elements.notifyServerUrl.value.trim(),
      topic: elements.notifyTopic.value.trim(),
      priority: Number(elements.notifyPriority.value),
      webhook_url: elements.notifyWebhookUrl.value.trim(),
      cooldown_minutes: Number(elements.notifyCooldown.value),
    };
    if (elements.notifyClearToken.checked) payload.webhook_token = "";
    else if (elements.notifyWebhookToken.value) payload.webhook_token = elements.notifyWebhookToken.value;
    elements.notifySettingsStatus.textContent = "設定を保存しています…";
    try {
      const response = await fetch("/api/v1/notify/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await apiError(response));
      elements.notifySettingsStatus.textContent = "設定を保存しました。";
      window.setTimeout(() => elements.notifySettingsDialog.close(), 650);
    } catch (error) { elements.notifySettingsStatus.textContent = `保存できません: ${error.message}`; }
  });

  window.setInterval(() => { elements.clock.textContent = new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date()); }, 1000);
  window.setInterval(() => { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send("ping"); }, 20000);
  window.setInterval(loadLLMReports, 60000);
  window.setInterval(() => loadTrafficSummary(7), 300000);
  window.setInterval(pollSnapshot, 5000);
  window.addEventListener("resize", drawTraffic);

  loadInitial();
  loadLLMReports();
  loadTrafficSummary(7);
  connect();
})();
