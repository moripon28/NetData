from __future__ import annotations

import random
import socket
import struct
import time
from typing import Any, Iterable

from app.collectors.network import DeviceDiscovery


class ConnectivityCollector:
    """Low-volume DNS and ICMP checks that do not inspect user traffic."""

    def __init__(
        self,
        dns_servers: Iterable[str],
        internet_targets: Iterable[str],
        dns_name: str = "example.com",
    ) -> None:
        self.dns_servers = tuple(dict.fromkeys(dns_servers))
        self.internet_targets = tuple(dict.fromkeys(internet_targets))
        self.dns_name = dns_name.strip(".") or "example.com"
        self._ping = DeviceDiscovery()

    def collect(self) -> list[dict[str, Any]]:
        now = time.time()
        checks: list[dict[str, Any]] = []
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
