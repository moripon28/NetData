from __future__ import annotations

import ipaddress
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path


logger = logging.getLogger(__name__)


DEFAULT_LLM_SYSTEM_PROMPT = (
    "あなたは家庭内ネットワークの運用アナリストです。与えられた観測値だけを使い、必ず日本語で簡潔に報告してください。"
    "見出し、説明、推奨事項を含む出力のすべてを日本語にし、英語で回答しないでください。"
    "データが無い項目は推測せず、断定には必ず数値またはイベントを根拠として添えてください。"
    "報告は『総評』『注目点』『推奨対応』『根拠』の順にし、問題が無い場合もその理由を説明してください。"
    "出力はマークダウン形式で、各見出しには「###」、箇条書きには番号付きリストを使い、要点には太字を使ってください。"
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


AGENT_TOKEN_MIN_LENGTH = 32


def validate_agent_token(token: str) -> None:
    """Fail startup on a structurally weak token; warn on low entropy."""
    if not token:
        return
    if len(token) < AGENT_TOKEN_MIN_LENGTH:
        raise RuntimeError(
            f"AGENT_TOKENは{AGENT_TOKEN_MIN_LENGTH}文字以上にしてください。"
            "乱数値を生成してください（例: openssl rand -hex 32）。"
        )
    counts: dict[str, int] = {}
    for character in token:
        counts[character] = counts.get(character, 0) + 1
    entropy = -sum(count / len(token) * math.log2(count / len(token)) for count in counts.values())
    if entropy < 3.0:
        logger.warning(
            "AGENT_TOKENのエントロピーが低いです（%.2f bits/char）。乱数生成した値の使用を推奨します。", entropy
        )


def validate_web_auth(user: str, password: str) -> None:
    """Fail startup when a username is set without a password.

    A non-empty ``WEB_AUTH_USER`` with an empty password would let anyone log in
    with ``user:`` (empty password), so refuse to start instead of running weakly.
    """
    if user and not password:
        raise RuntimeError(
            "WEB_AUTH_USERが設定されているのでWEB_AUTH_PASSWORDも設定してください。"
            "パスワードの無いBasic認証は推測可能なため使用できません。"
        )


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
    internet_probes_enabled: bool = field(default_factory=lambda: _bool_env("INTERNET_PROBES_ENABLED", False))
    internet_targets: tuple[str, ...] = field(
        default_factory=lambda: _csv_env_default("INTERNET_TARGETS", ("1.1.1.1", "8.8.8.8"))
    )
    dns_servers: tuple[str, ...] = field(default_factory=lambda: _csv_env("DNS_SERVERS"))
    dns_check_name: str = field(default_factory=lambda: os.getenv("DNS_CHECK_NAME", "example.com").strip())
    lan_probe_targets: tuple[str, ...] = field(default_factory=lambda: _csv_env("LAN_PROBE_TARGETS"))
    snmp_enabled: bool = field(default_factory=lambda: _bool_env("SNMP_ENABLED", False))
    snmp_targets: tuple[str, ...] = field(default_factory=lambda: _csv_env("SNMP_TARGETS"))
    snmp_version: str = field(default_factory=lambda: os.getenv("SNMP_VERSION", "2c").strip().lower())
    snmp_profile: str = field(default_factory=lambda: os.getenv("SNMP_PROFILE", "generic").strip().lower())
    snmp_community: str = field(default_factory=lambda: os.getenv("SNMP_COMMUNITY", "public"))
    snmp_username: str = field(default_factory=lambda: os.getenv("SNMP_USERNAME", "").strip())
    snmp_auth_protocol: str = field(default_factory=lambda: os.getenv("SNMP_AUTH_PROTOCOL", "SHA").strip())
    snmp_auth_password: str = field(default_factory=lambda: os.getenv("SNMP_AUTH_PASSWORD", ""))
    snmp_priv_protocol: str = field(default_factory=lambda: os.getenv("SNMP_PRIV_PROTOCOL", "DES").strip())
    snmp_priv_password: str = field(default_factory=lambda: os.getenv("SNMP_PRIV_PASSWORD", ""))
    snmp_interval: int = field(default_factory=lambda: _int_env("SNMP_INTERVAL_SECONDS", 30, 10))
    snmp_timeout: float = field(default_factory=lambda: _float_env("SNMP_TIMEOUT_SECONDS", 2.0, 0.5))
    snmp_interface_index: int = field(default_factory=lambda: _int_env("SNMP_INTERFACE_INDEX", 2, 1))
    snmp_extra_oids: tuple[str, ...] = field(default_factory=lambda: _csv_env("SNMP_EXTRA_OIDS"))
    prometheus_exporters_enabled: bool = field(
        default_factory=lambda: _bool_env("PROMETHEUS_EXPORTERS_ENABLED", False)
    )
    prometheus_exporter_targets: tuple[str, ...] = field(
        default_factory=lambda: _csv_env("PROMETHEUS_EXPORTER_TARGETS")
    )
    prometheus_exporter_interval: int = field(
        default_factory=lambda: _int_env("PROMETHEUS_EXPORTER_INTERVAL_SECONDS", 15, 5)
    )
    prometheus_exporter_timeout: float = field(
        default_factory=lambda: _float_env("PROMETHEUS_EXPORTER_TIMEOUT_SECONDS", 5.0, 1.0)
    )
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
    llm_allow_external: bool = field(default_factory=lambda: _bool_env("LLM_ALLOW_EXTERNAL", False))
    notify_enabled: bool = field(default_factory=lambda: _bool_env("NOTIFY_ENABLED", False))
    notify_server_url: str = field(default_factory=lambda: (os.getenv("NOTIFY_SERVER_URL") or "").strip())
    notify_topic: str = field(default_factory=lambda: (os.getenv("NOTIFY_TOPIC") or "").strip())
    notify_priority: int = field(default_factory=lambda: min(5, _int_env("NOTIFY_PRIORITY", 3, 1)))
    notify_webhook_url: str = field(default_factory=lambda: (os.getenv("NOTIFY_WEBHOOK_URL") or "").strip())
    notify_webhook_token: str = field(default_factory=lambda: (os.getenv("NOTIFY_WEBHOOK_TOKEN") or "").strip())
    notify_cooldown_minutes: int = field(default_factory=lambda: _int_env("NOTIFY_COOLDOWN_MINUTES", 15, 1))
    notify_timeout: float = field(default_factory=lambda: _float_env("NOTIFY_TIMEOUT_SECONDS", 8.0, 1.0))
    notify_allow_external: bool = field(default_factory=lambda: _bool_env("NOTIFY_ALLOW_EXTERNAL", False))
    web_auth_user: str = field(default_factory=lambda: os.getenv("WEB_AUTH_USER", "").strip())
    web_auth_password: str = field(default_factory=lambda: os.getenv("WEB_AUTH_PASSWORD", ""))

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
