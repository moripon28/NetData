from __future__ import annotations

import concurrent.futures
import ipaddress
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

import psutil


class TrafficCollector:
    def __init__(self, preferred_interface: str | None = None) -> None:
        self.preferred_interface = preferred_interface
        self._previous: tuple[float, int, int] | None = None

    def collect(self) -> dict[str, Any]:
        counters = psutil.net_io_counters(pernic=True)
        interface = self._select_interface(counters)
        current = counters.get(interface) if interface else None
        now = time.monotonic()
        rx_bps = tx_bps = 0.0
        if current is not None and self._previous is not None:
            elapsed = max(0.001, now - self._previous[0])
            rx_bps = max(0.0, (current.bytes_recv - self._previous[1]) / elapsed)
            tx_bps = max(0.0, (current.bytes_sent - self._previous[2]) / elapsed)
        if current is not None:
            self._previous = (now, current.bytes_recv, current.bytes_sent)
        return {
            "interface": interface or "unknown",
            "rx_bps": round(rx_bps, 1),
            "tx_bps": round(tx_bps, 1),
            "rx_total": current.bytes_recv if current else 0,
            "tx_total": current.bytes_sent if current else 0,
        }

    def _select_interface(self, counters: dict[str, Any]) -> str | None:
        if self.preferred_interface in counters:
            return self.preferred_interface
        candidates = [name for name in counters if name != "lo" and not name.startswith(("veth", "docker", "br-"))]
        if not candidates:
            candidates = [name for name in counters if name != "lo"]
        return max(candidates, key=lambda name: counters[name].bytes_recv + counters[name].bytes_sent) if candidates else None


class DeviceDiscovery:
    PING_TIME = re.compile(r"time[=<]([0-9.]+)\s*ms", re.IGNORECASE)

    def detect_gateway(self) -> str | None:
        route_path = Path("/proc/net/route")
        try:
            for line in route_path.read_text(encoding="utf-8").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    raw = bytes.fromhex(parts[2])
                    return socket.inet_ntoa(raw[::-1])
        except (OSError, ValueError):
            pass
        return None

    def detect_subnet(self) -> str | None:
        try:
            result = subprocess.run(
                ["ip", "-o", "-4", "addr", "show", "scope", "global"],
                capture_output=True, text=True, timeout=3, check=False,
            )
            matches = re.findall(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)", result.stdout)
            for cidr in matches:
                network = ipaddress.ip_interface(cidr).network
                if network.is_private and network.num_addresses <= 1024:
                    return str(network)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return None

    def neighbours(self) -> list[dict[str, Any]]:
        devices: dict[str, dict[str, Any]] = {}
        try:
            result = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=5, check=False)
            for line in result.stdout.splitlines():
                parts = line.split()
                if not parts or not re.fullmatch(r"\d+(?:\.\d+){3}", parts[0]):
                    continue
                state = parts[-1].upper()
                if state in {"FAILED", "INCOMPLETE"}:
                    continue
                mac = None
                if "lladdr" in parts:
                    index = parts.index("lladdr") + 1
                    if index < len(parts) and re.fullmatch(r"[0-9a-f:]{17}", parts[index], re.IGNORECASE):
                        mac = parts[index]
                devices[parts[0]] = {"ip": parts[0], "mac": mac}
        except (OSError, subprocess.SubprocessError):
            pass
        arp_path = Path("/proc/net/arp")
        try:
            for line in arp_path.read_text(encoding="utf-8").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                    devices[parts[0]] = {"ip": parts[0], "mac": parts[3]}
        except OSError:
            pass
        return list(devices.values())

    def ping(self, host: str) -> float | None:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", host], capture_output=True, text=True, timeout=2, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        match = self.PING_TIME.search(result.stdout)
        return round(float(match.group(1)), 2) if match else 0.1

    def resolve_hostname(self, ip: str) -> str | None:
        try:
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, TimeoutError):
            return None

    def scan(self, subnet: str, additional_hosts: Iterable[str] = ()) -> list[dict[str, Any]]:
        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            return []
        hosts = set(str(ip) for ip in network.hosts())
        hosts.update(additional_hosts)
        if len(hosts) > 1024:
            # 最初の1024ホストのみスキャン
            hosts = set(list(hosts)[:1024])

        def probe(ip: str) -> dict[str, Any] | None:
            latency = self.ping(ip)
            return {"ip": ip, "latency_ms": latency} if latency is not None else None

        found: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, len(hosts) or 1)) as executor:
            for result in executor.map(probe, sorted(hosts)):
                if result:
                    found.append(result)
        neighbour_map = {item["ip"]: item for item in self.neighbours()}
        for device in found:
            device.update(neighbour_map.get(device["ip"], {}))
        return found
