from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.config import Settings
from app.database import Database
from app.llm import LocalOnlyTransport, SecretCipher, _is_local_target


logger = logging.getLogger(__name__)


TOPIC_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

_NTFY_TAGS = {
    "error": "rotating_light,critical",
    "warning": "warning,warning",
    "success": "white_check_mark",
    "info": "information_source",
}


def _require_http_url(url: str, name: str, allow_query: bool) -> str:
    parsed = urlsplit(url.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (not allow_query and parsed.query)
    ):
        raise ValueError(f"{name}には有効なhttpまたはhttpsのURLを指定してください。")
    return url.strip()


def validate_ntfy_server_url(server_url: str, allow_external: bool) -> str:
    normalized = _require_http_url(server_url, "ntfyサーバーURL", allow_query=False)
    if not normalized:
        raise ValueError("ntfyサーバーURLを入力してください。")
    host = urlsplit(normalized).hostname or ""
    if not allow_external and not _is_local_target(host):
        raise ValueError(
            "ntfyサーバーURLはローカルネットワーク内のアドレスにしてください。"
            "外部サーバーに送信する場合はNOTIFY_ALLOW_EXTERNAL=trueを有効にしてください。"
        )
    return normalized.rstrip("/")


def validate_webhook_url(webhook_url: str, allow_external: bool) -> str:
    normalized = _require_http_url(webhook_url, "Webhook URL", allow_query=True)
    if not normalized:
        raise ValueError("Webhook URLを入力してください。")
    host = urlsplit(normalized).hostname or ""
    if not allow_external and not _is_local_target(host):
        raise ValueError(
            "Webhook URLはローカルネットワーク内のアドレスにしてください。"
            "外部サーバーに送信する場合はNOTIFY_ALLOW_EXTERNAL=trueを有効にしてください。"
        )
    return normalized


class _NotifyRequest:
    def __init__(self, url: str, headers: dict[str, str], body: bytes) -> None:
        self.url = url
        self.headers = headers
        self.body = body


