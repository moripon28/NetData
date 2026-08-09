from __future__ import annotations

from pathlib import Path
from typing import Any

import psutil


class SystemCollector:
    THERMAL_PATHS = (
        Path("/sys/class/thermal/thermal_zone0/temp"),
        Path("/host/sys/class/thermal/thermal_zone0/temp"),
    )

    def collect(self) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
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
            "uptime_seconds": max(0, int(__import__("time").time() - psutil.boot_time())),
        }

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
