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

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "netpulse_health_score" in metrics.text


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
