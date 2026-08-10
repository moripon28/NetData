from __future__ import annotations

import asyncio
import ipaddress
import math
import random
import time
from contextlib import suppress
from typing import Any, Awaitable, Callable

from app.anomaly import AnomalyDetector
from app.collectors.connectivity import ConnectivityCollector
from app.collectors.network import DeviceDiscovery, TrafficCollector
from app.collectors.prometheus import PrometheusExporterCollector
from app.collectors.snmp import SnmpCollector
from app.collectors.system import SystemCollector
from app.config import Settings
from app.database import Database


Broadcast = Callable[[dict[str, Any]], Awaitable[None]]


class MonitorService:
    def __init__(self, settings: Settings, database: Database, broadcast: Broadcast | None = None) -> None:
        self.settings = settings
        self.database = database
        self.broadcast = broadcast
        self.system = SystemCollector()
        self.traffic = TrafficCollector(settings.preferred_interface)
        self.discovery = DeviceDiscovery()
        self.gateway = settings.gateway_host or self.discovery.detect_gateway()
        self.subnet = settings.validated_subnet() or self.discovery.detect_subnet()
        self._network = ipaddress.ip_network(self.subnet, strict=False) if self.subnet else None
        self._device_stale_after = max(
            settings.offline_after,
            settings.discovery_interval + 15 if settings.discovery_enabled else settings.offline_after,
        )
        dns_servers = (settings.dns_servers or tuple(filter(None, (self.gateway,)))) if settings.internet_probes_enabled else ()
        internet_targets = settings.internet_targets if settings.internet_probes_enabled else ()
        self.connectivity = ConnectivityCollector(
            dns_servers,
            internet_targets,
            settings.dns_check_name,
            settings.lan_probe_targets if settings.connectivity_enabled else (),
        )
        self.snmp = SnmpCollector(
            settings.snmp_targets,
            settings.snmp_community,
            settings.snmp_interface_index,
            settings.snmp_extra_oids,
            version=settings.snmp_version,
            username=settings.snmp_username,
            auth_protocol=settings.snmp_auth_protocol,
            auth_password=settings.snmp_auth_password,
            priv_protocol=settings.snmp_priv_protocol,
            priv_password=settings.snmp_priv_password,
            profile=settings.snmp_profile,
            timeout=settings.snmp_timeout,
        )
        self.prometheus = PrometheusExporterCollector(
            settings.prometheus_exporter_targets if settings.prometheus_exporters_enabled else (),
            settings.prometheus_exporter_timeout,
        )
        self.anomaly = AnomalyDetector(database, settings.anomaly_min_samples)
        self.connectivity_latest: dict[str, Any] = {
            "enabled": settings.connectivity_enabled,
            "status": "checking" if settings.connectivity_enabled else "disabled",
            "dns_latency_ms": None,
            "internet_latency_ms": None,
            "lan_latency_ms": None,
            "lan_status": "checking" if settings.connectivity_enabled and settings.lan_probe_targets else "disabled",
            "external_status": "checking" if settings.connectivity_enabled and settings.internet_probes_enabled else "disabled",
            "checks": [],
            "updated_at": None,
        }
        self.snmp_latest: dict[str, Any] = {
            "enabled": settings.snmp_enabled,
            "status": "checking" if settings.snmp_enabled else "disabled",
            "profile": settings.snmp_profile,
            "security": "authPriv" if settings.snmp_version == "3" else "community",
            "metrics": {},
            "details": [],
            "targets": list(settings.snmp_targets),
            "updated_at": None,
        }
        self.exporters_latest: dict[str, Any] = {
            "enabled": settings.prometheus_exporters_enabled,
            "configured": bool(self.prometheus.targets),
            "status": "checking" if settings.prometheus_exporters_enabled and self.prometheus.targets else "disabled",
            "online": 0,
            "total": len(self.prometheus.targets),
            "items": [],
            "updated_at": None,
        }
        self.latest: dict[str, Any] = self._empty_snapshot()
        self._tasks: list[asyncio.Task[Any]] = []
        self._running = False
        self._last_thresholds: dict[str, float] = {}
        self._demo_tick = 0
        self._last_cleanup = 0.0
        self._last_anomaly_observation = 0.0
        self._connectivity_status = self.connectivity_latest["status"]
        self._snmp_status = self.snmp_latest["status"]
        self._exporter_status = self.exporters_latest["status"]

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self.database.cleanup(self.settings.retention_days)
        self._last_cleanup = time.time()
        await self.database.add_event(
            "info",
            "system",
            "NetPulse started",
            f"Monitoring interface {self.settings.preferred_interface or 'auto'}; subnet {self.subnet or 'not detected'}.",
        )
        if self.settings.collector_enabled:
            self._tasks.append(asyncio.create_task(self._collector_loop(), name="metric-collector"))
            if self.settings.discovery_enabled and self.subnet:
                self._tasks.append(asyncio.create_task(self._discovery_loop(), name="device-discovery"))
            if self.settings.connectivity_enabled:
                self._tasks.append(asyncio.create_task(self._connectivity_loop(), name="connectivity-checks"))
            if self.settings.snmp_enabled and self.settings.snmp_targets:
                self._tasks.append(asyncio.create_task(self._snmp_loop(), name="snmp-collector"))
            if self.settings.prometheus_exporters_enabled and self.prometheus.targets:
                self._tasks.append(asyncio.create_task(self._prometheus_loop(), name="prometheus-exporter-collector"))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def collect_once(self) -> dict[str, Any]:
        if self.settings.demo_mode:
            sample = await self._demo_sample()
        else:
            system = await asyncio.to_thread(self.system.collect)
            traffic = self.traffic.collect()
            latency = await asyncio.to_thread(self.discovery.ping, self.gateway) if self.gateway else None
            devices = await self.devices()
            online = sum(device["status"] == "online" for device in devices)
            sample = {
                "ts": time.time(),
                **system,
                **traffic,
                "gateway": self.gateway,
                "gateway_latency_ms": latency,
                "packet_loss_percent": 0.0 if latency is not None else (100.0 if self.gateway else 0.0),
                "online_devices": online,
                "total_devices": len(devices),
            }

        await self._refresh_neighbours()
        current_devices = await self.devices()
        sample["online_devices"] = sum(device["status"] == "online" for device in current_devices)
        sample["total_devices"] = len(current_devices)
        sample["health_score"] = self._health_score(sample)
        await self.database.save_sample(sample)
        if time.time() - self._last_cleanup >= 86400:
            await self.database.cleanup(self.settings.retention_days)
            self._last_cleanup = time.time()
        await self._detect_threshold_events(sample)
        if self.settings.anomaly_enabled and time.time() - self._last_anomaly_observation >= self.settings.anomaly_interval:
            anomaly_state, anomaly_events = await self.anomaly.observe(sample, self.connectivity_latest)
            self._last_anomaly_observation = time.time()
            for item in anomaly_events:
                await self.database.add_event(
                    "warning",
                    "anomaly",
                    f"Unusual {item['label']}",
                    f"The value is {item['score']:.1f} standard deviations from the learned {item['direction']} pattern.",
                    item,
                )
        agents = await self.agent_nodes()
        exporter_nodes = await self.exporter_nodes()
        exporters = dict(self.exporters_latest)
        exporters["nodes"] = exporter_nodes
        self.latest = {
            "type": "snapshot",
            "generated_at": time.time(),
            "system": {
                key: sample.get(key)
                for key in (
                    "cpu_percent", "memory_percent", "memory_used", "memory_total", "disk_percent",
                    "disk_used", "disk_total", "temperature_c", "load_1m", "load_5m", "uptime_seconds",
                )
            },
            "network": {
                key: sample.get(key)
                for key in (
                    "interface", "rx_bps", "tx_bps", "rx_total", "tx_total", "gateway",
                    "gateway_latency_ms", "packet_loss_percent",
                )
            },
            "summary": {
                "online_devices": sample["online_devices"],
                "total_devices": sample["total_devices"],
                "health_score": sample["health_score"],
                "subnet": self.subnet,
            },
            "devices": current_devices,
            "connectivity": self.connectivity_latest,
            "snmp": self.snmp_latest,
            "exporters": exporters,
            "agents": {
                "configured": bool(self.settings.agent_token),
                "online": sum(agent["status"] == "online" for agent in agents),
                "total": len(agents),
                "items": agents,
            },
            "insights": self.anomaly.last_result if self.settings.anomaly_enabled else {"status": "disabled"},
            "events": await self.database.events(12),
        }
        if self.broadcast:
            await self.broadcast(self.latest)
        return self.latest

    async def snapshot(self) -> dict[str, Any]:
        snapshot = dict(self.latest)
        snapshot["devices"] = await self.devices()
        agents = await self.agent_nodes()
        snapshot["agents"] = {
            "configured": bool(self.settings.agent_token),
            "online": sum(agent["status"] == "online" for agent in agents),
            "total": len(agents),
            "items": agents,
        }
        exporters = dict(self.exporters_latest)
        exporters["nodes"] = await self.exporter_nodes()
        snapshot["exporters"] = exporters
        snapshot["events"] = await self.database.events(12)
        return snapshot

    async def devices(self) -> list[dict[str, Any]]:
        items = await self.database.devices()
        return [item for item in items if self._is_monitored_ip(item["ip"])]

    async def agent_nodes(self) -> list[dict[str, Any]]:
        nodes = await self.database.agents(self.settings.agent_offline_after)
        return [item for item in nodes if item.get("metadata", {}).get("collection_method") != "prometheus"]

    async def exporter_nodes(self) -> list[dict[str, Any]]:
        nodes = await self.database.agents(
            max(self.settings.agent_offline_after, self.settings.prometheus_exporter_interval * 3)
        )
        configured = {target.name for target in self.prometheus.targets}
        return [
            item
            for item in nodes
            if item.get("metadata", {}).get("collection_method") == "prometheus"
            and item.get("metadata", {}).get("target_name") in configured
        ]

    async def exporters(self) -> dict[str, Any]:
        payload = dict(self.exporters_latest)
        payload["nodes"] = await self.exporter_nodes()
        return payload

    async def _collector_loop(self) -> None:
        while self._running:
            started = time.monotonic()
            try:
                await self.collect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # Keep monitoring alive; report the specific failure in the UI.
                await self.database.add_event("error", "collector", "Collection failed", str(exc)[:500])
            elapsed = time.monotonic() - started
            await asyncio.sleep(max(0.1, self.settings.sample_interval - elapsed))

    async def _discovery_loop(self) -> None:
        await asyncio.sleep(3)
        while self._running:
            try:
                hosts = tuple(filter(None, (self.gateway, *self.settings.monitored_hosts)))
                found = await asyncio.to_thread(self.discovery.scan, self.subnet or "", hosts)
                for device in found:
                    device.update({"status": "online", "last_seen": time.time()})
                    await self._register_device(device)
                await self.database.mark_stale_devices(time.time() - self._device_stale_after)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.database.add_event("warning", "discovery", "Device scan failed", str(exc)[:500])
            await asyncio.sleep(self.settings.discovery_interval)

    async def _connectivity_loop(self) -> None:
        while self._running:
            try:
                checks = await asyncio.to_thread(self.connectivity.collect)
                await self.database.save_connectivity_checks(checks)
                successful_internet = [item for item in checks if item["check_type"] == "internet" and item["success"]]
                successful_dns = [item for item in checks if item["check_type"] == "dns" and item["success"]]
                successful_lan = [item for item in checks if item["check_type"].startswith("lan_") and item["success"]]
                internet_checks = [item for item in checks if item["check_type"] == "internet"]
                dns_checks = [item for item in checks if item["check_type"] == "dns"]
                lan_checks = [item for item in checks if item["check_type"].startswith("lan_")]
                internet_ok = bool(successful_internet) if internet_checks else True
                dns_ok = bool(successful_dns) if dns_checks else True
                external_status = (
                    "online" if internet_ok and dns_ok else ("degraded" if internet_ok or dns_ok else "offline")
                ) if internet_checks or dns_checks else "disabled"
                lan_status = (
                    "online" if len(successful_lan) == len(lan_checks)
                    else ("degraded" if successful_lan else "offline")
                ) if lan_checks else "disabled"
                active_statuses = [item for item in (lan_status, external_status) if item != "disabled"]
                status = (
                    "online" if active_statuses and all(item == "online" for item in active_statuses)
                    else ("offline" if active_statuses and all(item == "offline" for item in active_statuses) else "degraded")
                ) if active_statuses else "disabled"
                self.connectivity_latest = {
                    "enabled": True,
                    "status": status,
                    "dns_latency_ms": self._average_latency(successful_dns),
                    "internet_latency_ms": self._average_latency(successful_internet),
                    "lan_latency_ms": self._average_latency(successful_lan),
                    "lan_status": lan_status,
                    "external_status": external_status,
                    "checks": checks,
                    "updated_at": time.time(),
                }
                if status != self._connectivity_status and self._connectivity_status != "checking":
                    severity = "success" if status == "online" else "warning"
                    await self.database.add_event(
                        severity,
                        "connectivity",
                        f"Network probe status changed to {status}",
                        "Configured LAN and optional external probes changed state.",
                    )
                self._connectivity_status = status
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connectivity_latest.update({"status": "error", "updated_at": time.time()})
                await self.database.add_event("warning", "connectivity", "Connectivity checks failed", str(exc)[:500])
            await asyncio.sleep(self.settings.connectivity_interval)

    async def _snmp_loop(self) -> None:
        while self._running:
            try:
                samples, errors = await asyncio.to_thread(self.snmp.collect)
                await self.database.save_snmp_samples(samples)
                metrics: dict[str, float] = {}
                for sample in samples:
                    metrics[sample["metric"]] = round(float(sample["value"]), 2)
                qnap_warning = any(item.get("status") == "degraded" for item in self.snmp.last_details)
                status = "degraded" if samples and (errors or qnap_warning) else ("ok" if samples else "unreachable")
                self.snmp_latest = {
                    "enabled": True,
                    "status": status,
                    "profile": self.settings.snmp_profile,
                    "security": "authPriv" if self.settings.snmp_version == "3" else "community",
                    "metrics": metrics,
                    "details": self.snmp.last_details,
                    "targets": list(self.settings.snmp_targets),
                    "error_count": len(errors),
                    "updated_at": time.time(),
                }
                if status != self._snmp_status and self._snmp_status != "checking":
                    severity = "success" if status == "ok" else "warning"
                    await self.database.add_event(
                        severity,
                        "snmp",
                        f"SNMP status changed to {status}",
                        "Configured SNMP telemetry collection changed state.",
                    )
                self._snmp_status = status
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.snmp_latest.update({"status": "error", "updated_at": time.time()})
                await self.database.add_event("warning", "snmp", "SNMP collection failed", str(exc)[:500])
            await asyncio.sleep(self.settings.snmp_interval)

    async def collect_exporters_once(self) -> dict[str, Any]:
        samples, statuses = await asyncio.to_thread(self.prometheus.collect)
        source_hosts = {target.name: target.hostname for target in self.prometheus.targets}
        for sample in samples:
            target_name = sample.get("metadata", {}).get("target_name", "")
            await self.database.upsert_agent(sample, source_hosts.get(target_name, target_name or "unknown"))
        online = sum(item["status"] == "online" for item in statuses)
        if not statuses:
            status = "disabled"
        elif online == len(statuses):
            status = "ok"
        elif online:
            status = "degraded"
        else:
            status = "error"
        self.exporters_latest = {
            "enabled": self.settings.prometheus_exporters_enabled,
            "configured": bool(self.prometheus.targets),
            "status": status,
            "online": online,
            "total": len(statuses),
            "items": statuses,
            "updated_at": time.time(),
        }
        if status != self._exporter_status and self._exporter_status not in {"checking", "disabled"}:
            severity = "success" if status == "ok" else "warning"
            await self.database.add_event(
                severity,
                "exporter",
                f"Prometheus exporter status changed to {status}",
                f"{online} of {len(statuses)} configured exporters are reachable.",
            )
        self._exporter_status = status
        return self.exporters_latest

    async def _prometheus_loop(self) -> None:
        while self._running:
            try:
                await self.collect_exporters_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.exporters_latest.update({"status": "error", "updated_at": time.time()})
                await self.database.add_event(
                    "warning", "exporter", "Prometheus exporter collection failed", str(exc)[:500]
                )
            await asyncio.sleep(self.settings.prometheus_exporter_interval)

    @staticmethod
    def _average_latency(checks: list[dict[str, Any]]) -> float | None:
        values = [float(item["latency_ms"]) for item in checks if item.get("latency_ms") is not None]
        return round(sum(values) / len(values), 2) if values else None

    async def _refresh_neighbours(self) -> None:
        if self.settings.demo_mode:
            return
        neighbours = await asyncio.to_thread(self.discovery.neighbours)
        for device in neighbours:
            if not self._is_monitored_ip(device["ip"]):
                continue
            device.update({"status": "online", "last_seen": time.time()})
            await self._register_device(device)
        stale = await self.database.mark_stale_devices(time.time() - self._device_stale_after)
        for device in stale:
            label = device.get("display_name") or device.get("hostname") or device["ip"]
            await self.database.add_event("warning", "device", "Device went offline", f"{label} is no longer reachable.", {"ip": device["ip"]})

    async def _register_device(self, device: dict[str, Any]) -> None:
        is_new, previous = await self.database.upsert_device(device)
        if is_new:
            await self.database.add_event(
                "info", "device", "New device detected", f"First observed {device['ip']} on the local network.", {"ip": device["ip"], "mac": device.get("mac")}
            )
        elif previous == "offline" and device.get("status") == "online":
            await self.database.add_event("success", "device", "Device is back online", f"{device['ip']} responded again.", {"ip": device["ip"]})

    def _is_monitored_ip(self, address: str) -> bool:
        if self._network is None:
            return True
        try:
            return ipaddress.ip_address(address) in self._network
        except ValueError:
            return False

    async def _detect_threshold_events(self, sample: dict[str, Any]) -> None:
        thresholds = (
            ("cpu", sample["cpu_percent"], 90.0, "CPU usage is high"),
            ("memory", sample["memory_percent"], 90.0, "Memory usage is high"),
            ("temperature", sample.get("temperature_c") or 0.0, 75.0, "Raspberry Pi temperature is high"),
            ("latency", sample.get("gateway_latency_ms") or 0.0, 100.0, "Gateway latency is high"),
        )
        now = time.time()
        for key, value, limit, title in thresholds:
            if value >= limit and now - self._last_thresholds.get(key, 0) > 300:
                self._last_thresholds[key] = now
                await self.database.add_event("warning", "threshold", title, f"Observed {value:.1f}; threshold is {limit:.1f}.")

    def _health_score(self, sample: dict[str, Any]) -> int:
        score = 100.0
        score -= max(0.0, sample["cpu_percent"] - 65) * 0.45
        score -= max(0.0, sample["memory_percent"] - 70) * 0.45
        score -= max(0.0, sample["disk_percent"] - 80) * 0.7
        temperature = sample.get("temperature_c")
        if temperature is not None:
            score -= max(0.0, temperature - 65) * 1.1
        latency = sample.get("gateway_latency_ms")
        if latency is None and self.gateway:
            score -= 25
        elif latency is not None:
            score -= max(0.0, latency - 25) * 0.18
        score -= min(25.0, sample.get("packet_loss_percent", 0) * 0.5)
        if self.connectivity_latest["status"] == "offline":
            score -= 25
        elif self.connectivity_latest["status"] in {"degraded", "error"}:
            score -= 10
        return max(0, min(100, round(score)))

    async def _demo_sample(self) -> dict[str, Any]:
        self._demo_tick += 1
        tick = self._demo_tick
        devices = (
            ("192.168.10.1", "a0:b1:c2:d3:e4:01", "Gateway", "router", True),
            ("192.168.10.21", "a0:b1:c2:d3:e4:21", "Living Room TV", "tv", True),
            ("192.168.10.34", "a0:b1:c2:d3:e4:34", "Gaming PC", "computer", True),
            ("192.168.10.48", "a0:b1:c2:d3:e4:48", "Kitchen Speaker", "iot", True),
            ("192.168.10.72", "a0:b1:c2:d3:e4:72", "Phone", "phone", True),
            ("192.168.10.93", "a0:b1:c2:d3:e4:93", "NAS", "server", True),
        )
        for index, (ip, mac, name, kind, trusted) in enumerate(devices):
            await self.database.upsert_device({
                "ip": ip, "mac": mac, "hostname": name.lower().replace(" ", "-"), "status": "online",
                "latency_ms": round(1.2 + index * 0.7 + random.random(), 2), "last_seen": time.time(),
            })
            await self.database.update_device(ip, {"display_name": name, "device_type": kind, "is_trusted": trusted})
        wave = math.sin(tick / 4)
        return {
            "ts": time.time(), "cpu_percent": round(24 + 13 * wave + random.random() * 6, 1),
            "memory_percent": round(42 + math.sin(tick / 9) * 5, 1), "memory_used": 3_600_000_000,
            "memory_total": 8_000_000_000, "disk_percent": 38.4, "disk_used": 48_000_000_000,
            "disk_total": 128_000_000_000, "temperature_c": round(49 + wave * 3, 1),
            "load_1m": 0.62, "load_5m": 0.55, "uptime_seconds": 483_920,
            "interface": "eth0", "rx_bps": max(5000, round(2_400_000 + wave * 1_500_000 + random.random() * 850_000)),
            "tx_bps": max(2000, round(420_000 + math.sin(tick / 3) * 300_000 + random.random() * 180_000)),
            "rx_total": 184_000_000_000, "tx_total": 31_000_000_000, "gateway": "192.168.10.1",
            "gateway_latency_ms": round(2.1 + random.random() * 1.6, 1), "packet_loss_percent": 0.0,
            "online_devices": len(devices), "total_devices": len(devices),
        }

    def _empty_snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot", "generated_at": time.time(),
            "system": {"cpu_percent": 0, "memory_percent": 0, "disk_percent": 0, "temperature_c": None},
            "network": {"interface": "detecting", "rx_bps": 0, "tx_bps": 0, "gateway": self.gateway, "gateway_latency_ms": None, "packet_loss_percent": 0},
            "summary": {"online_devices": 0, "total_devices": 0, "health_score": 0, "subnet": self.subnet},
            "devices": [], "connectivity": self.connectivity_latest, "snmp": self.snmp_latest,
            "exporters": self.exporters_latest,
            "agents": {"configured": bool(self.settings.agent_token), "online": 0, "total": 0, "items": []},
            "insights": self.anomaly.last_result, "events": [],
        }
