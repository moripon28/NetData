from __future__ import annotations

import hashlib
import ipaddress
import math
import re
import socket
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx


_METRIC_LINE = re.compile(
    r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})?\s+([^\s]+)(?:\s+\d+)?$"
)
_LABEL = re.compile(r'(\w+)\s*=\s*"((?:\\.|[^"\\])*)"(?:\s*,\s*|$)')
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_VIRTUAL_INTERFACES = ("lo", "loopback", "veth", "docker", "br-", "virbr", "tun", "tap")
_VIRTUAL_FILESYSTEMS = {
    "autofs", "cgroup", "cgroup2", "configfs", "debugfs", "devpts", "devtmpfs", "fusectl",
    "hugetlbfs", "mqueue", "overlay", "proc", "pstore", "securityfs", "sysfs", "tmpfs", "tracefs",
}


@dataclass(frozen=True, slots=True)
class ExporterTarget:
    name: str
    url: str

    @property
    def target_id(self) -> str:
        digest = hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:20]
        return f"exporter-{digest}"

    @property
    def hostname(self) -> str:
        return urlsplit(self.url).hostname or self.name


def parse_exporter_targets(values: Iterable[str]) -> tuple[ExporterTarget, ...]:
    targets: list[ExporterTarget] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for raw in values:
        if "=" not in raw:
            raise ValueError("Prometheus exporter target must use name=http://host:port/metrics format")
        name, raw_url = (part.strip() for part in raw.split("=", 1))
        if not _SAFE_NAME.fullmatch(name):
            raise ValueError(f"Invalid Prometheus exporter target name: {name[:64]}")
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid Prometheus exporter URL for {name}")
        if parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise ValueError(f"Prometheus exporter URL for {name} must not contain credentials, query, or fragment")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"Invalid Prometheus exporter port for {name}") from exc
        netloc = parsed.hostname
        if ":" in netloc and not netloc.startswith("["):
            netloc = f"[{netloc}]"
        if port is not None:
            netloc = f"{netloc}:{port}"
        path = parsed.path.rstrip("/") or "/metrics"
        url = urlunsplit((parsed.scheme, netloc, path, "", ""))
        if name in seen_names or url in seen_urls:
            raise ValueError(f"Duplicate Prometheus exporter target: {name}")
        seen_names.add(name)
        seen_urls.add(url)
        targets.append(ExporterTarget(name=name, url=url))
    return tuple(targets)


def _unescape_label(value: str) -> str:
    return value.replace(r"\n", "\n").replace(r'\"', '"').replace(r"\\", "\\")


