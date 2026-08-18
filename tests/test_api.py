from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_snapshot_and_static_ui(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    app = create_app(settings)
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        snapshot = client.get("/api/v1/snapshot")
        assert snapshot.status_code == 200
        assert snapshot.json()["type"] == "snapshot"

        index = client.get("/")
        assert index.status_code == 200
        assert "NETPULSE" in index.text
        assert "EASY SETUP" in index.text
        assert "RAW WEBGL" in index.text
        assert "SPATIAL TELEMETRY" in index.text
        assert 'src="/static/topology3d.js?v=20260818-card-settings"' in index.text
        assert 'src="/static/app.js?v=20260818-xlarge"' in index.text
        assert 'data-font-size="small"' in index.text
        assert 'data-font-size="medium"' in index.text
        assert 'data-font-size="large"' in index.text
        assert 'data-font-size="xlarge"' in index.text
        assert "netpulse.fontSize" in index.text
        assert 'id="topologyNodeMetrics"' in index.text
        assert 'id="trafficTabs"' in index.text
        assert 'role="tablist"' in index.text
        assert 'id="llmFlavorStream"' in index.text
        assert 'id="llmFlavorScope"' in index.text
        assert 'id="agentManageDialog"' in index.text
        assert 'id="agentDeleteDialog"' in index.text
        assert 'id="topologyCardSettingsButton"' in index.text
        assert 'id="topologyCardSettingsDialog"' in index.text
        assert 'id="topologyCardMode"' in index.text
        assert 'id="topologyCardLimit"' in index.text
        assert "MANAGE" in index.text
        assert "接続端末、通信量、遅延、Raspberry Piの状態をリアルタイムに観測します。" not in index.text
        assert '/static/styles.css?v=20260818-flavor' in index.text
        assert '/static/app.js?v=20260818-xlarge' in index.text
        assert "TRAFFIC LOW → SURGE" in index.text
        assert '<div class="health-value"><strong id="healthScore">--</strong></div>' in index.text
        assert "<small>HEALTH</small>" not in index.text

        topology_script = client.get("/static/topology3d.js")
        assert topology_script.status_code == 200
        assert "NetPulseTopology3D" in topology_script.text
        assert "findLabelPlacement" in topology_script.text
        assert "reservedLabelRects" in topology_script.text
        assert '".llm-flavor-stream"' not in topology_script.text
        assert '".topology-inspector"' not in topology_script.text
        assert "collidesWithCard" in topology_script.text
        assert "collidesWithReserved" in topology_script.text
        assert "appendCandidate" in topology_script.text
        assert "createSphereMesh" in topology_script.text
        assert "meshVertex" in topology_script.text
        assert "gl.DEPTH_TEST" in topology_script.text
        assert "drawMesh" in topology_script.text
        assert "gl.POINTS" in topology_script.text
        assert "updateLabelLeader" in topology_script.text
        assert "appendTrafficGlow" in topology_script.text
        assert "trafficColor" in topology_script.text
        assert "trafficTargetId" in topology_script.text
        assert "node-flow-readout" in topology_script.text
        assert "compactRateLabel" in topology_script.text
        assert "setCardConfig" in topology_script.text
        assert "computeCardVisibleIds" in topology_script.text
        assert '"is-card-hidden"' in topology_script.text

        app_script = client.get("/static/app.js")
        assert app_script.status_code == 200
        assert "offlineGroupMinimum = 4" in app_script.text
        assert "INACTIVE DEVICES ×" in app_script.text
        assert "topologySocketCount" in app_script.text
        assert "liveSocketNodes" in app_script.text
        assert 'role === "agent" ? "AGENT" : "PROM"' in app_script.text
        assert "topologyTrafficLevel" in app_script.text
        assert "trafficTargetId" in app_script.text
        assert "GATEWAYより先の経路は描画しません" in app_script.text
        assert 'method: "DELETE"' in app_script.text
        assert "renderAgentManager" in app_script.text
        assert "uninstall-windows.ps1" in app_script.text
        assert "uninstall-linux.sh" in app_script.text
        assert 'copied ? "COPIED" : "SELECT TEXT"' in app_script.text
        assert "netpulse.topologyCards" in app_script.text
        assert "loadTopologyCardSettings" in app_script.text
        assert "setCardConfig" in app_script.text

        styles = client.get("/static/styles.css")
        assert styles.status_code == 200
        assert ".command-rail .health-orbit { width: 116px; height: 116px; }" in styles.text
        assert ".command-rail .health-ring { width: 100px; height: 100px; }" in styles.text
        assert ".command-rail .health-value strong { font-size: 32px; }" in styles.text
        assert ".health-value { position: absolute; inset: 0; display: grid; place-items: center; pointer-events: none; }" in styles.text
        assert "min-width: calc(112 * var(--ui-font-unit))" in styles.text
        assert "max-width: calc(180 * var(--ui-font-unit))" in styles.text
        assert ".topology-node-label.selected .node-label-metrics { display: flex; }" in styles.text
        assert ".llm-flavor-stream { position: absolute; z-index: 8;" in styles.text
        assert ".node-label-glance" in styles.text
        assert ".node-flow-readout" in styles.text
        assert ".node-traffic-meter" in styles.text
        assert 'data-font-size="large"] .llm-flavor-stream' not in styles.text
        assert 'data-font-size="xlarge"] .llm-flavor-stream' not in styles.text
        assert 'html[data-font-size="large"] .topology-stage { min-height: 862px; }' in styles.text
        assert 'html[data-font-size="xlarge"] { --ui-font-unit: 1.5px; }' in styles.text
        assert ".topology-volume" in styles.text
        assert ".topology-depth-rail" in styles.text
        assert "--leader-length" in styles.text
        assert ".topology-panel { min-height: 806px; display: flex; flex-direction: column; }" in styles.text
        assert ".topology-stage { min-height: 742px; flex: 1 1 auto;" in styles.text
        assert ".command-deck .topology-stage { min-height: 620px; }" in styles.text
        assert "@media (min-width: 1921px)" in styles.text
        assert ".dashboard { width: clamp(1680px, calc(100% - 320px), 3200px); }" in styles.text
        assert ".command-deck { grid-template-columns: minmax(0, 1fr) clamp(420px, 20vw, 560px); }" in styles.text
        assert ".topology-node-label.is-card-hidden { display: none; }" in styles.text
        assert ".topology-head-action" in styles.text

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "netpulse_health_score" in metrics.text


def test_external_probes_are_opt_in_and_lan_probe_state_is_exposed(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        lan_probe_targets=("gateway=icmp://192.168.10.1",),
    )
    app = create_app(settings)
    assert app.state.monitor.connectivity.internet_targets == ()
    assert app.state.monitor.connectivity.dns_servers == ()
    assert app.state.monitor.connectivity.lan_targets[0].name == "gateway"
    with TestClient(app) as client:
        snapshot = client.get("/api/v1/snapshot").json()
        assert snapshot["connectivity"]["lan_status"] == "checking"
        assert snapshot["connectivity"]["external_status"] == "disabled"


def test_agent_install_files_are_available_without_exposing_other_files(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    app = create_app(settings)
    expected = {
        "install-windows.ps1": "NetPulseAgent",
        "install-linux.sh": "netpulse-agent.service",
        "uninstall-windows.ps1": "Unregister-ScheduledTask",
        "uninstall-linux.sh": "systemctl disable --now",
        "netpulse_agent.py": "/api/v1/agent/heartbeat",
        "requirements.txt": "psutil",
    }
    with TestClient(app) as client:
        for filename, marker in expected.items():
            response = client.get(f"/agent/{filename}")
            assert response.status_code == 200
            assert marker in response.text
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["x-content-type-options"] == "nosniff"

        assert client.get("/agent/README.md").status_code == 404


def test_demo_mode_produces_devices(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False, demo_mode=True)
    app = create_app(settings)
    with TestClient(app) as client:
        snapshot = app.state.monitor
        client.portal.call(snapshot.collect_once)
        payload = client.get("/api/v1/snapshot").json()
        assert payload["summary"]["online_devices"] == 6
        assert payload["network"]["rx_bps"] > 0
        assert payload["system"]["socket_count"] == 86
        assert payload["system"]["process_count"] == 147
        assert len(payload["devices"]) == 6


def test_signed_agent_heartbeat(tmp_path):
    token = "test-token-that-is-long-enough-01"
    settings = Settings(
        data_dir=tmp_path, collector_enabled=False, discovery_enabled=False, agent_token=token
    )
    app = create_app(settings)
    payload = {
        "node_id": "node-1234", "hostname": "workstation", "os_name": "Windows",
        "cpu_percent": 12.5, "memory_percent": 45.0, "disk_percent": 60.0,
        "load_1m": 0.78, "process_count": 214,
        "uptime_seconds": 86400, "rx_bps": 512.0, "tx_bps": 128.0,
        "socket_count": 42, "established_socket_count": 9, "listening_socket_count": 5,
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(token.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/heartbeat",
            content=body,
            headers={"Content-Type": "application/json", "X-Agent-Timestamp": timestamp, "X-Agent-Signature": signature},
        )
        assert response.status_code == 200
        agents = client.get("/api/v1/agents").json()
        assert agents["online"] == 1
        assert agents["items"][0]["hostname"] == "workstation"
        assert agents["items"][0]["socket_count"] == 42
        assert agents["items"][0]["process_count"] == 214
        app.state.monitor.latest["generated_at"] = time.time()
        app.state.monitor.latest["network"].update(
            {"interface": "eth0", "ip_address": "192.168.10.201", "rx_bps": 1024.0, "tx_bps": 256.0}
        )
        snapshot = client.get("/api/v1/snapshot").json()
        assert snapshot["agents"]["items"][0]["cpu_percent"] == 12.5
        assert snapshot["agents"]["items"][0]["established_socket_count"] == 9
        assert snapshot["agents"]["items"][0]["load_1m"] == 0.78
        assert snapshot["traffic"]["source_count"] == 2
        assert snapshot["traffic"]["total"]["rx_bps"] == 1536.0
        assert {item["id"] for item in snapshot["traffic"]["sources"]} == {"local", "agent:node-1234"}
        traffic = client.get("/api/v1/traffic?minutes=1&points=20")
        assert traffic.status_code == 200
        assert len(traffic.json()["series"]["all"]) == 20
        assert len(traffic.json()["series"]["agent:node-1234"]) == 20

        deleted = client.delete("/api/v1/agents/node-1234")
        assert deleted.status_code == 200
        assert deleted.json() == {
            "status": "deleted", "node_id": "node-1234", "hostname": "workstation",
            "source_ip": "testclient", "deleted_traffic_samples": 1,
        }
        assert client.get("/api/v1/agents").json()["total"] == 0
        assert "agent:node-1234" not in client.get("/api/v1/traffic?minutes=1&points=20").json()["series"]
        assert 'node_id="node-1234"' not in client.get("/metrics").text
        assert client.delete("/api/v1/agents/node-1234").status_code == 404


def test_agent_rejects_bad_signature(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, agent_token="server-secret-32char-test-value-00")
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/heartbeat",
            content=b"{}",
            headers={"X-Agent-Timestamp": str(int(time.time())), "X-Agent-Signature": "bad"},
        )
        assert response.status_code == 401


def test_prometheus_exporter_nodes_are_separate_from_signed_agents(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        prometheus_exporters_enabled=True,
        prometheus_exporter_targets=("nas=http://192.168.10.20:9100/metrics",),
    )
    app = create_app(settings)
    sample = {
        "node_id": "exporter-test",
        "hostname": "nas",
        "os_name": "Linux",
        "os_version": "6.12",
        "agent_version": "node_exporter",
        "cpu_percent": 10.0,
        "memory_percent": 20.0,
        "disk_percent": 30.0,
        "temperature_c": 40.0,
        "uptime_seconds": 1000,
        "rx_bps": 123.0,
        "tx_bps": 45.0,
        "metadata": {
            "collection_method": "prometheus",
            "exporter_kind": "node_exporter",
            "target_name": "nas",
        },
    }
    status = {
        "name": "nas", "url": "http://192.168.10.20:9100/metrics", "status": "online",
        "kind": "node_exporter", "duration_ms": 4.2, "error": "", "updated_at": time.time(),
    }
    app.state.monitor.prometheus.collect = lambda: ([sample], [status])
    with TestClient(app) as client:
        client.portal.call(app.state.monitor.collect_exporters_once)
        exporters = client.get("/api/v1/exporters").json()
        assert exporters["status"] == "ok"
        assert exporters["online"] == 1
        assert exporters["nodes"][0]["hostname"] == "nas"
        snapshot = client.get("/api/v1/snapshot").json()
        assert snapshot["exporters"]["nodes"][0]["cpu_percent"] == 10.0
        assert snapshot["traffic"]["sources"][1]["id"] == "prometheus:exporter-test"
        assert snapshot["traffic"]["total"]["rx_bps"] == 123.0
        assert client.get("/api/v1/agents").json()["total"] == 0
        assert client.delete("/api/v1/agents/exporter-test").status_code == 404
        assert client.get("/api/v1/exporters").json()["nodes"][0]["node_id"] == "exporter-test"
        metrics = client.get("/metrics").text
        assert 'netpulse_host_up{node_id="exporter-test",hostname="nas",source="prometheus",os="Linux"} 1' in metrics
        assert 'netpulse_prometheus_exporter_up{target="nas",kind="node_exporter"} 1' in metrics


def test_traffic_sources_are_stable_and_do_not_double_count_same_ip(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        prometheus_exporters_enabled=True,
        prometheus_exporter_targets=("duplicate=http://192.168.10.50:9100/metrics",),
    )
    app = create_app(settings)
    base = {
        "os_name": "Linux", "cpu_percent": 10, "memory_percent": 20, "disk_percent": 30,
        "uptime_seconds": 100, "tx_bps": 1,
    }
    with TestClient(app) as client:
        client.portal.call(
            app.state.database.upsert_agent,
            {**base, "node_id": "zeta", "hostname": "zeta-host", "rx_bps": 20},
            "192.168.10.50",
        )
        client.portal.call(
            app.state.database.upsert_agent,
            {**base, "node_id": "alpha", "hostname": "alpha-host", "rx_bps": 10},
            "192.168.10.60",
        )
        client.portal.call(
            app.state.database.upsert_agent,
            {
                **base, "node_id": "duplicate-exporter", "hostname": "zeta-host", "rx_bps": 999,
                "metadata": {"collection_method": "prometheus", "target_name": "duplicate"},
            },
            "192.168.10.50",
        )
        traffic = client.get("/api/v1/snapshot").json()["traffic"]
        assert [source["id"] for source in traffic["sources"]] == ["local", "agent:alpha", "agent:zeta"]
        assert traffic["total"]["rx_bps"] == 30


def test_qnap_snmp_details_and_metrics_exclude_credentials_and_serials(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        snmp_enabled=True,
        snmp_targets=("192.168.10.20",),
        snmp_version="3",
        snmp_profile="qnap",
        snmp_username="netpulse",
        snmp_auth_password="auth-secret",
        snmp_priv_protocol="DES",
        snmp_priv_password="privacy-secret",
    )
    app = create_app(settings)
    qnap = {
        "target": "192.168.10.20",
        "profile": "qnap",
        "status": "online",
        "identity": {"model": "TS-464", "hostname": "home-nas", "firmware": "QTS 5.2"},
        "system": {"cpu_percent": 15, "cpu_temperature_celsius": 47, "uptime_seconds": 3600},
        "disks": [{"index": "1", "id": "1", "model": "Disk Model", "type": "SATA", "status": "Good", "temperature_celsius": 38, "capacity_bytes": 4_000}],
        "raids": [{"index": "1", "id": "1", "status": "Ready", "capacity_bytes": 4_000}],
        "storage_pools": [{"index": "1", "id": "1", "status": "ready", "capacity_bytes": 4_000, "free_bytes": 1_000}],
        "volumes": [{"index": "1", "id": "1", "status": "Ready", "capacity_bytes": 4_000, "free_bytes": 1_000}],
        "warnings": [],
    }
    app.state.monitor.snmp_latest.update({"status": "ok", "details": [qnap]})
    app.state.monitor.latest["snmp"] = app.state.monitor.snmp_latest
    with TestClient(app) as client:
        body = client.get("/api/v1/snmp").json()
        encoded = json.dumps(body)
        assert body["current"]["details"][0]["identity"]["model"] == "TS-464"
        assert "auth-secret" not in encoded
        assert "privacy-secret" not in encoded
        assert "serial" not in encoded.lower()
        metrics = client.get("/metrics").text
        assert 'netpulse_qnap_up{target="192.168.10.20",hostname="home-nas",model="TS-464"} 1' in metrics
        assert 'netpulse_qnap_disk_temperature_celsius{target="192.168.10.20",disk_id="1",model="Disk Model",type="SATA"} 38' in metrics
        assert "secret" not in metrics


def test_llm_settings_model_discovery_and_manual_report(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        demo_mode=True,
        llm_base_url="http://127.0.0.1:1234/v1",
        llm_model="test-model",
    )
    app = create_app(settings)

    async def fake_list_models(base_url, api_key="", allow_external=False):
        assert base_url == "http://127.0.0.1:1234/v1"
        assert api_key == "secret-value"
        assert allow_external is False
        return [{"id": "chat-model"}]

    async def fake_report(base_url, model, api_key, context, system_prompt, allow_external=False):
        assert base_url == "http://127.0.0.1:1234/v1"
        assert model == "chat-model"
        assert api_key == "secret-value"
        assert context["samples"]["sample_count"] == 1
        assert system_prompt == "必ず日本語で報告してください。"
        assert allow_external is False
        return "総評\nネットワークは正常です。"

    with TestClient(app) as client:
        client.portal.call(app.state.monitor.collect_once)
        app.state.llm_reporter.client.list_models = fake_list_models
        app.state.llm_reporter.client.create_report = fake_report

        update = client.put(
            "/api/v1/llm/settings",
            json={
                "enabled": True,
                "base_url": "http://127.0.0.1:1234/v1",
                "model": "chat-model",
                "system_prompt": "必ず日本語で報告してください。",
                "interval_minutes": 60,
                "lookback_minutes": 60,
                "flavor_scope": "last_3",
                "api_key": "secret-value",
            },
        )
        assert update.status_code == 200
        assert update.json()["api_key_configured"] is True
        assert "api_key" not in update.json()

        public_settings = client.get("/api/v1/llm/settings").json()
        assert public_settings["model"] == "chat-model"
        assert public_settings["system_prompt"] == "必ず日本語で報告してください。"
        assert public_settings["flavor_scope"] == "last_3"
        assert "secret-value" not in json.dumps(public_settings)

        models = client.post(
            "/api/v1/llm/models", json={"base_url": "http://127.0.0.1:1234/v1"}
        )
        assert models.status_code == 200
        assert models.json()["models"] == [{"id": "chat-model"}]

        generated = client.post("/api/v1/llm/reports/run")
        assert generated.status_code == 200
        assert generated.json()["status"] == "completed"
        reports = client.get("/api/v1/llm/reports").json()
        assert reports["items"][0]["content"].startswith("総評")
        assert reports["items"][0]["context"]["sample_count"] == 1
        flavor = client.get("/api/v1/llm/flavor-reports")
        assert flavor.status_code == 200
        assert flavor.json()["scope"] == "last_3"
        assert flavor.json()["label"] == "直近3回分"
        assert flavor.json()["items"][0]["content"].startswith("総評")
        changed_scope = client.put("/api/v1/llm/settings", json={"flavor_scope": "hours_24"})
        assert changed_scope.status_code == 200
        assert changed_scope.json()["flavor_scope"] == "hours_24"
        flavor_24h = client.get("/api/v1/llm/flavor-reports").json()
        assert flavor_24h["scope"] == "hours_24"
        assert flavor_24h["label"] == "直近24時間分"
        assert client.put("/api/v1/llm/settings", json={"flavor_scope": "invalid"}).status_code == 422

        async def fake_other_models(base_url, api_key="", allow_external=False):
            assert base_url == "http://192.168.10.99:1234/v1"
            assert api_key == ""
            assert allow_external is False
            return []

        app.state.llm_reporter.client.list_models = fake_other_models
        other = client.post(
            "/api/v1/llm/models", json={"base_url": "http://192.168.10.99:1234/v1"}
        )
        assert other.status_code == 200

        moved = client.put(
            "/api/v1/llm/settings", json={"base_url": "http://192.168.10.99:1234/v1"}
        )
        assert moved.status_code == 200
        assert moved.json()["api_key_configured"] is False


def test_llm_settings_reject_credentials_in_base_url(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/llm/settings",
            json={"base_url": "http://user:password@192.168.10.20:1234/v1"},
        )
        assert response.status_code == 400
        assert "password" not in response.text


def test_agent_heartbeat_rejects_non_ascii_signature(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        agent_token="server-secret-32char-test-value-01",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/heartbeat",
            content=b"{}",
            # A signature carrying raw high bytes decodes to a non-ASCII string on
            # the server and used to hit an unhandled TypeError (HTTP 500).
            # It must now be rejected as an invalid signature (HTTP 401).
            headers={
                "X-Agent-Timestamp": str(int(time.time())),
                "X-Agent-Signature": b"bad-\xe9",
            },
        )
        assert response.status_code == 401


def test_agent_heartbeat_rejects_non_numeric_timestamp(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        agent_token="server-secret-32char-test-value-01",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/heartbeat",
            content=b"{}",
            headers={
                # Raw high bytes must not reach int()/ascii-encode as a 500.
                "X-Agent-Timestamp": b"\xd9\xa1\xd9\xa2",
                "X-Agent-Signature": "bad",
            },
        )
        assert response.status_code == 401


def test_agent_heartbeat_rejects_replay_within_timestamp_window(tmp_path):
    token = "agent-replay-test-32char-token-v1"
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        agent_token=token,
    )
    app = create_app(settings)
    payload = {
        "node_id": "node-replay", "hostname": "replay-host", "os_name": "Linux",
        "cpu_percent": 1.0, "memory_percent": 1.0, "disk_percent": 1.0,
        "load_1m": 0.1, "process_count": 10, "uptime_seconds": 10,
        "rx_bps": 1.0, "tx_bps": 1.0,
        "socket_count": 1, "established_socket_count": 0, "listening_socket_count": 0,
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(token.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Agent-Timestamp": timestamp,
        "X-Agent-Signature": signature,
    }
    with TestClient(app) as client:
        first = client.post("/api/v1/agent/heartbeat", content=body, headers=headers)
        assert first.status_code == 200
        # The 60s timestamp window alone would allow replaying the captured
        # request; an identical (timestamp, payload) MAC must be rejected.
        replay = client.post("/api/v1/agent/heartbeat", content=body, headers=headers)
        assert replay.status_code == 401
        assert "Duplicate" in replay.text


def test_create_app_rejects_weak_agent_token(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        agent_token="way-too-short",
    )
    with pytest.raises(RuntimeError, match="AGENT_TOKEN"):
        create_app(settings)


def test_llm_base_url_rejects_external_by_default(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    app = create_app(settings)
    with TestClient(app) as client:
        update = client.put("/api/v1/llm/settings", json={"base_url": "https://api.openai.com/v1"})
        assert update.status_code == 400
        # The URL itself must not be echoed back into the error.
        assert "openai" not in update.text
        models = client.post("/api/v1/llm/models", json={"base_url": "https://api.openai.com/v1"})
        assert models.status_code == 400
        # Cloud-metadata link-local addresses are never a valid LLM target.
        meta = client.post("/api/v1/llm/models", json={"base_url": "http://169.254.169.254/latest/meta-data/"})
        assert meta.status_code == 400


def test_llm_base_url_allows_external_when_flagged(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        collector_enabled=False,
        discovery_enabled=False,
        llm_allow_external=True,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        update = client.put("/api/v1/llm/settings", json={"base_url": "https://api.openai.com/v1"})
        assert update.status_code == 200
        assert update.json()["base_url"] == "https://api.openai.com/v1"
        settings_payload = client.get("/api/v1/llm/settings").json()
        assert settings_payload["base_url"] == "https://api.openai.com/v1"
