from __future__ import annotations

import math
import time
from typing import Any

from app.database import Database


class AnomalyDetector:
    LABELS = {
        "cpu_percent": "CPU usage",
        "memory_percent": "Memory usage",
        "temperature_c": "Raspberry Pi temperature",
        "gateway_latency_ms": "Gateway latency",
        "rx_log": "Download traffic",
        "tx_log": "Upload traffic",
        "online_devices": "Online device count",
        "dns_latency_ms": "DNS latency",
    }
    MINIMUM_DELTAS = {
        "cpu_percent": 15.0,
        "memory_percent": 10.0,
        "temperature_c": 5.0,
        "gateway_latency_ms": 10.0,
        "rx_log": 1.0,
        "tx_log": 1.0,
        "online_devices": 2.0,
        "dns_latency_ms": 15.0,
    }

    def __init__(self, database: Database, minimum_samples: int = 20) -> None:
        self.database = database
        self.minimum_samples = minimum_samples
        self.last_result: dict[str, Any] = {
            "status": "learning", "learning_progress": 0, "active": [], "hour_bucket": None,
        }
        self._event_cooldowns: dict[str, float] = {}

    async def observe(
        self, sample: dict[str, Any], connectivity: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        hour_bucket = time.localtime().tm_hour
        dns_latency = connectivity.get("dns_latency_ms")
        values = {
            "cpu_percent": sample.get("cpu_percent"),
            "memory_percent": sample.get("memory_percent"),
            "temperature_c": sample.get("temperature_c"),
            "gateway_latency_ms": sample.get("gateway_latency_ms"),
            "rx_log": math.log1p(max(0.0, sample.get("rx_bps", 0.0))),
            "tx_log": math.log1p(max(0.0, sample.get("tx_bps", 0.0))),
            "online_devices": float(sample.get("online_devices", 0)),
            "dns_latency_ms": dns_latency,
        }
        anomalies: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for metric, value in values.items():
            if value is None:
                continue
            result = await self.database.observe_baseline(metric, hour_bucket, float(value), self.minimum_samples)
            results.append(result)
            delta = abs(float(value) - result["mean"])
            if (
                result["count"] >= self.minimum_samples
                and result["z_score"] >= 3.5
                and delta >= self.MINIMUM_DELTAS[metric]
            ):
                display_value = math.expm1(value) if metric in {"rx_log", "tx_log"} else value
                anomaly = {
                    "metric": metric,
                    "label": self.LABELS[metric],
                    "score": round(result["z_score"], 1),
                    "value": round(float(display_value), 2),
                    "direction": "high" if value > result["mean"] else "low",
                }
                anomalies.append(anomaly)
        lowest_count = min((result["count"] for result in results), default=0)
        progress = min(100, round(lowest_count / self.minimum_samples * 100))
        self.last_result = {
            "status": "anomaly" if anomalies else ("normal" if progress >= 100 else "learning"),
            "learning_progress": progress,
            "active": anomalies,
            "hour_bucket": hour_bucket,
            "minimum_samples": self.minimum_samples,
            "updated_at": time.time(),
        }
        now = time.time()
        new_events = []
        for anomaly in anomalies:
            key = anomaly["metric"]
            if now - self._event_cooldowns.get(key, 0) >= 900:
                self._event_cooldowns[key] = now
                new_events.append(anomaly)
        return self.last_result, new_events
