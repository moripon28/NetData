from __future__ import annotations

import sqlite3
import time

import pytest

from app.database import Database


@pytest.mark.asyncio
async def test_database_adds_system_prompt_to_existing_llm_settings(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE llm_settings (
            id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL, base_url TEXT NOT NULL,
            model TEXT NOT NULL, interval_minutes INTEGER NOT NULL, lookback_minutes INTEGER NOT NULL,
            api_key_encrypted TEXT NOT NULL, updated_at REAL NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO llm_settings VALUES (1, 0, '', '', 60, 60, '', ?)", (time.time(),)
    )
    connection.commit()
    connection.close()

    database = Database(path)
    await database.connect()
    try:
        migrated = await database.llm_settings()
        assert migrated["system_prompt"] == ""
        assert migrated["flavor_scope"] == "last_3"
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_database_adds_socket_counts_to_existing_agent_nodes(tmp_path):
    path = tmp_path / "legacy-agents.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE agent_nodes (
            node_id TEXT PRIMARY KEY, hostname TEXT NOT NULL, os_name TEXT NOT NULL,
            os_version TEXT NOT NULL DEFAULT '', source_ip TEXT NOT NULL,
            agent_version TEXT NOT NULL DEFAULT '', cpu_percent REAL NOT NULL,
            memory_percent REAL NOT NULL, disk_percent REAL NOT NULL, temperature_c REAL,
            uptime_seconds INTEGER NOT NULL, rx_bps REAL NOT NULL DEFAULT 0,
            tx_bps REAL NOT NULL DEFAULT 0, last_seen REAL NOT NULL,
            metadata TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    connection.commit()
    connection.close()

    database = Database(path)
    await database.connect()
    try:
        cursor = await database._db().execute("PRAGMA table_info(agent_nodes)")
        columns = {row["name"] for row in await cursor.fetchall()}
        assert {
            "load_1m", "process_count", "socket_count",
            "established_socket_count", "listening_socket_count",
        } <= columns
    finally:
        await database.close()


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
        snmp_statistics = await database.snmp_statistics(1)
        assert snmp_statistics[0]["value_avg"] == 2048

        await database.upsert_agent(
            {
                "node_id": "node-test", "hostname": "test-host", "os_name": "Linux", "cpu_percent": 12,
                "memory_percent": 34, "disk_percent": 56, "uptime_seconds": 1000,
                "load_1m": 0.42, "process_count": 123,
                "rx_bps": 2048, "tx_bps": 256,
                "socket_count": 21, "established_socket_count": 4, "listening_socket_count": 3,
            },
            "192.168.10.50",
        )
        assert (await database.agents())[0]["status"] == "online"
        assert (await database.agents())[0]["socket_count"] == 21
        assert (await database.agents())[0]["process_count"] == 123
        traffic_history = await database.host_traffic_history(1, ["node-test"])
        assert traffic_history[-1]["source_type"] == "agent"
        assert traffic_history[-1]["rx_bps"] == 2048

        for value in (10.0, 11.0, 9.0, 10.5, 9.5, 10.0, 11.0, 9.0, 10.5, 9.5):
            await database.observe_baseline("test_metric", 12, value, 10)
        baseline = await database.observe_baseline("test_metric", 12, 50.0, 10)
        assert baseline["z_score"] > 3.5

        await database.ensure_llm_settings(
            {
                "enabled": False, "base_url": "http://127.0.0.1:1234/v1", "model": "test-model",
                "system_prompt": "日本語で報告してください。",
                "interval_minutes": 60, "lookback_minutes": 60, "api_key_encrypted": "ciphertext",
                "flavor_scope": "last_3",
            }
        )
        llm_settings = await database.update_llm_settings(
            {"enabled": True, "lookback_minutes": 360, "flavor_scope": "last_5"}
        )
        assert llm_settings["enabled"] is True
        assert llm_settings["api_key_encrypted"] == "ciphertext"
        assert llm_settings["system_prompt"] == "日本語で報告してください。"
        assert llm_settings["flavor_scope"] == "last_5"
        statistics = await database.sample_statistics(60)
        assert statistics["sample_count"] == 1
        assert statistics["rx_bps_avg"] == 1024

        report = await database.save_llm_report(
            period_start=now - 3600,
            period_end=now,
            model="test-model",
            status="completed",
            content="ネットワークは正常です。",
            context={"trigger": "manual", "sample_count": 1},
        )
        assert report["context"]["sample_count"] == 1
        assert (await database.llm_reports(1))[0]["content"] == "ネットワークは正常です。"
        for index in range(4):
            await database.save_llm_report(
                period_start=now - 3600,
                period_end=now,
                model="test-model",
                status="completed",
                content=f"追加レポート {index}",
            )
        flavor_reports = await database.llm_flavor_reports("last_3")
        assert [item["content"] for item in flavor_reports] == [
            "追加レポート 3", "追加レポート 2", "追加レポート 1",
        ]
    finally:
        await database.close()
