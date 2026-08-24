from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database
from app.main import create_app


def _local_sample(ts: float, rx: float, tx: float) -> dict:
    return {
        "ts": ts, "cpu_percent": 1.0, "memory_percent": 1.0, "disk_percent": 1.0,
        "temperature_c": 30.0, "rx_bps": rx, "tx_bps": tx, "gateway_latency_ms": 5.0,
        "packet_loss_percent": 0.0, "online_devices": 1, "total_devices": 1,
    }


@pytest.mark.asyncio
async def _seed_history(database):
    """Two samples an hour apart for a workstation (agent + prometheus twin) and local Pi."""
    now = time.time()
    stamps = [now - 3600, now]
    for ts in stamps:
        await database.save_sample(_local_sample(ts, 2.0, 1.0))
        await database._db().execute(
            "INSERT INTO host_traffic_samples (ts, node_id, hostname, source_ip, source_type, rx_bps, tx_bps) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, "node-1", "workstation", "192.168.10.50", "agent", 10.0, 5.0),
        )
        await database._db().execute(
            "INSERT INTO host_traffic_samples (ts, node_id, hostname, source_ip, source_type, rx_bps, tx_bps) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, "node-exporter", "workstation", "192.168.10.50", "prometheus", 9999.0, 0.0),
        )
    await database._db().commit()


@pytest.mark.asyncio
async def test_ranking_prefers_agent_over_prometheus_and_includes_local(tmp_path):
    database = Database(tmp_path / "netpulse.db")
    await database.connect()
    try:
        await _seed_history(database)
        result = await database.device_traffic_ranking(24, limit=5, fallback_interval=2.0)
        by_id = {item["identity"]: item for item in result["items"]}
        # Same identity 192.168.10.50 must appear exactly once, using agent values.
        assert by_id["192.168.10.50"]["kind"] == "agent"
        assert by_id["192.168.10.50"]["label"] == "workstation"
        # Prometheus twin is dropped, not summed into the agent identity.
        prometheus_only = 2 * 9999.0 * 3600
        assert by_id["192.168.10.50"]["total_bytes"] < prometheus_only
        # Local Pi is always included.
        assert by_id["local"]["kind"] == "local"
        assert by_id["local"]["label"] == "Raspberry Pi 5"
        # Workstation (15 B/s) outranks the local Pi (3 B/s).
        assert result["items"][0]["identity"] == "192.168.10.50"
        assert result["items"][1]["identity"] == "local"
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_ranking_limit_clamps_and_drops_lowest(tmp_path):
    database = Database(tmp_path / "netpulse.db")
    await database.connect()
    try:
        await _seed_history(database)
        limited = await database.device_traffic_ranking(24, limit=1, fallback_interval=2.0)
        assert limited["hours"] == 24
        assert [item["identity"] for item in limited["items"]] == ["192.168.10.50"]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_daily_summary_totals_peak_hour_and_dedup(tmp_path):
    database = Database(tmp_path / "netpulse.db")
    await database.connect()
    try:
        await _seed_history(database)
        result = await database.daily_traffic_summary(7, fallback_interval=2.0)
        assert result["fallback_sample_interval"] == 2.0
        days = result["days"]
        assert days, "expected at least one day row"
        latest = days[-1]
        assert latest["rx_bytes"] >= 0 and latest["tx_bytes"] >= 0
        assert latest["rx_bytes"] + latest["tx_bytes"] == latest["total_bytes"]
        assert latest["total_bytes"] > 0
        assert latest["peak_hour"] is not None
        assert 0 <= latest["peak_hour"] <= 23
        # If identity dedup failed, the 9999 B/s prometheus twin would blow the
        # day total past this ceiling. Agent total is only 15 B/s x ~4 samples x 3600s.
        assert latest["total_bytes"] < 1_000_000
        assert latest["sample_count"] >= 2
    finally:
        await database.close()


def test_summary_endpoints_return_shape(tmp_path):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    app = create_app(settings)
    with TestClient(app) as client:
        client.portal.call(app.state.database.save_sample, _local_sample(time.time() - 60, 100.0, 40.0))
        daily = client.get("/api/v1/summary/daily?days=7")
        assert daily.status_code == 200
        body = daily.json()
        assert "days" in body and "fallback_sample_interval" in body
        assert body["days"][-1]["total_bytes"] > 0

        ranking = client.get("/api/v1/summary/ranking?hours=24&limit=5")
        assert ranking.status_code == 200
        rank = ranking.json()
        assert rank["hours"] == 24
        assert any(item["identity"] == "local" for item in rank["items"])

        assert client.get("/api/v1/summary/daily?days=31").status_code == 422
        assert client.get("/api/v1/summary/ranking?hours=0").status_code == 422
