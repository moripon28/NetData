from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS samples (
                ts REAL PRIMARY KEY,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                disk_percent REAL NOT NULL,
                temperature_c REAL,
                rx_bps REAL NOT NULL,
                tx_bps REAL NOT NULL,
                gateway_latency_ms REAL,
                packet_loss_percent REAL NOT NULL,
                online_devices INTEGER NOT NULL,
                total_devices INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                ip TEXT PRIMARY KEY,
                mac TEXT,
                hostname TEXT,
                display_name TEXT,
                vendor TEXT,
                device_type TEXT NOT NULL DEFAULT 'unknown',
                status TEXT NOT NULL DEFAULT 'unknown',
                latency_ms REAL,
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                is_trusted INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS connectivity_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                check_type TEXT NOT NULL,
                target TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency_ms REAL,
                detail TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS snmp_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                target TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS agent_nodes (
                node_id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                os_name TEXT NOT NULL,
                os_version TEXT NOT NULL DEFAULT '',
                source_ip TEXT NOT NULL,
                agent_version TEXT NOT NULL DEFAULT '',
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                disk_percent REAL NOT NULL,
                temperature_c REAL,
                uptime_seconds INTEGER NOT NULL,
                rx_bps REAL NOT NULL DEFAULT 0,
                tx_bps REAL NOT NULL DEFAULT 0,
                last_seen REAL NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS metric_baselines (
                metric TEXT NOT NULL,
                hour_bucket INTEGER NOT NULL,
                sample_count INTEGER NOT NULL,
                mean REAL NOT NULL,
                m2 REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY(metric, hour_bucket)
            );

            CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen DESC);
            CREATE INDEX IF NOT EXISTS idx_connectivity_ts ON connectivity_checks(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_snmp_ts ON snmp_samples(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_agents_seen ON agent_nodes(last_seen DESC);
            """
        )
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    def _db(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        return self._connection

    async def save_sample(self, sample: dict[str, Any]) -> None:
        async with self._lock:
            await self._db().execute(
                """
                INSERT OR REPLACE INTO samples VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample["ts"], sample["cpu_percent"], sample["memory_percent"],
                    sample["disk_percent"], sample.get("temperature_c"), sample["rx_bps"],
                    sample["tx_bps"], sample.get("gateway_latency_ms"),
                    sample["packet_loss_percent"], sample["online_devices"],
                    sample["total_devices"],
                ),
            )
            await self._db().commit()

    async def history(self, minutes: int = 60, limit: int = 1800) -> list[dict[str, Any]]:
        since = time.time() - max(1, minutes) * 60
        cursor = await self._db().execute(
            "SELECT * FROM samples WHERE ts >= ? ORDER BY ts DESC LIMIT ?", (since, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in reversed(rows)]

    async def upsert_device(self, device: dict[str, Any]) -> tuple[bool, str | None]:
        now = float(device.get("last_seen", time.time()))
        cursor = await self._db().execute("SELECT status FROM devices WHERE ip = ?", (device["ip"],))
        previous = await cursor.fetchone()
        is_new = previous is None
        previous_status = previous["status"] if previous else None
        await self._db().execute(
            """
            INSERT INTO devices (ip, mac, hostname, vendor, device_type, status, latency_ms, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                mac = COALESCE(excluded.mac, devices.mac),
                hostname = COALESCE(excluded.hostname, devices.hostname),
                vendor = COALESCE(excluded.vendor, devices.vendor),
                status = excluded.status,
                latency_ms = excluded.latency_ms,
                last_seen = CASE WHEN excluded.status = 'online' THEN excluded.last_seen ELSE devices.last_seen END
            """,
            (
                device["ip"], device.get("mac"), device.get("hostname"), device.get("vendor"),
                device.get("device_type", "unknown"), device.get("status", "online"),
                device.get("latency_ms"), now, now,
            ),
        )
        await self._db().commit()
        return is_new, previous_status

    async def mark_stale_devices(self, older_than: float) -> list[dict[str, Any]]:
        cursor = await self._db().execute(
            "SELECT ip, display_name, hostname FROM devices WHERE status = 'online' AND last_seen < ?",
            (older_than,),
        )
        stale = [dict(row) for row in await cursor.fetchall()]
        if stale:
            await self._db().execute(
                "UPDATE devices SET status = 'offline', latency_ms = NULL WHERE status = 'online' AND last_seen < ?",
                (older_than,),
            )
            await self._db().commit()
        return stale

    async def devices(self) -> list[dict[str, Any]]:
        cursor = await self._db().execute(
            """
            SELECT ip, mac, hostname, display_name, vendor, device_type, status, latency_ms,
                   first_seen, last_seen, is_trusted
            FROM devices
            ORDER BY status = 'online' DESC, is_trusted DESC, COALESCE(display_name, hostname, ip)
            """
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        for row in rows:
            row["is_trusted"] = bool(row["is_trusted"])
        return rows

    async def update_device(self, ip: str, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"display_name", "device_type", "is_trusted"}
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return None
        columns = ", ".join(f"{key} = ?" for key in updates)
        params = [int(value) if key == "is_trusted" else value for key, value in updates.items()]
        params.append(ip)
        await self._db().execute(f"UPDATE devices SET {columns} WHERE ip = ?", params)
        await self._db().commit()
        cursor = await self._db().execute("SELECT * FROM devices WHERE ip = ?", (ip,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def add_event(
        self, severity: str, category: str, title: str, detail: str, metadata: dict[str, Any] | None = None
    ) -> None:
        await self._db().execute(
            "INSERT INTO events (ts, severity, category, title, detail, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), severity, category, title, detail, json.dumps(metadata or {}, ensure_ascii=False)),
        )
        await self._db().commit()

    async def events(self, limit: int = 50) -> list[dict[str, Any]]:
        cursor = await self._db().execute(
            "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (max(1, min(limit, 500)),)
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        for row in rows:
            try:
                row["metadata"] = json.loads(row["metadata"])
            except json.JSONDecodeError:
                row["metadata"] = {}
        return rows

    async def save_connectivity_checks(self, checks: list[dict[str, Any]]) -> None:
        if not checks:
            return
        async with self._lock:
            await self._db().executemany(
                """
                INSERT INTO connectivity_checks (ts, check_type, target, success, latency_ms, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.get("ts", time.time()), item["check_type"], item["target"],
                        int(bool(item["success"])), item.get("latency_ms"), item.get("detail", ""),
                    )
                    for item in checks
                ],
            )
            await self._db().commit()

    async def connectivity_history(self, minutes: int = 60, limit: int = 1000) -> list[dict[str, Any]]:
        since = time.time() - max(1, minutes) * 60
        cursor = await self._db().execute(
            "SELECT * FROM connectivity_checks WHERE ts >= ? ORDER BY ts DESC LIMIT ?", (since, limit)
        )
        rows = [dict(row) for row in reversed(await cursor.fetchall())]
        for row in rows:
            row["success"] = bool(row["success"])
        return rows

    async def save_snmp_samples(self, samples: list[dict[str, Any]]) -> None:
        if not samples:
            return
        async with self._lock:
            await self._db().executemany(
                "INSERT INTO snmp_samples (ts, target, metric, value, unit) VALUES (?, ?, ?, ?, ?)",
                [
                    (item.get("ts", time.time()), item["target"], item["metric"], item["value"], item.get("unit", ""))
                    for item in samples
                ],
            )
            await self._db().commit()

    async def snmp_history(self, minutes: int = 60, limit: int = 1000) -> list[dict[str, Any]]:
        since = time.time() - max(1, minutes) * 60
        cursor = await self._db().execute(
            "SELECT * FROM snmp_samples WHERE ts >= ? ORDER BY ts DESC LIMIT ?", (since, limit)
        )
        return [dict(row) for row in reversed(await cursor.fetchall())]

    async def upsert_agent(self, payload: dict[str, Any], source_ip: str) -> None:
        now = time.time()
        async with self._lock:
            await self._db().execute(
                """
                INSERT INTO agent_nodes (
                    node_id, hostname, os_name, os_version, source_ip, agent_version, cpu_percent,
                    memory_percent, disk_percent, temperature_c, uptime_seconds, rx_bps, tx_bps,
                    last_seen, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    hostname=excluded.hostname, os_name=excluded.os_name, os_version=excluded.os_version,
                    source_ip=excluded.source_ip, agent_version=excluded.agent_version,
                    cpu_percent=excluded.cpu_percent, memory_percent=excluded.memory_percent,
                    disk_percent=excluded.disk_percent, temperature_c=excluded.temperature_c,
                    uptime_seconds=excluded.uptime_seconds, rx_bps=excluded.rx_bps,
                    tx_bps=excluded.tx_bps, last_seen=excluded.last_seen, metadata=excluded.metadata
                """,
                (
                    payload["node_id"], payload["hostname"], payload["os_name"], payload.get("os_version", ""),
                    source_ip, payload.get("agent_version", ""), payload["cpu_percent"],
                    payload["memory_percent"], payload["disk_percent"], payload.get("temperature_c"),
                    payload["uptime_seconds"], payload.get("rx_bps", 0), payload.get("tx_bps", 0), now,
                    json.dumps(payload.get("metadata", {}), ensure_ascii=False),
                ),
            )
            await self._db().commit()

    async def agents(self, offline_after: int = 60) -> list[dict[str, Any]]:
        cursor = await self._db().execute("SELECT * FROM agent_nodes ORDER BY last_seen DESC")
        rows = [dict(row) for row in await cursor.fetchall()]
        cutoff = time.time() - offline_after
        for row in rows:
            row["status"] = "online" if row["last_seen"] >= cutoff else "offline"
            try:
                row["metadata"] = json.loads(row["metadata"])
            except json.JSONDecodeError:
                row["metadata"] = {}
        return rows

    async def observe_baseline(
        self, metric: str, hour_bucket: int, value: float, minimum_samples: int
    ) -> dict[str, Any]:
        async with self._lock:
            cursor = await self._db().execute(
                "SELECT sample_count, mean, m2 FROM metric_baselines WHERE metric = ? AND hour_bucket = ?",
                (metric, hour_bucket),
            )
            row = await cursor.fetchone()
            count = int(row["sample_count"]) if row else 0
            mean = float(row["mean"]) if row else 0.0
            m2 = float(row["m2"]) if row else 0.0
            variance = m2 / (count - 1) if count > 1 else 0.0
            deviation = variance ** 0.5
            z_score = abs(value - mean) / deviation if count >= minimum_samples and deviation > 1e-9 else 0.0

            new_count = count + 1
            delta = value - mean
            new_mean = mean + delta / new_count
            new_m2 = m2 + delta * (value - new_mean)
            await self._db().execute(
                """
                INSERT INTO metric_baselines (metric, hour_bucket, sample_count, mean, m2, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(metric, hour_bucket) DO UPDATE SET
                    sample_count=excluded.sample_count, mean=excluded.mean, m2=excluded.m2,
                    updated_at=excluded.updated_at
                """,
                (metric, hour_bucket, new_count, new_mean, new_m2, time.time()),
            )
            await self._db().commit()
        return {"count": count, "mean": mean, "deviation": deviation, "z_score": z_score, "value": value}

    async def baseline_summary(self, hour_bucket: int) -> dict[str, int]:
        cursor = await self._db().execute(
            "SELECT metric, sample_count FROM metric_baselines WHERE hour_bucket = ?", (hour_bucket,)
        )
        return {row["metric"]: int(row["sample_count"]) for row in await cursor.fetchall()}

    async def cleanup(self, retention_days: int) -> None:
        cutoff = time.time() - retention_days * 86400
        await self._db().execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
        await self._db().execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        await self._db().execute("DELETE FROM connectivity_checks WHERE ts < ?", (cutoff,))
        await self._db().execute("DELETE FROM snmp_samples WHERE ts < ?", (cutoff,))
        await self._db().commit()
