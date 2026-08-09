from __future__ import annotations

import time

import pytest

from app.database import Database


@pytest.mark.asyncio
async def test_database_round_trip(tmp_path):
    database = Database(tmp_path / "test.db")
    await database.connect()
    try:
        is_new, previous = await database.upsert_device(
            {"ip": "192.168.10.20", "mac": "aa:bb:cc:dd:ee:ff", "status": "online", "latency_ms": 2.4}
        )
        assert is_new is True
        assert previous is None
        await database.update_device(
            "192.168.10.20", {"display_name": "Test NAS", "device_type": "server", "is_trusted": True}
        )
        devices = await database.devices()
        assert devices[0]["display_name"] == "Test NAS"
        assert devices[0]["is_trusted"] is True

        now = time.time()
        await database.save_sample(
            {
                "ts": now, "cpu_percent": 10, "memory_percent": 20, "disk_percent": 30,
                "temperature_c": 45, "rx_bps": 1024, "tx_bps": 512, "gateway_latency_ms": 2,
                "packet_loss_percent": 0, "online_devices": 1, "total_devices": 1,
            }
        )
        history = await database.history(1)
        assert history[-1]["rx_bps"] == 1024

        await database.add_event("info", "test", "Round trip", "Stored successfully")
        assert (await database.events(1))[0]["title"] == "Round trip"

        await database.save_connectivity_checks(
            [{"ts": now, "check_type": "dns", "target": "192.168.10.1", "success": True, "latency_ms": 2.1}]
        )
        assert (await database.connectivity_history(1))[0]["success"] is True

        await database.save_snmp_samples(
            [{"ts": now, "target": "192.168.10.1", "metric": "wan_rx_bps", "value": 2048, "unit": "bytes/s"}]
        )
        assert (await database.snmp_history(1))[0]["value"] == 2048

        await database.upsert_agent(
            {
                "node_id": "node-test", "hostname": "test-host", "os_name": "Linux", "cpu_percent": 12,
                "memory_percent": 34, "disk_percent": 56, "uptime_seconds": 1000,
            },
            "192.168.10.50",
        )
        assert (await database.agents())[0]["status"] == "online"

        for value in (10.0, 11.0, 9.0, 10.5, 9.5, 10.0, 11.0, 9.0, 10.5, 9.5):
            await database.observe_baseline("test_metric", 12, value, 10)
        baseline = await database.observe_baseline("test_metric", 12, 50.0, 10)
        assert baseline["z_score"] > 3.5
    finally:
        await database.close()
