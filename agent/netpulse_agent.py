#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import psutil


VERSION = "0.3.0"


def stable_node_id() -> str:
    candidates = [socket.gethostname(), str(__import__("uuid").getnode())]
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            candidates.append(path.read_text(encoding="utf-8").strip())
            break
        except OSError:
            continue
    digest = hashlib.sha256("|".join(candidates).encode("utf-8")).hexdigest()[:20]
    return f"node-{digest}"


def temperature() -> float | None:
    try:
        sensors = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    for entries in sensors.values():
        if entries:
            return round(float(entries[0].current), 1)
    return None


def socket_counts() -> dict[str, int | None]:
    try:
        connections = psutil.net_connections(kind="inet")
    except (OSError, psutil.Error):
        return {
            "socket_count": None,
            "established_socket_count": None,
            "listening_socket_count": None,
        }
    return {
        "socket_count": len(connections),
        "established_socket_count": sum(
            connection.status == psutil.CONN_ESTABLISHED for connection in connections
        ),
        "listening_socket_count": sum(
            connection.status == psutil.CONN_LISTEN for connection in connections
        ),
    }


class Agent:
    def __init__(self, server: str, token: str, interval: int, verify_tls: bool = True) -> None:
        self.base = server.rstrip("/")
        self.endpoint = f"{self.base}/api/v1/agent/heartbeat"
        self.token = token.encode("utf-8")
        self.interval = max(5, interval)
        self.verify_tls = verify_tls
        self.node_id = stable_node_id()
        self._previous_network: tuple[float, int, int] | None = None
        self._clock_offset = 0.0

    def sync_clock(self) -> bool:
        try:
            probe = urllib.request.Request(
                f"{self.base}/api/health", headers={"User-Agent": f"NetPulse-Agent/{VERSION}"}
            )
            context = None if self.verify_tls else ssl._create_unverified_context()
            with urllib.request.urlopen(probe, timeout=5, context=context) as response:
                payload = json.loads(response.read().decode("utf-8"))
            offset = float(payload["server_time"]) - time.time()
        except (OSError, ValueError, KeyError):
            return False
        if abs(offset) > 86_400:
            return False
        self._clock_offset = offset
        return True

    def payload(self) -> dict[str, Any]:
        now = time.monotonic()
        counters = psutil.net_io_counters()
        rx_bps = tx_bps = 0.0
        if self._previous_network:
            elapsed = max(0.001, now - self._previous_network[0])
            rx_bps = max(0.0, (counters.bytes_recv - self._previous_network[1]) / elapsed)
            tx_bps = max(0.0, (counters.bytes_sent - self._previous_network[2]) / elapsed)
        self._previous_network = (now, counters.bytes_recv, counters.bytes_sent)
        root = Path.home().anchor or "/"
        disk = psutil.disk_usage(root)
        sockets = socket_counts()
        try:
            load_1m: float | None = round(float(psutil.getloadavg()[0]), 2)
        except (AttributeError, OSError):
            load_1m = None
        try:
            process_count: int | None = len(psutil.pids())
        except (OSError, psutil.Error):
            process_count = None
        return {
            "node_id": self.node_id,
            "hostname": socket.gethostname(),
            "os_name": platform.system(),
            "os_version": platform.version()[:255],
            "agent_version": VERSION,
            "cpu_percent": round(psutil.cpu_percent(interval=0.2), 1),
            "memory_percent": round(psutil.virtual_memory().percent, 1),
            "disk_percent": round(disk.percent, 1),
            "temperature_c": temperature(),
            "load_1m": load_1m,
            "process_count": process_count,
            "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
            "rx_bps": round(rx_bps, 1),
            "tx_bps": round(tx_bps, 1),
            **sockets,
            "metadata": {"architecture": platform.machine(), "python": platform.python_version()},
        }

    def send_once(self) -> bool:
        body = json.dumps(self.payload(), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        timestamp = str(int(time.time() + self._clock_offset))
        signature = hmac.new(self.token, timestamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Agent-Timestamp": timestamp,
                "X-Agent-Signature": signature,
                "User-Agent": f"NetPulse-Agent/{VERSION}",
            },
        )
        context = None if self.verify_tls else ssl._create_unverified_context()
        try:
            with urllib.request.urlopen(request, timeout=10, context=context) as response:
                if response.status != 200:
                    raise RuntimeError(f"Server returned HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail", "")
            except (OSError, ValueError):
                pass
            if exc.code == 401 and "Expired" in detail:
                return False
            raise
        return True

    def run(self, once: bool = False) -> int:
        self.sync_clock()
        while True:
            try:
                if not self.send_once():
                    print(
                        "Heartbeat rejected as expired; resyncing clock from the server.",
                        file=sys.stderr,
                        flush=True,
                    )
                    if self.sync_clock():
                        self.send_once()
                if once:
                    return 0
            except (OSError, urllib.error.URLError, RuntimeError) as exc:
                print(f"NetPulse heartbeat failed: {type(exc).__name__}", file=sys.stderr, flush=True)
                if once:
                    return 1
            time.sleep(self.interval)


def read_token(args: argparse.Namespace) -> str:
    if args.token_file:
        return Path(args.token_file).read_text(encoding="utf-8").strip()
    return args.token or os.getenv("NETPULSE_AGENT_TOKEN", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Signed NetPulse host metrics agent")
    parser.add_argument("--server", default=os.getenv("NETPULSE_SERVER", "http://localhost:39080"))
    parser.add_argument("--token", default="", help=argparse.SUPPRESS)
    parser.add_argument("--token-file", default=os.getenv("NETPULSE_TOKEN_FILE", ""))
    parser.add_argument("--interval", type=int, default=int(os.getenv("NETPULSE_INTERVAL", "15")))
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--once", action="store_true", help="Send one heartbeat and exit")
    args = parser.parse_args()
    token = read_token(args)
    if not token:
        print("Agent token is not configured.", file=sys.stderr)
        return 2
    return Agent(args.server, token, args.interval, not args.insecure).run(args.once)


if __name__ == "__main__":
    raise SystemExit(main())
