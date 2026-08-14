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
                load_1m REAL,
                process_count INTEGER,
                uptime_seconds INTEGER NOT NULL,
                rx_bps REAL NOT NULL DEFAULT 0,
                tx_bps REAL NOT NULL DEFAULT 0,
                socket_count INTEGER,
                established_socket_count INTEGER,
                listening_socket_count INTEGER,
                last_seen REAL NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS host_traffic_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                node_id TEXT NOT NULL,
                hostname TEXT NOT NULL,
                source_ip TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL,
                rx_bps REAL NOT NULL DEFAULT 0,
                tx_bps REAL NOT NULL DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS llm_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                base_url TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                system_prompt TEXT NOT NULL DEFAULT '',
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                lookback_minutes INTEGER NOT NULL DEFAULT 60,
                flavor_scope TEXT NOT NULL DEFAULT 'last_3',
                api_key_encrypted TEXT NOT NULL DEFAULT '',
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS llm_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                period_start REAL NOT NULL,
                period_end REAL NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                context TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices(last_seen DESC);
            CREATE INDEX IF NOT EXISTS idx_connectivity_ts ON connectivity_checks(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_snmp_ts ON snmp_samples(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_agents_seen ON agent_nodes(last_seen DESC);
            CREATE INDEX IF NOT EXISTS idx_host_traffic_node_ts ON host_traffic_samples(node_id, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_host_traffic_ts ON host_traffic_samples(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_llm_reports_created ON llm_reports(created_at DESC);
            """
        )
        llm_columns = {
            row["name"]
            for row in await (await self._connection.execute("PRAGMA table_info(llm_settings)")).fetchall()
        }
        if "system_prompt" not in llm_columns:
            await self._connection.execute(
                "ALTER TABLE llm_settings ADD COLUMN system_prompt TEXT NOT NULL DEFAULT ''"
            )
        if "flavor_scope" not in llm_columns:
            await self._connection.execute(
                "ALTER TABLE llm_settings ADD COLUMN flavor_scope TEXT NOT NULL DEFAULT 'last_3'"
            )
        agent_columns = {
            row["name"]
            for row in await (await self._connection.execute("PRAGMA table_info(agent_nodes)")).fetchall()
        }
        agent_migrations = {
            "load_1m": "REAL",
            "process_count": "INTEGER",
            "socket_count": "INTEGER",
            "established_socket_count": "INTEGER",
            "listening_socket_count": "INTEGER",
        }
        for column, column_type in agent_migrations.items():
            if column not in agent_columns:
                await self._connection.execute(f"ALTER TABLE agent_nodes ADD COLUMN {column} {column_type}")
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
        async with self._lock:
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
                    device_type = COALESCE(excluded.device_type, devices.device_type),
                    status = excluded.status,
                    latency_ms = CASE WHEN excluded.status = 'online' THEN excluded.latency_ms ELSE devices.latency_ms END,
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
        async with self._lock:
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
        async with self._lock:
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
        async with self._lock:
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

    async def events_since(self, since: float, limit: int = 50) -> list[dict[str, Any]]:
        cursor = await self._db().execute(
            "SELECT * FROM events WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
            (since, max(1, min(limit, 200))),
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        for row in rows:
            try:
                row["metadata"] = json.loads(row["metadata"])
            except json.JSONDecodeError:
                row["metadata"] = {}
        return rows

    async def sample_statistics(self, minutes: int) -> dict[str, Any]:
        since = time.time() - max(1, minutes) * 60
        metric_columns = (
            "cpu_percent", "memory_percent", "disk_percent", "temperature_c", "rx_bps",
            "tx_bps", "gateway_latency_ms", "packet_loss_percent", "online_devices", "total_devices",
        )
        select_parts = ["COUNT(*) AS sample_count", "MIN(ts) AS first_sample_at", "MAX(ts) AS last_sample_at"]
        for column in metric_columns:
            select_parts.extend(
                (f"AVG({column}) AS {column}_avg", f"MIN({column}) AS {column}_min", f"MAX({column}) AS {column}_max")
            )
        cursor = await self._db().execute(
            f"SELECT {', '.join(select_parts)} FROM samples WHERE ts >= ?", (since,)
        )
        row = dict(await cursor.fetchone())
        return row

    async def connectivity_statistics(self, minutes: int) -> list[dict[str, Any]]:
        since = time.time() - max(1, minutes) * 60
        cursor = await self._db().execute(
            """
            SELECT check_type, COUNT(*) AS checks, SUM(success) AS successful,
                   AVG(CASE WHEN success = 1 THEN latency_ms END) AS latency_ms_avg,
                   MAX(CASE WHEN success = 1 THEN latency_ms END) AS latency_ms_max
            FROM connectivity_checks
            WHERE ts >= ?
            GROUP BY check_type
            ORDER BY check_type
            """,
            (since,),
        )
        return [dict(row) for row in await cursor.fetchall()]

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

    async def snmp_statistics(self, minutes: int) -> list[dict[str, Any]]:
        since = time.time() - max(1, minutes) * 60
        cursor = await self._db().execute(
            """
            SELECT target, metric, COUNT(*) AS samples, AVG(value) AS value_avg,
                   MIN(value) AS value_min, MAX(value) AS value_max, MAX(unit) AS unit
            FROM snmp_samples
            WHERE ts >= ?
            GROUP BY target, metric
            ORDER BY target, metric
            LIMIT 500
            """,
            (since,),
        )
        return [dict(row) for row in await cursor.fetchall()]

    async def upsert_agent(self, payload: dict[str, Any], source_ip: str) -> None:
        now = time.time()
        metadata = payload.get("metadata", {})
        source_type = "prometheus" if metadata.get("collection_method") == "prometheus" else "agent"
        async with self._lock:
            await self._db().execute(
                """
                INSERT INTO agent_nodes (
                    node_id, hostname, os_name, os_version, source_ip, agent_version, cpu_percent,
                    memory_percent, disk_percent, temperature_c, load_1m, process_count, uptime_seconds, rx_bps, tx_bps,
                    socket_count, established_socket_count, listening_socket_count, last_seen, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    hostname=excluded.hostname, os_name=excluded.os_name, os_version=excluded.os_version,
                    source_ip=excluded.source_ip, agent_version=excluded.agent_version,
                    cpu_percent=excluded.cpu_percent, memory_percent=excluded.memory_percent,
                    disk_percent=excluded.disk_percent, temperature_c=excluded.temperature_c,
                    load_1m=excluded.load_1m, process_count=excluded.process_count,
                    uptime_seconds=excluded.uptime_seconds, rx_bps=excluded.rx_bps,
                    tx_bps=excluded.tx_bps, socket_count=excluded.socket_count,
                    established_socket_count=excluded.established_socket_count,
                    listening_socket_count=excluded.listening_socket_count,
                    last_seen=excluded.last_seen, metadata=excluded.metadata
                """,
                (
                    payload["node_id"], payload["hostname"], payload["os_name"], payload.get("os_version", ""),
                    source_ip, payload.get("agent_version", ""), payload["cpu_percent"],
                    payload["memory_percent"], payload["disk_percent"], payload.get("temperature_c"),
                    payload.get("load_1m"), payload.get("process_count"),
                    payload["uptime_seconds"], payload.get("rx_bps", 0), payload.get("tx_bps", 0),
                    payload.get("socket_count"), payload.get("established_socket_count"),
                    payload.get("listening_socket_count"), now,
                    json.dumps(metadata, ensure_ascii=False),
                ),
            )
            await self._db().execute(
                """
                INSERT INTO host_traffic_samples (
                    ts, node_id, hostname, source_ip, source_type, rx_bps, tx_bps
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now, payload["node_id"], payload["hostname"], source_ip, source_type,
                    payload.get("rx_bps", 0), payload.get("tx_bps", 0),
                ),
            )
            await self._db().commit()

    async def host_traffic_history(
        self, minutes: int = 60, node_ids: list[str] | None = None, limit: int = 20_000
    ) -> list[dict[str, Any]]:
        if node_ids is not None and not node_ids:
            return []
        since = time.time() - max(1, minutes) * 60
        params: list[Any] = [since]
        predicate = "ts >= ?"
        if node_ids:
            placeholders = ", ".join("?" for _ in node_ids)
            predicate += f" AND node_id IN ({placeholders})"
            params.extend(node_ids)
        params.append(max(1, min(limit, 50_000)))
        cursor = await self._db().execute(
            f"""
            SELECT ts, node_id, hostname, source_ip, source_type, rx_bps, tx_bps
            FROM host_traffic_samples
            WHERE {predicate}
            ORDER BY ts DESC
            LIMIT ?
            """,
            params,
        )
        return [dict(row) for row in reversed(await cursor.fetchall())]

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

    async def ensure_llm_settings(self, defaults: dict[str, Any]) -> None:
        async with self._lock:
            await self._db().execute(
                """
                INSERT OR IGNORE INTO llm_settings (
                    id, enabled, base_url, model, system_prompt, interval_minutes, lookback_minutes,
                    flavor_scope, api_key_encrypted, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(bool(defaults.get("enabled"))), defaults.get("base_url", ""), defaults.get("model", ""),
                    defaults.get("system_prompt", ""),
                    int(defaults.get("interval_minutes", 60)), int(defaults.get("lookback_minutes", 60)),
                    defaults.get("flavor_scope", "last_3"),
                    defaults.get("api_key_encrypted", ""), time.time(),
                ),
            )
            await self._db().commit()

    async def llm_settings(self) -> dict[str, Any]:
        cursor = await self._db().execute("SELECT * FROM llm_settings WHERE id = 1")
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("LLM settings have not been initialized")
        values = dict(row)
        values["enabled"] = bool(values["enabled"])
        return values

    async def update_llm_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "enabled", "base_url", "model", "system_prompt", "interval_minutes", "lookback_minutes",
            "flavor_scope", "api_key_encrypted",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return await self.llm_settings()
        updates["updated_at"] = time.time()
        columns = ", ".join(f"{key} = ?" for key in updates)
        params = [int(value) if key == "enabled" else value for key, value in updates.items()]
        async with self._lock:
            await self._db().execute(f"UPDATE llm_settings SET {columns} WHERE id = 1", params)
            await self._db().commit()
        return await self.llm_settings()

    async def save_llm_report(
        self,
        *,
        period_start: float,
        period_end: float,
        model: str,
        status: str,
        content: str = "",
        error: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            cursor = await self._db().execute(
                """
                INSERT INTO llm_reports (
                    created_at, period_start, period_end, model, status, content, error, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(), period_start, period_end, model, status, content, error,
                    json.dumps(context or {}, ensure_ascii=False),
                ),
            )
            await self._db().commit()
            report_id = cursor.lastrowid
            row_cursor = await self._db().execute("SELECT * FROM llm_reports WHERE id = ?", (report_id,))
            return self._decode_llm_report(dict(await row_cursor.fetchone()))

    async def llm_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        cursor = await self._db().execute(
            "SELECT * FROM llm_reports ORDER BY created_at DESC, id DESC LIMIT ?", (max(1, min(limit, 100)),)
        )
        return [self._decode_llm_report(dict(row)) for row in await cursor.fetchall()]

    async def llm_flavor_reports(self, scope: str) -> list[dict[str, Any]]:
        count_limits = {"last_3": 3, "last_5": 5, "last_10": 10}
        if scope in count_limits:
            cursor = await self._db().execute(
                """
                SELECT * FROM llm_reports
                WHERE status = 'completed' AND content != ''
                ORDER BY created_at DESC, id DESC LIMIT ?
                """,
                (count_limits[scope],),
            )
        elif scope == "hours_24":
            cursor = await self._db().execute(
                """
                SELECT * FROM llm_reports
                WHERE status = 'completed' AND content != '' AND created_at >= ?
                ORDER BY created_at DESC, id DESC
                """,
                (time.time() - 86_400,),
            )
        else:
            raise ValueError("Unknown LLM flavor report scope")
        return [self._decode_llm_report(dict(row)) for row in await cursor.fetchall()]

    async def last_llm_report_at(self) -> float | None:
        cursor = await self._db().execute("SELECT MAX(created_at) AS created_at FROM llm_reports")
        row = await cursor.fetchone()
        return float(row["created_at"]) if row and row["created_at"] is not None else None

    @staticmethod
    def _decode_llm_report(row: dict[str, Any]) -> dict[str, Any]:
        try:
            row["context"] = json.loads(row.get("context", "{}"))
        except json.JSONDecodeError:
            row["context"] = {}
        return row

    async def cleanup(self, retention_days: int) -> None:
        async with self._lock:
            cutoff = time.time() - retention_days * 86400
            await self._db().execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
            await self._db().execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            await self._db().execute("DELETE FROM connectivity_checks WHERE ts < ?", (cutoff,))
            await self._db().execute("DELETE FROM snmp_samples WHERE ts < ?", (cutoff,))
            await self._db().execute("DELETE FROM host_traffic_samples WHERE ts < ?", (cutoff,))
            await self._db().execute("DELETE FROM llm_reports WHERE created_at < ?", (cutoff,))
            await self._db().commit()
