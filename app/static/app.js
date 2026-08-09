(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const elements = {
    connection: $("connectionPill"), clock: $("clock"), subnet: $("subnetLabel"), gateway: $("gatewayLabel"),
    gatewayLatency: $("gatewayLatency"), healthScore: $("healthScore"), healthRing: $("healthRing"),
    healthMessage: $("healthMessage"), online: $("onlineDevices"), total: $("totalDevices"),
    packetLoss: $("packetLoss"), interface: $("interfaceName"), uptime: $("uptime"),
    down: $("downloadRate"), up: $("uploadRate"), temperature: $("temperature"),
    cpu: $("cpuValue"), cpuBar: $("cpuBar"), cpuDetail: $("cpuDetail"),
    memory: $("memoryValue"), memoryBar: $("memoryBar"), memoryDetail: $("memoryDetail"),
    disk: $("diskValue"), diskBar: $("diskBar"), diskDetail: $("diskDetail"),
    deviceRows: $("deviceRows"), eventList: $("eventList"), eventCount: $("eventCount"),
    search: $("deviceSearch"), topology: $("topologyCanvas"), traffic: $("trafficCanvas"),
    dialog: $("deviceDialog"), form: $("deviceForm"), dialogIp: $("dialogIp"), dialogName: $("dialogName"),
    dialogType: $("dialogType"), dialogTrusted: $("dialogTrusted"),
    connectivityStatus: $("connectivityStatus"), internetLatency: $("internetLatency"), dnsLatency: $("dnsLatency"),
    connectivityDetail: $("connectivityDetail"), snmpStatus: $("snmpStatus"), snmpDown: $("snmpDown"),
    snmpUp: $("snmpUp"), snmpDetail: $("snmpDetail"), agentCount: $("agentCount"), agentNodes: $("agentNodes"),
    agentDetail: $("agentDetail"), anomalyStatus: $("anomalyStatus"), learningBar: $("learningBar"),
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
    llmClearApiKey: $("llmClearApiKey"), llmSettingsStatus: $("llmSettingsStatus"),
  };

  const state = {
    snapshot: null, devices: [], rx: [], tx: [], filter: "all", search: "", selectedIp: null,
    topologyNodes: [], particles: [], socket: null, reconnectTimer: null, reports: [], llmSettings: null,
  };
  const maxPoints = 60;
  const typeIcons = { router: "⌁", computer: "▣", phone: "▯", tablet: "▭", tv: "▰", iot: "◇", server: "▤", printer: "▥", camera: "◉", game: "✦", unknown: "?" };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
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
    elements.healthRing.style.stroke = health >= 85 ? "#9cffce" : health >= 65 ? "#ffb65c" : "#ff667a";
    elements.healthMessage.textContent = health >= 90 ? "すべての信号は良好です。" : health >= 75 ? "おおむね安定しています。" : health > 0 ? "注意が必要な信号があります。" : "テレメトリを取得しています…";
    elements.online.textContent = summary.online_devices ?? 0;
    elements.total.textContent = ` / ${summary.total_devices ?? 0}`;
    elements.packetLoss.textContent = `${Number(network.packet_loss_percent || 0).toFixed(1)}%`;
    elements.interface.textContent = String(network.interface || "—").toUpperCase();
    elements.uptime.textContent = formatDuration(system.uptime_seconds);
    elements.down.textContent = formatRate(network.rx_bps);
    elements.up.textContent = formatRate(network.tx_bps);
    elements.temperature.textContent = system.temperature_c == null ? "N/A" : `${Number(system.temperature_c).toFixed(1)}°C`;

    updateMetric("cpu", system.cpu_percent, `LOAD ${Number(system.load_1m || 0).toFixed(2)} / ${Number(system.load_5m || 0).toFixed(2)}`);
    updateMetric("memory", system.memory_percent, `${formatBytes(system.memory_used)} / ${formatBytes(system.memory_total)}`);
    updateMetric("disk", system.disk_percent, `${formatBytes(system.disk_used)} / ${formatBytes(system.disk_total)}`);

    pushPoint(network.rx_bps, network.tx_bps);
    renderDevices();
    renderEvents(snapshot.events || []);
    renderHorizon(snapshot);
    updateTopologyNodes();
  }

  function updateMetric(name, value, detail) {
    const percent = clamp(value, 0, 100);
    elements[name].textContent = `${percent.toFixed(1)}%`;
    elements[`${name}Bar`].style.width = `${percent}%`;
    elements[`${name}Bar`].style.background = percent >= 90 ? "#ff667a" : percent >= 75 ? "#ffb65c" : "linear-gradient(90deg, #4ce7db, #9cffce)";
    elements[`${name}Detail`].textContent = detail;
  }

  function pushPoint(rx, tx) {
    state.rx.push(Number(rx) || 0);
    state.tx.push(Number(tx) || 0);
    if (state.rx.length > maxPoints) state.rx.shift();
    if (state.tx.length > maxPoints) state.tx.shift();
  }

  function renderDevices() {
    const query = state.search.toLowerCase();
    const filtered = state.devices.filter((device) => {
      const text = `${device.display_name || ""} ${device.hostname || ""} ${device.ip || ""} ${device.mac || ""}`.toLowerCase();
      const filterMatch = state.filter === "all" || (state.filter === "unknown" ? !device.is_trusted : device.status === state.filter);
      return filterMatch && (!query || text.includes(query));
    });
    if (!filtered.length) {
      elements.deviceRows.innerHTML = '<tr class="empty-row"><td colspan="6">条件に一致する端末はありません。</td></tr>';
      return;
    }
    elements.deviceRows.innerHTML = filtered.map((device) => {
      const name = device.display_name || device.hostname || `Device ${String(device.ip).split(".").pop()}`;
      const kind = device.device_type || "unknown";
      const latency = device.latency_ms == null ? "—" : `${Number(device.latency_ms).toFixed(1)} ms`;
      return `<tr data-ip="${escapeHtml(device.ip)}">
        <td><div class="device-identity"><span class="device-icon">${typeIcons[kind] || "?"}</span><div>${escapeHtml(name)}${device.is_trusted ? '<span class="trusted">✓ TRUSTED</span>' : ""}<small>${escapeHtml(device.mac || "MAC UNKNOWN")}</small></div></div></td>
        <td class="mono">${escapeHtml(device.ip)}</td><td><span class="type-tag">${escapeHtml(kind)}</span></td>
        <td class="mono">${latency}</td><td class="mono">${relativeTime(device.last_seen)}</td>
        <td><span class="status ${device.status === "online" ? "online" : "offline"}"><i></i>${escapeHtml(String(device.status || "unknown").toUpperCase())}</span></td>
      </tr>`;
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
    elements.llmReportContent.textContent = report.status === "completed" ? report.content : `分析に失敗しました: ${report.error || "原因不明"}`;
  }

  async function loadLLMSettings() {
    const response = await fetch("/api/v1/llm/settings");
    if (!response.ok) throw new Error(await apiError(response));
    state.llmSettings = await response.json();
    return state.llmSettings;
  }

  async function loadLLMReports() {
    try {
      const [settings, response] = await Promise.all([loadLLMSettings(), fetch("/api/v1/llm/reports?limit=20")]);
      if (!response.ok) throw new Error(await apiError(response));
      const payload = await response.json();
      state.reports = payload.items || [];
      elements.llmRunButton.disabled = Boolean(payload.running);
      elements.llmRunButton.textContent = payload.running ? "ANALYZING…" : "ANALYZE NOW";
      elements.llmReportHistory.innerHTML = '<option value="">LATEST REPORT</option>' + state.reports.map((report) => `<option value="${report.id}">${escapeHtml(formatDateTime(report.created_at))} · ${escapeHtml(report.status.toUpperCase())}</option>`).join("");
      renderLLMReport(state.reports[0]);
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
      elements.llmApiKey.value = "";
      elements.llmClearApiKey.checked = false;
      elements.llmSettingsStatus.textContent = settings.api_key_configured ? "APIキーは暗号化して設定済みです。変更する場合だけ入力してください。" : "APIキーは未設定です。";
    } catch (error) { elements.llmSettingsStatus.textContent = `設定を読み込めません: ${error.message}`; }
  }

  function setMiniStatus(element, value) {
    const status = String(value || "unknown").toLowerCase();
    element.className = `mini-status ${status}`;
    element.textContent = status.toUpperCase();
  }

  function renderHorizon(snapshot) {
    const connectivity = snapshot.connectivity || { status: "checking", checks: [] };
    setMiniStatus(elements.connectivityStatus, connectivity.status);
    elements.internetLatency.textContent = connectivity.internet_latency_ms == null ? "—" : `${Number(connectivity.internet_latency_ms).toFixed(1)} ms`;
    elements.dnsLatency.textContent = connectivity.dns_latency_ms == null ? "—" : `${Number(connectivity.dns_latency_ms).toFixed(1)} ms`;
    const successfulChecks = (connectivity.checks || []).filter((item) => item.success).length;
    const totalChecks = (connectivity.checks || []).length;
    elements.connectivityDetail.textContent = connectivity.status === "online" ? `${totalChecks}経路中${successfulChecks}経路が正常です。` : connectivity.status === "disabled" ? "外部疎通チェックは無効です。" : `${totalChecks}経路中${successfulChecks}経路が応答しています。`;

    const snmp = snapshot.snmp || { status: "disabled", metrics: {} };
    setMiniStatus(elements.snmpStatus, snmp.status);
    elements.snmpDown.textContent = snmp.metrics?.wan_rx_bps == null ? "—" : formatRate(snmp.metrics.wan_rx_bps);
    elements.snmpUp.textContent = snmp.metrics?.wan_tx_bps == null ? "—" : formatRate(snmp.metrics.wan_tx_bps);
    elements.snmpDetail.textContent = snmp.status === "ok" ? `${(snmp.targets || []).length}台のSNMPテレメトリを受信中です。` : snmp.status === "unreachable" ? "SNMP応答がありません。設定を確認してください。" : "ルーターのSNMP設定を待っています。";

    const agents = snapshot.agents || { online: 0, total: 0, items: [] };
    elements.agentCount.textContent = `${agents.online || 0} / ${agents.total || 0}`;
    elements.agentCount.className = `mini-status ${(agents.online || 0) > 0 ? "online" : agents.configured ? "checking" : "disabled"}`;
    if (agents.items?.length) {
      elements.agentNodes.innerHTML = agents.items.slice(0, 4).map((agent) => `<span class="agent-node ${agent.status === "online" ? "" : "offline"}"><i></i>${escapeHtml(agent.hostname)} · ${Number(agent.cpu_percent || 0).toFixed(0)}%</span>`).join("");
      elements.agentDetail.textContent = `${agents.online}台がオンライン。CPU・メモリ・ディスクを受信中です。`;
    } else {
      elements.agentNodes.innerHTML = '<span class="agent-empty">Windows/Linuxエージェントを待っています。</span>';
      elements.agentDetail.textContent = agents.configured ? "登録トークンは準備済みです。" : "サーバー側の登録トークンが未設定です。";
    }

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

  function updateTopologyNodes() {
    const onlineFirst = [...state.devices].sort((a, b) => Number(b.status === "online") - Number(a.status === "online"));
    state.topologyNodes = onlineFirst.slice(0, 12);
    const particleTarget = Math.min(28, state.topologyNodes.filter((device) => device.status === "online").length * 3);
    while (state.particles.length < particleTarget) state.particles.push({ node: state.particles.length % Math.max(1, state.topologyNodes.length), progress: Math.random(), speed: .002 + Math.random() * .004, reverse: Math.random() > .65 });
    state.particles.length = particleTarget;
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

  function drawTopology(now) {
    const { context: ctx, width, height } = sizeCanvas(elements.topology);
    ctx.clearRect(0, 0, width, height);
    const cx = width / 2, cy = height / 2;
    const count = Math.max(1, state.topologyNodes.length);
    const radiusX = Math.min(width * .39, 350), radiusY = Math.min(height * .36, 145);
    const positions = [];

    ctx.strokeStyle = "rgba(156,255,206,.055)"; ctx.lineWidth = 1;
    for (let radius = 48; radius < Math.max(radiusX, radiusY) + 45; radius += 48) {
      ctx.beginPath(); ctx.ellipse(cx, cy, Math.min(radius, radiusX), Math.min(radius * .55, radiusY), 0, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.setLineDash([3, 7]);
    state.topologyNodes.forEach((device, index) => {
      const angle = -Math.PI / 2 + (index / count) * Math.PI * 2;
      const stagger = 1 + ((index % 3) - 1) * .09;
      const x = cx + Math.cos(angle) * radiusX * stagger;
      const y = cy + Math.sin(angle) * radiusY * stagger;
      positions.push({ x, y });
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y);
      ctx.strokeStyle = device.status === "online" ? "rgba(156,255,206,.18)" : "rgba(110,130,122,.1)"; ctx.stroke();
    });
    ctx.setLineDash([]);

    const corePulse = 2 + Math.sin(now / 450) * 2;
    ctx.beginPath(); ctx.arc(cx, cy, 52 + corePulse, 0, Math.PI * 2); ctx.fillStyle = "rgba(156,255,206,.035)"; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, 43, 0, Math.PI * 2); ctx.strokeStyle = "rgba(156,255,206,.42)"; ctx.lineWidth = 1; ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 35, 0, Math.PI * 2); ctx.fillStyle = "rgba(10,28,23,.95)"; ctx.fill();

    state.particles.forEach((particle) => {
      if (!positions.length) return;
      particle.node %= positions.length;
      particle.progress = (particle.progress + particle.speed) % 1;
      const target = positions[particle.node];
      const progress = particle.reverse ? 1 - particle.progress : particle.progress;
      const x = cx + (target.x - cx) * progress, y = cy + (target.y - cy) * progress;
      ctx.beginPath(); ctx.arc(x, y, 1.7, 0, Math.PI * 2); ctx.fillStyle = particle.reverse ? "#a78bfa" : "#9cffce"; ctx.shadowBlur = 9; ctx.shadowColor = ctx.fillStyle; ctx.fill(); ctx.shadowBlur = 0;
    });

    state.topologyNodes.forEach((device, index) => {
      const { x, y } = positions[index];
      const online = device.status === "online";
      ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.fillStyle = online ? "rgba(12,31,26,.96)" : "rgba(14,20,18,.96)"; ctx.fill();
      ctx.strokeStyle = online ? "rgba(156,255,206,.5)" : "rgba(100,120,112,.28)"; ctx.stroke();
      ctx.fillStyle = online ? "#9cffce" : "#66756f"; ctx.font = "12px Consolas, monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(typeIcons[device.device_type] || "?", x, y);
      const label = String(device.display_name || device.hostname || device.ip).slice(0, 18);
      ctx.font = "9px Segoe UI, sans-serif"; ctx.fillStyle = online ? "#d7e9e0" : "#6f7f78"; ctx.textBaseline = "top"; ctx.fillText(label, x, y + 25);
      ctx.font = "7px Consolas, monospace"; ctx.fillStyle = "#61736c"; ctx.fillText(device.ip || "", x, y + 38);
    });
  }

  function drawTraffic() {
    const { context: ctx, width, height } = sizeCanvas(elements.traffic);
    ctx.clearRect(0, 0, width, height);
    const padding = { x: 10, y: 12 }, chartWidth = width - padding.x * 2, chartHeight = height - padding.y * 2;
    ctx.strokeStyle = "rgba(156,255,206,.07)"; ctx.lineWidth = 1;
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
    drawSeries(state.rx, "#9cffce", "rgba(156,255,206,.12)");
    drawSeries(state.tx, "#a78bfa", "rgba(167,139,250,.06)");
  }

  function animate(now) { drawTopology(now); drawTraffic(); requestAnimationFrame(animate); }

  async function loadInitial() {
    try {
      const [snapshotResponse, historyResponse] = await Promise.all([fetch("/api/v1/snapshot"), fetch("/api/v1/history?minutes=5")]);
      if (!snapshotResponse.ok || !historyResponse.ok) throw new Error("API unavailable");
      const history = await historyResponse.json();
      state.rx = (history.samples || []).slice(-maxPoints).map((sample) => Number(sample.rx_bps) || 0);
      state.tx = (history.samples || []).slice(-maxPoints).map((sample) => Number(sample.tx_bps) || 0);
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

  elements.search.addEventListener("input", (event) => { state.search = event.target.value; renderDevices(); });
  document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active"); state.filter = button.dataset.filter; renderDevices();
  }));
  elements.deviceRows.addEventListener("click", (event) => { const row = event.target.closest("tr[data-ip]"); if (row) openDevice(row.dataset.ip); });
  elements.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedIp) return;
    const response = await fetch(`/api/v1/devices/${encodeURIComponent(state.selectedIp)}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: elements.dialogName.value.trim() || null, device_type: elements.dialogType.value, is_trusted: elements.dialogTrusted.checked }),
    });
    if (response.ok) { const updated = await response.json(); state.devices = state.devices.map((item) => item.ip === updated.ip ? { ...item, ...updated, is_trusted: Boolean(updated.is_trusted) } : item); renderDevices(); elements.dialog.close(); }
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
    };
    if (elements.llmClearApiKey.checked) payload.api_key = "";
    else if (elements.llmApiKey.value) payload.api_key = elements.llmApiKey.value;
    elements.llmSettingsStatus.textContent = "設定を保存しています…";
    try {
      const response = await fetch("/api/v1/llm/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await apiError(response));
      state.llmSettings = await response.json();
      elements.llmSettingsStatus.textContent = "設定を保存しました。次の分析から反映されます。";
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

  window.setInterval(() => { elements.clock.textContent = new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date()); }, 1000);
  window.setInterval(() => { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send("ping"); }, 20000);
  window.setInterval(loadLLMReports, 60000);
  window.addEventListener("resize", () => { drawTraffic(); drawTopology(performance.now()); });

  loadInitial();
  loadLLMReports();
  connect();
  requestAnimationFrame(animate);
})();
