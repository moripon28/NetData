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
    topologyStage: $("topologyStage"), topologyLabelLayer: $("topologyLabelLayer"),
    topologyRenderMode: $("topologyRenderMode"), topologyNodeCount: $("topologyNodeCount"),
    topologyNodeRole: $("topologyNodeRole"), topologyNodeTitle: $("topologyNodeTitle"),
    topologyNodeSubtitle: $("topologyNodeSubtitle"), topologyNodeState: $("topologyNodeState"),
    topologyNodeMetrics: $("topologyNodeMetrics"), topologyNodeDescription: $("topologyNodeDescription"),
    topologyProfileButton: $("topologyProfileButton"),
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
    llmClearApiKey: $("llmClearApiKey"), llmSettingsStatus: $("llmSettingsStatus"),
  };

  const state = {
    snapshot: null, devices: [], rx: [], tx: [], filter: "all", search: "", selectedIp: null,
    topologyNodes: [], topologyScene: null, selectedTopologyNode: null,
    socket: null, reconnectTimer: null, reports: [], llmSettings: null,
  };
  const fontSizeKey = "netpulse.fontSize";
  const fontSizes = new Set(["small", "medium", "large"]);
  const fontSizeButtons = [...document.querySelectorAll("[data-font-size]")];
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
    drawTraffic();
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
    elements.agentCount.textContent = `${agents.online || 0} / ${agents.total || 0}`;
    elements.agentCount.className = `mini-status ${(agents.online || 0) > 0 ? "online" : agents.configured ? "checking" : "disabled"}`;
    if (agents.items?.length) {
      elements.agentNodes.innerHTML = agents.items.slice(0, 4).map((agent) => `<span class="agent-node ${agent.status === "online" ? "" : "offline"}"><i></i>${escapeHtml(agent.hostname)} · ${Number(agent.cpu_percent || 0).toFixed(0)}%</span>`).join("");
      elements.agentDetail.textContent = `${agents.online}台がオンライン。CPU・メモリ・ディスクを受信中です。`;
    } else {
      elements.agentNodes.innerHTML = '<span class="agent-empty">Windows/Linuxエージェントを待っています。</span>';
      elements.agentDetail.textContent = agents.configured ? "登録トークンは準備済みです。" : "サーバー側の登録トークンが未設定です。";
    }
    elements.agentSetupTokenStatus.textContent = agents.configured
      ? "登録トークンはサーバー側で設定済みです。実行時に値を1回入力します。"
      : "先にRaspberry Pi上の .env に32文字以上の AGENT_TOKEN を設定し、NetPulseを再作成してください。";
    elements.agentSetupTokenStatus.classList.toggle("warning", !agents.configured);

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
    (node.metrics?.length ? node.metrics : [metric("STATUS", String(node.status || "unknown").toUpperCase())]).slice(0, 6).forEach((item) => {
      const wrapper = document.createElement("span");
      const label = document.createElement("small");
      const value = document.createElement("b");
      label.textContent = item.label;
      value.textContent = item.value;
      wrapper.append(label, value);
      elements.topologyNodeMetrics.append(wrapper);
    });
    elements.topologyNodeDescription.textContent = node.description || "このノードから取得できる監視値を表示しています。";
    elements.topologyProfileButton.hidden = node.kind !== "device" || !node.ip;
  }

  function updateTopologyNodes() {
    const snapshot = state.snapshot || {};
    const system = snapshot.system || {};
    const network = snapshot.network || {};
    const summary = snapshot.summary || {};
    const nodes = [];
    const representedIps = new Set();
    const health = finiteNumber(summary.health_score);
    const coreStatus = health == null ? "checking" : health >= 85 ? "online" : health >= 65 ? "degraded" : "error";

    nodes.push({
      id: "core:rp5", role: "core", kind: "system", status: coreStatus,
      title: "RP5 OBSERVER", subtitle: `${String(network.interface || "LOCAL NODE").toUpperCase()} · ${summary.subnet || "SUBNET DETECTING"}`,
      metrics: compactMetrics(
        percentMetric("CPU", system.cpu_percent), percentMetric("MEM", system.memory_percent),
        percentMetric("DISK", system.disk_percent), temperatureMetric("TEMP", system.temperature_c),
        metric("RX", formatRate(network.rx_bps)), metric("TX", formatRate(network.tx_bps)),
      ),
      description: "NetPulseを実行するRaspberry Pi 5です。主要なシステム負荷と、この監視ノード自身のNIC通信量を表示しています。",
    });

    if (network.gateway) {
      representedIps.add(network.gateway);
      const snmpMetrics = snapshot.snmp?.metrics || {};
      const gatewayOnline = network.gateway_latency_ms != null;
      nodes.push({
        id: `gateway:${network.gateway}`, role: "gateway", kind: "gateway", status: gatewayOnline ? "online" : "offline",
        title: "NETWORK GATEWAY", subtitle: network.gateway,
        metrics: compactMetrics(
          metric("LATENCY", network.gateway_latency_ms == null ? "NO RESPONSE" : `${Number(network.gateway_latency_ms).toFixed(1)} ms`),
          metric("LOSS", `${Number(network.packet_loss_percent || 0).toFixed(1)}%`),
          snmpMetrics.wan_rx_bps == null ? null : metric("WAN RX", formatRate(snmpMetrics.wan_rx_bps)),
          snmpMetrics.wan_tx_bps == null ? null : metric("WAN TX", formatRate(snmpMetrics.wan_tx_bps)),
        ),
        description: "デフォルトゲートウェイの到達性です。WAN通信量はルーターSNMPで取得できた場合だけ表示します。",
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
        metrics: compactMetrics(
          percentMetric("CPU", host.cpu_percent), percentMetric("MEM", host.memory_percent),
          percentMetric("DISK", host.disk_percent), temperatureMetric("TEMP", host.temperature_c),
          metric("RX", formatRate(host.rx_bps)), metric("TX", formatRate(host.tx_bps)),
        ),
        description: role === "agent" ? "署名付きホストエージェントから受信した内部メトリクスです。" : "Prometheus Exporterから取得したホストメトリクスです。",
      });
    };
    (snapshot.agents?.items || []).slice(0, 6).forEach((host, index) => appendHostNode(host, "agent", index));
    (snapshot.exporters?.nodes || []).slice(0, 6).forEach((host, index) => appendHostNode(host, "exporter", index));

    const remainingSlots = Math.max(0, 18 - nodes.length);
    [...state.devices]
      .filter((device) => !representedIps.has(device.ip))
      .sort((first, second) => Number(second.status === "online") - Number(first.status === "online"))
      .slice(0, remainingSlots)
      .forEach((device) => {
        nodes.push({
          id: `device:${device.ip}`, role: "device", kind: "device", status: device.status || "unknown", ip: device.ip,
          title: device.display_name || device.hostname || device.ip, subtitle: `${String(device.device_type || "unknown").toUpperCase()} · ${device.ip}`,
          metrics: compactMetrics(
            metric("LATENCY", device.latency_ms == null ? "—" : `${Number(device.latency_ms).toFixed(1)} ms`),
            metric("SEEN", relativeTime(device.last_seen)), metric("TRUST", device.is_trusted ? "TRUSTED" : "UNSET"),
          ),
          description: "LAN探索で検出した端末です。CPUやメモリはエージェントまたはExporterを導入した場合だけ取得できます。",
        });
      });

    state.topologyNodes = nodes;
    const liveCount = nodes.filter((node) => topologyStatusClass(node.status) === "online").length;
    elements.topologyNodeCount.textContent = `${liveCount} LIVE / ${nodes.length} NODES`;
    state.topologyScene?.setNodes(nodes);
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

  function openAgentSetup() {
    const server = window.location.origin.replace(/\/$/, "");
    elements.windowsInstallCommand.textContent = `$u='${server}'; $p=Join-Path $env:TEMP 'netpulse-install.ps1'; Invoke-WebRequest "$u/agent/install-windows.ps1" -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Server $u`;
    elements.linuxInstallCommand.textContent = `curl -fsSL '${server}/agent/install-linux.sh' -o /tmp/netpulse-install.sh && sudo sh /tmp/netpulse-install.sh '${server}'`;
    elements.agentSetupDialog.showModal();
  }

  async function copyAgentCommand(button) {
    const target = $(button.dataset.copyTarget);
    if (!target) return;
    const command = target.textContent;
    try {
      if (!navigator.clipboard) throw new Error("Clipboard API unavailable");
      await navigator.clipboard.writeText(command);
    } catch (_error) {
      const textarea = document.createElement("textarea");
      textarea.value = command;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    button.textContent = "COPIED";
    window.setTimeout(() => { button.textContent = "COPY"; }, 1200);
  }

  elements.search.addEventListener("input", (event) => { state.search = event.target.value; renderDevices(); });
  document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active"); state.filter = button.dataset.filter; renderDevices();
  }));
  elements.deviceRows.addEventListener("click", (event) => { const row = event.target.closest("tr[data-ip]"); if (row) openDevice(row.dataset.ip); });
  elements.topologyProfileButton.addEventListener("click", () => {
    if (state.selectedTopologyNode?.ip) openDevice(state.selectedTopologyNode.ip);
  });
  elements.agentSetupButton.addEventListener("click", openAgentSetup);
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

  state.topologyScene = window.NetPulseTopology3D?.create({
    canvas: elements.topology,
    labelLayer: elements.topologyLabelLayer,
    onSelect: renderTopologyInspector,
    onModeChange: (mode) => {
      const fallback = mode !== "webgl";
      elements.topologyRenderMode.className = `render-mode${fallback ? " fallback" : ""}`;
      elements.topologyRenderMode.textContent = fallback ? "2D · SAFE MODE" : "WEBGL · ACTIVE";
    },
  }) || null;
  if (!state.topologyScene) {
    elements.topologyRenderMode.className = "render-mode fallback";
    elements.topologyRenderMode.textContent = "RENDERER · OFFLINE";
  }

  window.setInterval(() => { elements.clock.textContent = new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date()); }, 1000);
  window.setInterval(() => { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send("ping"); }, 20000);
  window.setInterval(loadLLMReports, 60000);
  window.addEventListener("resize", drawTraffic);

  loadInitial();
  loadLLMReports();
  connect();
})();
