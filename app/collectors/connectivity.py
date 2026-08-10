from __future__ import annotations

import random
import ipaddress
import re
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx

from app.collectors.network import DeviceDiscovery


_SAFE_PROBE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@dataclass(frozen=True, slots=True)
class LanProbeTarget:
    name: str
    url: str
    scheme: str
    host: str
    port: int | None


def parse_lan_probe_targets(values: Iterable[str]) -> tuple[LanProbeTarget, ...]:
    targets: list[LanProbeTarget] = []
    names: set[str] = set()
    for raw in values:
        if "=" not in raw:
            raise ValueError("LAN probe target must use name=scheme://host format")
        name, url = (part.strip() for part in raw.split("=", 1))
        parsed = urlsplit(url)
        if not _SAFE_PROBE_NAME.fullmatch(name) or parsed.scheme not in {"icmp", "tcp", "http", "https"}:
            raise ValueError(f"Invalid LAN probe target: {name[:64]}")
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError(f"Invalid LAN probe URL for {name}")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"Invalid LAN probe port for {name}") from exc
        if parsed.scheme == "tcp" and port is None:
            raise ValueError(f"TCP probe requires a port: {name}")
        if parsed.scheme == "icmp" and (port is not None or parsed.path not in {"", "/"} or parsed.query):
            raise ValueError(f"ICMP probe accepts only a host: {name}")
        if name in names:
            raise ValueError(f"Duplicate LAN probe target: {name}")
        names.add(name)
        targets.append(LanProbeTarget(name=name, url=url, scheme=parsed.scheme, host=parsed.hostname, port=port))
    return tuple(targets)


class ConnectivityCollector:
    """Low-volume DNS and ICMP checks that do not inspect user traffic."""

    def __init__(
        self,
        dns_servers: Iterable[str],
        internet_targets: Iterable[str],
        dns_name: str = "example.com",
        lan_targets: Iterable[str] = (),
    ) -> None:
        self.dns_servers = tuple(dict.fromkeys(dns_servers))
        self.internet_targets = tuple(dict.fromkeys(internet_targets))
        self.dns_name = dns_name.strip(".") or "example.com"
        self.lan_targets = parse_lan_probe_targets(lan_targets)
        self._ping = DeviceDiscovery()

    def collect(self) -> list[dict[str, Any]]:
        now = time.time()
        checks: list[dict[str, Any]] = []
        for target in self.lan_targets:
            try:
                self._require_local_host(target.host, target.name)
                success, latency, detail = self._probe_lan(target)
            except (OSError, ValueError, httpx.HTTPError) as exc:
                success, latency, detail = False, None, self._safe_error(exc)
            checks.append(
                {
                    "ts": now,
                    "check_type": f"lan_{target.scheme}",
                    "target": target.name,
                    "success": success,
                    "latency_ms": latency,
                    "detail": detail,
                }
            )
        for target in self.internet_targets:
            latency = self._ping.ping(target)
            checks.append(
                {
                    "ts": now,
                    "check_type": "internet",
                    "target": target,
                    "success": latency is not None,
                    "latency_ms": latency,
                    "detail": "ICMP echo" if latency is not None else "No ICMP response",
                }
            )
        for server in self.dns_servers:
            success, latency, detail = self._dns_query(server, self.dns_name)
            checks.append(
                {
                    "ts": now,
                    "check_type": "dns",
                    "target": server,
                    "success": success,
                    "latency_ms": latency,
                    "detail": detail,
                }
            )
        return checks

    def _probe_lan(self, target: LanProbeTarget) -> tuple[bool, float | None, str]:
        if target.scheme == "icmp":
            latency = self._ping.ping(target.host)
            return latency is not None, latency, "ICMP echo" if latency is not None else "No ICMP response"
        if target.scheme == "tcp":
            started = time.monotonic()
            with socket.create_connection((target.host, int(target.port or 0)), timeout=2.0):
                pass
            return True, round((time.monotonic() - started) * 1000, 2), f"TCP {target.port} accepted"
        started = time.monotonic()
        with httpx.Client(timeout=3.0, follow_redirects=False) as client:
            with client.stream("GET", target.url, headers={"User-Agent": "NetPulse/0.2"}) as response:
                status_code = response.status_code
        latency = round((time.monotonic() - started) * 1000, 2)
        return 200 <= status_code < 400, latency, f"HTTP {status_code}"

    @staticmethod
    def _require_local_host(host: str, name: str) -> None:
        try:
            addresses = {ipaddress.ip_address(host)}
        except ValueError:
            try:
                addresses = {
                    ipaddress.ip_address(item[4][0])
                    for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
                }
            except socket.gaierror as exc:
                raise ValueError(f"LAN probe host cannot be resolved: {name}") from exc
        if not addresses or any(not (address.is_private or address.is_loopback or address.is_link_local) for address in addresses):
            raise ValueError(f"LAN probe target must resolve only to a local address: {name}")

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"HTTP {exc.response.status_code}"
        if isinstance(exc, httpx.TimeoutException):
            return "request timed out"
        if isinstance(exc, httpx.HTTPError):
            return "connection failed"
        if isinstance(exc, TimeoutError):
            return "request timed out"
        return str(exc)[:160]

    def _dns_query(self, server: str, name: str) -> tuple[bool, float | None, str]:
        request_id = random.randint(0, 65535)
        labels = name.encode("idna").split(b".")
        question = b"".join(bytes((len(label),)) + label for label in labels) + b"\x00"
        packet = struct.pack("!HHHHHH", request_id, 0x0100, 1, 0, 0, 0) + question + struct.pack("!HH", 1, 1)
        started = time.monotonic()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(2.0)
                sock.sendto(packet, (server, 53))
                response, _ = sock.recvfrom(4096)
        except (OSError, TimeoutError) as exc:
            return False, None, type(exc).__name__
        latency = round((time.monotonic() - started) * 1000, 2)
        if len(response) < 12:
            return False, latency, "Short DNS response"
        response_id, flags, _, answers, _, _ = struct.unpack("!HHHHHH", response[:12])
        rcode = flags & 0x000F
        if response_id != request_id:
            return False, latency, "Mismatched DNS response"
        if rcode != 0:
            return False, latency, f"DNS RCODE {rcode}"
        return answers > 0, latency, f"{answers} answer(s) for {name}"
