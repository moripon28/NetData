from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import psutil


class SystemCollector:
    THERMAL_PATHS = (
        Path("/sys/class/thermal/thermal_zone0/temp"),
        Path("/host/sys/class/thermal/thermal_zone0/temp"),
    )

    def __init__(self, disk_path: str | Path = "/") -> None:
        self.disk_path = str(disk_path)
        self._socket_cache: tuple[float, dict[str, int | None]] | None = None

    def collect(self) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        try:
            disk = psutil.disk_usage(self.disk_path)
        except OSError:
            disk = psutil.disk_usage("/")
        load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
        socket_counts = self._socket_counts()
        try:
            process_count: int | None = len(psutil.pids())
        except (OSError, psutil.Error):
            process_count = None
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used": memory.used,
            "memory_total": memory.total,
            "disk_percent": round(disk.percent, 1),
            "disk_used": disk.used,
            "disk_total": disk.total,
            "temperature_c": self._temperature(),
            "load_1m": round(load[0], 2),
            "load_5m": round(load[1], 2),
            "process_count": process_count,
            "uptime_seconds": max(0, int(__import__("time").time() - psutil.boot_time())),
            **socket_counts,
        }

    def _socket_counts(self) -> dict[str, int | None]:
        now = time.monotonic()
        if self._socket_cache and now - self._socket_cache[0] < 5:
            return dict(self._socket_cache[1])
        try:
            connections = psutil.net_connections(kind="inet")
        except (OSError, psutil.Error):
            counts: dict[str, int | None] = {
                "socket_count": None,
                "established_socket_count": None,
                "listening_socket_count": None,
            }
        else:
            counts = {
                "socket_count": len(connections),
                "established_socket_count": sum(
                    connection.status == psutil.CONN_ESTABLISHED for connection in connections
                ),
                "listening_socket_count": sum(
                    connection.status == psutil.CONN_LISTEN for connection in connections
                ),
            }
        self._socket_cache = (now, counts)
        return dict(counts)

    def _temperature(self) -> float | None:
        for path in self.THERMAL_PATHS:
            try:
                value = float(path.read_text(encoding="utf-8").strip())
                return round(value / 1000 if value > 200 else value, 1)
            except (OSError, ValueError):
                continue
        try:
            sensors = psutil.sensors_temperatures()
        except (AttributeError, OSError):
            return None
        for entries in sensors.values():
            if entries:
                return round(float(entries[0].current), 1)
        return None
