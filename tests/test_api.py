from __future__ import annotations

import hashlib
import hmac
import json
import time

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

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "netpulse_health_score" in metrics.text


def test_agent_install_files_are_available_without_exposing_other_files(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    app = create_app(settings)
    expected = {
        "install-windows.ps1": "NetPulseAgent",
        "install-linux.sh": "netpulse-agent.service",
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
        assert len(payload["devices"]) == 6


def test_signed_agent_heartbeat(tmp_path):
    token = "test-token-that-is-long-enough"
    settings = Settings(
        data_dir=tmp_path, collector_enabled=False, discovery_enabled=False, agent_token=token
    )
    app = create_app(settings)
    payload = {
        "node_id": "node-1234", "hostname": "workstation", "os_name": "Windows",
        "cpu_percent": 12.5, "memory_percent": 45.0, "disk_percent": 60.0,
        "uptime_seconds": 86400,
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


def test_agent_rejects_bad_signature(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, agent_token="server-secret")
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent/heartbeat",
            content=b"{}",
            headers={"X-Agent-Timestamp": str(int(time.time())), "X-Agent-Signature": "bad"},
        )
        assert response.status_code == 401


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

    async def fake_list_models(base_url, api_key=""):
        assert base_url == "http://127.0.0.1:1234/v1"
        assert api_key == "secret-value"
        return [{"id": "chat-model"}]

    async def fake_report(base_url, model, api_key, context, system_prompt):
        assert base_url == "http://127.0.0.1:1234/v1"
        assert model == "chat-model"
        assert api_key == "secret-value"
        assert context["samples"]["sample_count"] == 1
        assert system_prompt == "必ず日本語で報告してください。"
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
                "api_key": "secret-value",
            },
        )
        assert update.status_code == 200
        assert update.json()["api_key_configured"] is True
        assert "api_key" not in update.json()

        public_settings = client.get("/api/v1/llm/settings").json()
        assert public_settings["model"] == "chat-model"
        assert public_settings["system_prompt"] == "必ず日本語で報告してください。"
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

        async def fake_other_models(base_url, api_key=""):
            assert base_url == "http://192.168.10.99:1234/v1"
            assert api_key == ""
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