class NotificationService:
    """Push monitoring events to ntfy and/or a generic JSON webhook.

    Delivery is best-effort: failures are logged to ``notify_log`` and never
    raise into the monitoring loops that trigger them.
    """

    def __init__(
        self,
        settings: Settings,
        database: Database,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.transport = transport
        self.cipher = SecretCipher(settings.data_dir / ".notify-settings.key")
        self._cooldown: dict[str, float] = {}

    async def initialize(self) -> None:
        await self.database.ensure_notify_settings(
            {
                "enabled": self.settings.notify_enabled,
                "server_url": self.settings.notify_server_url,
                "topic": self.settings.notify_topic,
                "priority": self.settings.notify_priority,
                "webhook_url": self.settings.notify_webhook_url,
                "webhook_token_encrypted": self.cipher.encrypt(self.settings.notify_webhook_token),
                "cooldown_minutes": self.settings.notify_cooldown_minutes,
            }
        )

    async def public_settings(self) -> dict[str, Any]:
        values = await self.database.notify_settings()
        return {
            "enabled": values["enabled"],
            "server_url": values["server_url"],
            "topic": values["topic"],
            "priority": values["priority"],
            "webhook_url": values["webhook_url"],
            "webhook_token_configured": bool(values["webhook_token_encrypted"]),
            "cooldown_minutes": values["cooldown_minutes"],
            "updated_at": values["updated_at"],
            "external_allowed": self.settings.notify_allow_external,
        }

    async def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(updates)
        if "server_url" in normalized:
            value = str(normalized["server_url"]).strip()
            normalized["server_url"] = (
                validate_ntfy_server_url(value, self.settings.notify_allow_external) if value else ""
            )
        if "webhook_url" in normalized:
            value = str(normalized["webhook_url"]).strip()
            normalized["webhook_url"] = (
                validate_webhook_url(value, self.settings.notify_allow_external) if value else ""
            )
        if "topic" in normalized:
            normalized["topic"] = str(normalized["topic"]).strip()
            if normalized["topic"] and not TOPIC_PATTERN.fullmatch(normalized["topic"]):
                raise ValueError("ntfyトピックは英数字と. _ -で1〜100文字にしてください。")
        if "priority" in normalized:
            normalized["priority"] = int(normalized["priority"])
        if "cooldown_minutes" in normalized:
            normalized["cooldown_minutes"] = int(normalized["cooldown_minutes"])
        if "enabled" in normalized:
            normalized["enabled"] = bool(normalized["enabled"])
        if "webhook_token" in normalized:
            normalized["webhook_token_encrypted"] = self.cipher.encrypt(
                str(normalized.pop("webhook_token")).strip()
            )
        await self.database.update_notify_settings(normalized)
        return await self.public_settings()

    @staticmethod
    def _channel_configured(values: dict[str, Any]) -> bool:
        return bool(values["server_url"] and values["topic"]) or bool(values["webhook_url"])

    @staticmethod
    def _should_notify(values: dict[str, Any], severity: str, category: str) -> bool:
        if severity in {"warning", "error"}:
            return True
        return severity in {"info", "success"} and category == "device"

    def _build_request(self, values: dict[str, Any], severity: str, category: str, title: str, detail: str) -> _NotifyRequest:
        if values["server_url"] and values["topic"]:
            url = f"{values['server_url'].rstrip('/')}/{quote(values['topic'], safe='')}"
            headers = {
                "Content-Type": "text/plain; charset=utf-8",
                "Title": title[:250],
                "Priority": str(int(values["priority"])),
                "Tags": _NTFY_TAGS.get(severity, _NTFY_TAGS["info"]),
                "X-User-Agent": "NetPulse",
            }
            body = f"[{severity}] {category}: {title} - {detail}".encode("utf-8")
            return _NotifyRequest(url, headers, body)
        headers = {"Content-Type": "application/json"}
        token = self.cipher.decrypt(values["webhook_token_encrypted"])
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {
            "source": "netpulse",
            "severity": severity,
            "category": category,
            "title": title,
            "detail": detail,
            "ts": time.time(),
        }
        return _NotifyRequest(values["webhook_url"], headers, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _channel_name(self, values: dict[str, Any]) -> str:
        if values["server_url"] and values["topic"]:
            return "ntfy"
        return "webhook"

    def _transport_for(self) -> httpx.AsyncBaseTransport:
        if self.transport is not None:
            return self.transport
        return LocalOnlyTransport(self.settings.notify_allow_external)

    async def _send(self, request: _NotifyRequest) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.notify_timeout, trust_env=False, transport=self._transport_for()
            ) as client:
                response = await client.post(
                    request.url,
                    content=request.body,
                    headers=request.headers,
                )
        except httpx.TimeoutException as exc:
            raise RuntimeError("通知サーバーへの送信がタイムアウトしました。") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"通知サーバーに接続できません（{str(exc)[:120]}）") from exc
        if response.status_code >= 400:
            raise RuntimeError(f"通知サーバーがエラーを返しました（HTTP {response.status_code}）")

    def _cooldown_expired(self, key: str, now: float, cooldown_seconds: float) -> bool:
        last = self._cooldown.get(key)
        if last is None:
            return True
        if now - last >= cooldown_seconds:
            self._cooldown.pop(key, None)
            return True
        return False

    def _prune_cooldown(self, now: float) -> None:
        stale = [key for key, sent_at in self._cooldown.items() if now - sent_at > 86_400]
        for key in stale:
            self._cooldown.pop(key, None)

    async def notify(
        self,
        severity: str,
        category: str,
        title: str,
        detail: str,
        metadata: dict[str, Any] | None = None,
        force: bool = False,
    ) -> str:
        values = await self.database.notify_settings()
        if not values["enabled"] and not force:
            return "disabled"
        if not self._should_notify(values, severity, category):
            return "filtered"
        if not self._channel_configured(values):
            return "unconfigured"
        key = f"{category}:{title}"
        now = time.time()
        if not self._cooldown_expired(key, now, float(values["cooldown_minutes"]) * 60):
            return "cooldown"
        request = self._build_request(values, severity, category, title, detail)
        channel = self._channel_name(values)
        succeeded = False
        error_text = ""
        try:
            await self._send(request)
            succeeded = True
        except Exception as exc:  # Never break monitoring because of a failed delivery.
            logger.warning("notification %s failed: %s", channel, exc)
            error_text = str(exc)[:300]
        detail_text = "sent" if succeeded else f"failed: {error_text}"
        try:
            await self.database.add_notify_log(channel, detail_text, str(metadata or {}).strip()[:200])
        except Exception:
            logger.warning("failed to record notification log", exc_info=True)
        if succeeded:
            self._prune_cooldown(now)
            self._cooldown[key] = now
            return "sent"
        return "failed"

    async def test_notification(self) -> dict[str, Any]:
        values = await self.database.notify_settings()
        if not self._channel_configured(values):
            raise ValueError("ntfy（URLとトピック）またはWebhook URLを設定してください。")
        request = self._build_request(values, "info", "notification", "NetPulse test notification", "テストメッセージです。")
        channel = self._channel_name(values)
        try:
            await self._send(request)
        except RuntimeError as exc:
            await self.database.add_notify_log(channel, "failed", f"test: {exc}")
            raise
        await self.database.add_notify_log(channel, "sent", "test")
        return {"status": "sent", "channel": channel}

    async def log(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self.database.notify_log(limit)