def parse_prometheus_text(text: str) -> dict[str, list[tuple[dict[str, str], float]]]:
    metrics: dict[str, list[tuple[dict[str, str], float]]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _METRIC_LINE.match(line)
        if not match:
            continue
        try:
            value = float(match.group(3))
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        labels: dict[str, str] = {}
        labels_text = match.group(2) or ""
        position = 0
        while position < len(labels_text):
            label = _LABEL.match(labels_text, position)
            if not label:
                labels = {}
                break
            labels[label.group(1)] = _unescape_label(label.group(2))
            position = label.end()
        metrics.setdefault(match.group(1), []).append((labels, value))
    return metrics


class PrometheusExporterCollector:
    """Scrape local node_exporter/windows_exporter endpoints and normalize host metrics."""

    def __init__(self, targets: Iterable[str], timeout: float = 5.0, max_response_bytes: int = 4_000_000) -> None:
        self.targets = parse_exporter_targets(targets)
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self._previous_cpu: dict[str, tuple[float, float]] = {}
        self._previous_network: dict[str, tuple[float, float, float]] = {}

    def collect(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        samples: list[dict[str, Any]] = []
        statuses: list[dict[str, Any]] = []
        with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
            for target in self.targets:
                started = time.monotonic()
                try:
                    self._require_local_target(target)
                    response = client.get(target.url, headers={"Accept": "text/plain", "User-Agent": "NetPulse/0.2"})
                    response.raise_for_status()
                    if len(response.content) > self.max_response_bytes:
                        raise ValueError("Exporter response is too large")
                    metrics = parse_prometheus_text(response.text)
                    sample = self._normalize(target, metrics)
                    samples.append(sample)
                    statuses.append({
                        "name": target.name,
                        "url": target.url,
                        "status": "online",
                        "kind": sample["metadata"]["exporter_kind"],
                        "duration_ms": round((time.monotonic() - started) * 1000, 2),
                        "error": "",
                        "updated_at": time.time(),
                    })
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    statuses.append({
                        "name": target.name,
                        "url": target.url,
                        "status": "error",
                        "kind": "unknown",
                        "duration_ms": round((time.monotonic() - started) * 1000, 2),
                        "error": self._safe_error(exc),
                        "updated_at": time.time(),
                    })
        return samples, statuses

    @staticmethod
    def _require_local_target(target: ExporterTarget) -> None:
        host = target.hostname
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            try:
                addresses = {
                    ipaddress.ip_address(item[4][0])
                    for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
                }
            except socket.gaierror as exc:
                raise ValueError(f"Exporter host cannot be resolved: {target.name}") from exc
        if not addresses or any(not (address.is_private or address.is_loopback or address.is_link_local) for address in addresses):
            raise ValueError(f"Exporter target must resolve only to a local address: {target.name}")

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"HTTP {exc.response.status_code}"
        if isinstance(exc, httpx.TimeoutException):
            return "request timed out"
        if isinstance(exc, httpx.HTTPError):
            return "connection failed"
        return str(exc)[:160]

    def _normalize(
        self, target: ExporterTarget, metrics: dict[str, list[tuple[dict[str, str], float]]]
    ) -> dict[str, Any]:
        if "node_uname_info" in metrics or "node_cpu_seconds_total" in metrics:
            return self._normalize_node(target, metrics)
        if "windows_os_info" in metrics or "windows_cpu_time_total" in metrics:
            return self._normalize_windows(target, metrics)
        raise ValueError("Unsupported exporter: expected node_exporter or windows_exporter metrics")

    def _normalize_node(
        self, target: ExporterTarget, metrics: dict[str, list[tuple[dict[str, str], float]]]
    ) -> dict[str, Any]:
        info = self._first_labels(metrics, "node_uname_info")
        total_memory = self._first_value(metrics, "node_memory_MemTotal_bytes")
        available_memory = self._first_value(metrics, "node_memory_MemAvailable_bytes")
        disk_percent = self._filesystem_percent(
            metrics, "node_filesystem_size_bytes", "node_filesystem_avail_bytes", ("mountpoint",), "/"
        )
        rx_total = self._sum_interfaces(metrics, "node_network_receive_bytes_total", ("device",))
        tx_total = self._sum_interfaces(metrics, "node_network_transmit_bytes_total", ("device",))
        temperature = self._temperature(metrics, ("node_hwmon_temp_celsius", "node_thermal_zone_temp"))
        boot_time = self._first_value(metrics, "node_boot_time_seconds")
        return self._payload(
            target=target,
            hostname=info.get("nodename") or target.name,
            os_name=info.get("sysname") or "Linux",
            os_version=info.get("release", ""),
            architecture=info.get("machine", ""),
            kind="node_exporter",
            cpu_percent=self._cpu_percent(target.target_id, metrics.get("node_cpu_seconds_total", [])),
            memory_percent=self._usage_percent(total_memory, available_memory),
            disk_percent=disk_percent,
            temperature_c=temperature,
            uptime_seconds=max(0, int(time.time() - boot_time)) if boot_time else 0,
            rx_total=rx_total,
            tx_total=tx_total,
        )

    def _normalize_windows(
        self, target: ExporterTarget, metrics: dict[str, list[tuple[dict[str, str], float]]]
    ) -> dict[str, Any]:
        info = self._first_labels(metrics, "windows_os_info")
        computer = self._first_labels(metrics, "windows_cs_hostname")
        total_memory = self._first_available_value(
            metrics, ("windows_memory_physical_total_bytes", "windows_cs_physical_memory_bytes")
        )
        available_memory = self._first_available_value(
            metrics,
            (
                "windows_memory_physical_free_bytes",
                "windows_os_physical_memory_free_bytes",
                "windows_memory_available_bytes",
            ),
        )
        disk_percent = self._filesystem_percent(
            metrics, "windows_logical_disk_size_bytes", "windows_logical_disk_free_bytes", ("volume", "device"), "C:"
        )
        rx_total = self._sum_interfaces(metrics, "windows_net_bytes_received_total", ("nic", "name"))
        tx_total = self._sum_interfaces(metrics, "windows_net_bytes_sent_total", ("nic", "name"))
        temperature = self._temperature(metrics, ("windows_thermalzone_temperature_celsius",))
        uptime = self._first_value(metrics, "windows_system_system_up_time")
        hostname = computer.get("hostname") or info.get("hostname") or target.name
        return self._payload(
            target=target,
            hostname=hostname,
            os_name="Windows",
            os_version=info.get("version", info.get("product", "")),
            architecture=info.get("architecture", ""),
            kind="windows_exporter",
            cpu_percent=self._cpu_percent(target.target_id, metrics.get("windows_cpu_time_total", [])),
            memory_percent=self._usage_percent(total_memory, available_memory),
            disk_percent=disk_percent,
            temperature_c=temperature,
            uptime_seconds=max(0, int(uptime or 0)),
            rx_total=rx_total,
            tx_total=tx_total,
        )

    def _payload(
        self,
        *,
        target: ExporterTarget,
        hostname: str,
        os_name: str,
        os_version: str,
        architecture: str,
        kind: str,
        cpu_percent: float,
        memory_percent: float,
        disk_percent: float,
        temperature_c: float | None,
        uptime_seconds: int,
        rx_total: float,
        tx_total: float,
    ) -> dict[str, Any]:
        now = time.monotonic()
        rx_bps = tx_bps = 0.0
        previous = self._previous_network.get(target.target_id)
        if previous:
            elapsed = max(0.001, now - previous[0])
            rx_bps = max(0.0, (rx_total - previous[1]) / elapsed)
            tx_bps = max(0.0, (tx_total - previous[2]) / elapsed)
        self._previous_network[target.target_id] = (now, rx_total, tx_total)
        return {
            "node_id": target.target_id,
            "hostname": hostname[:255],
            "os_name": os_name[:80],
            "os_version": os_version[:255],
            "agent_version": kind,
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory_percent, 1),
            "disk_percent": round(disk_percent, 1),
            "temperature_c": round(temperature_c, 1) if temperature_c is not None else None,
            "uptime_seconds": uptime_seconds,
            "rx_bps": round(rx_bps, 1),
            "tx_bps": round(tx_bps, 1),
            "metadata": {
                "collection_method": "prometheus",
                "exporter_kind": kind,
                "target_name": target.name,
                "architecture": architecture,
            },
        }

    def _cpu_percent(self, target_id: str, values: list[tuple[dict[str, str], float]]) -> float:
        total = sum(value for _, value in values)
        idle = sum(value for labels, value in values if labels.get("mode", "").lower() in {"idle", "iowait"})
        previous = self._previous_cpu.get(target_id)
        self._previous_cpu[target_id] = (total, idle)
        if not previous or total <= previous[0]:
            return 0.0
        total_delta = total - previous[0]
        idle_delta = max(0.0, idle - previous[1])
        return max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))

    @staticmethod
    def _usage_percent(total: float, available: float) -> float:
        if total <= 0:
            return 0.0
        return max(0.0, min(100.0, (total - max(0.0, available)) / total * 100.0))

    @staticmethod
    def _first_value(metrics: dict[str, list[tuple[dict[str, str], float]]], name: str) -> float:
        values = metrics.get(name, [])
        return float(values[0][1]) if values else 0.0

    @classmethod
    def _first_available_value(
        cls, metrics: dict[str, list[tuple[dict[str, str], float]]], names: tuple[str, ...]
    ) -> float:
        for name in names:
            if name in metrics:
                return cls._first_value(metrics, name)
        return 0.0

    @staticmethod
    def _first_labels(metrics: dict[str, list[tuple[dict[str, str], float]]], name: str) -> dict[str, str]:
        values = metrics.get(name, [])
        return values[0][0] if values else {}

    @staticmethod
    def _temperature(
        metrics: dict[str, list[tuple[dict[str, str], float]]], names: tuple[str, ...]
    ) -> float | None:
        for name in names:
            values = [value for _, value in metrics.get(name, []) if -50 <= value <= 200]
            if values:
                return max(values)
        return None

    @staticmethod
    def _label_value(labels: dict[str, str], candidates: tuple[str, ...]) -> str:
        return next((labels[name] for name in candidates if labels.get(name)), "")

    def _sum_interfaces(
        self,
        metrics: dict[str, list[tuple[dict[str, str], float]]],
        name: str,
        label_names: tuple[str, ...],
    ) -> float:
        total = 0.0
        for labels, value in metrics.get(name, []):
            interface = self._label_value(labels, label_names).lower()
            if interface and interface.startswith(_VIRTUAL_INTERFACES):
                continue
            total += value
        return total

    def _filesystem_percent(
        self,
        metrics: dict[str, list[tuple[dict[str, str], float]]],
        size_name: str,
        available_name: str,
        label_names: tuple[str, ...],
        preferred: str,
    ) -> float:
        sizes: dict[str, tuple[float, str]] = {}
        available: dict[str, float] = {}
        for labels, value in metrics.get(size_name, []):
            key = self._label_value(labels, label_names)
            fstype = labels.get("fstype", "").lower()
            if key and fstype not in _VIRTUAL_FILESYSTEMS:
                sizes[key] = (value, fstype)
        for labels, value in metrics.get(available_name, []):
            key = self._label_value(labels, label_names)
            if key:
                available[key] = value
        candidates = [preferred] if preferred in sizes else sorted(sizes, key=lambda key: sizes[key][0], reverse=True)
        for key in candidates:
            size = sizes[key][0]
            if size > 0 and key in available:
                return self._usage_percent(size, available[key])
        return 0.0
