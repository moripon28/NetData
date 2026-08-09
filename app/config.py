from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_LLM_SYSTEM_PROMPT = (
    "あなたは家庭内ネットワークの運用アナリストです。与えられた観測値だけを使い、必ず日本語で簡潔に報告してください。"
    "見出し、説明、推奨事項を含む出力のすべてを日本語にし、英語で回答しないでください。"
    "データが無い項目は推測せず、断定には必ず数値またはイベントを根拠として添えてください。"
    "報告は『総評』『注目点』『推奨対応』『根拠』の順にし、問題が無い場合もその理由を説明してください。"
    "設定変更や外部への通信を実行したように装わないでください。"
)


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _float_env(name: str, default: float, minimum: float = 0.1) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def _csv_env(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, "").split(",") if item.strip())


def _csv_env_default(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(slots=True)
class Settings:
    app_name: str = "NetPulse"
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "/data")))
    collector_enabled: bool = field(default_factory=lambda: _bool_env("COLLECTOR_ENABLED", True))
    sample_interval: float = field(default_factory=lambda: _float_env("SAMPLE_INTERVAL_SECONDS", 2.0))
    discovery_enabled: bool = field(default_factory=lambda: _bool_env("DISCOVERY_ENABLED", True))
    discovery_interval: int = field(default_factory=lambda: _int_env("DISCOVERY_INTERVAL_SECONDS", 120, 30))
    offline_after: int = field(default_factory=lambda: _int_env("DEVICE_OFFLINE_AFTER_SECONDS", 90, 10))
    retention_days: int = field(default_factory=lambda: _int_env("RETENTION_DAYS", 30, 1))
    network_subnet: str | None = field(default_factory=lambda: os.getenv("NETWORK_SUBNET") or None)
    gateway_host: str | None = field(default_factory=lambda: os.getenv("GATEWAY_HOST") or None)
    monitored_hosts: tuple[str, ...] = field(default_factory=lambda: _csv_env("MONITORED_HOSTS"))
    preferred_interface: str | None = field(default_factory=lambda: os.getenv("NETWORK_INTERFACE") or None)
    cors_origins: tuple[str, ...] = field(default_factory=lambda: _csv_env("CORS_ORIGINS"))
    demo_mode: bool = field(default_factory=lambda: _bool_env("DEMO_MODE", False))
    connectivity_enabled: bool = field(default_factory=lambda: _bool_env("CONNECTIVITY_ENABLED", True))
    connectivity_interval: int = field(default_factory=lambda: _int_env("CONNECTIVITY_INTERVAL_SECONDS", 15, 5))
    internet_targets: tuple[str, ...] = field(
        default_factory=lambda: _csv_env_default("INTERNET_TARGETS", ("1.1.1.1", "8.8.8.8"))
    )
    dns_servers: tuple[str, ...] = field(default_factory=lambda: _csv_env("DNS_SERVERS"))
    dns_check_name: str = field(default_factory=lambda: os.getenv("DNS_CHECK_NAME", "example.com").strip())
    snmp_enabled: bool = field(default_factory=lambda: _bool_env("SNMP_ENABLED", False))
    snmp_targets: tuple[str, ...] = field(default_factory=lambda: _csv_env("SNMP_TARGETS"))
    snmp_community: str = field(default_factory=lambda: os.getenv("SNMP_COMMUNITY", "public"))
    snmp_interval: int = field(default_factory=lambda: _int_env("SNMP_INTERVAL_SECONDS", 30, 10))
    snmp_interface_index: int = field(default_factory=lambda: _int_env("SNMP_INTERFACE_INDEX", 2, 1))
    snmp_extra_oids: tuple[str, ...] = field(default_factory=lambda: _csv_env("SNMP_EXTRA_OIDS"))
    agent_token: str = field(default_factory=lambda: os.getenv("AGENT_TOKEN", ""))
    agent_offline_after: int = field(default_factory=lambda: _int_env("AGENT_OFFLINE_AFTER_SECONDS", 60, 20))
    anomaly_enabled: bool = field(default_factory=lambda: _bool_env("ANOMALY_ENABLED", True))
    anomaly_interval: int = field(default_factory=lambda: _int_env("ANOMALY_INTERVAL_SECONDS", 30, 10))
    anomaly_min_samples: int = field(default_factory=lambda: _int_env("ANOMALY_MIN_SAMPLES", 20, 10))
    llm_report_enabled: bool = field(default_factory=lambda: _bool_env("LLM_REPORT_ENABLED", False))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1").strip())
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "").strip())
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "").strip())
    llm_system_prompt: str = field(
        default_factory=lambda: os.getenv("LLM_SYSTEM_PROMPT", "").strip() or DEFAULT_LLM_SYSTEM_PROMPT
    )
    llm_report_interval: int = field(default_factory=lambda: _int_env("LLM_REPORT_INTERVAL_MINUTES", 60, 15))
    llm_report_lookback: int = field(default_factory=lambda: _int_env("LLM_REPORT_LOOKBACK_MINUTES", 60, 15))
    llm_request_timeout: int = field(default_factory=lambda: _int_env("LLM_REQUEST_TIMEOUT_SECONDS", 120, 10))

    @property
    def database_path(self) -> Path:
        return self.data_dir / "netpulse.db"

    def validated_subnet(self) -> str | None:
        if not self.network_subnet:
            return None
        try:
            network = ipaddress.ip_network(self.network_subnet, strict=False)
        except ValueError:
            return None
        if network.version != 4 or network.num_addresses > 1024:
            return None
        return str(network)
