from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import socket
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import re

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.config import DEFAULT_LLM_SYSTEM_PROMPT, Settings
from app.database import Database


logger = logging.getLogger(__name__)

# Small Gemma E2B-class models served by Ollama can, under low-temperature
# sampling, fall into a loop that emits reserved placeholder tokens
# ("<unused49>", "<unused50>", ...) instead of readable text. Detect such
# collapsed output so it can be retried / surfaced clearly.
_UNUSED_TOKEN_RE = re.compile(r"<unused[0-9]+>")


def _is_degenerated(content: str) -> bool:
    if not content or "unused" not in content:
        return False
    total = sum(len(token) for token in _UNUSED_TOKEN_RE.findall(content))
    return total / max(len(content), 1) > 0.2


SnapshotProvider = Callable[[], Awaitable[dict[str, Any]]]
LLM_FLAVOR_SCOPES = {
    "last_3": "直近3回分",
    "last_5": "直近5回分",
    "last_10": "直近10回分",
    "hours_24": "直近24時間分",
}


class LLMConnectionError(RuntimeError):
    pass


class ReportInProgressError(RuntimeError):
    pass


_V6_LOCAL_NETWORKS = (ipaddress.ip_network("fc00::/7"),)  # unique-local (LAN)


def _is_local_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Loopback and RFC1918/ULA (LAN) addresses only.

    Link-local (e.g. 169.254.169.254 cloud metadata) is deliberately excluded
    so the LLM client cannot be used for SSRF. IPv6 embedding formats
    (v4-mapped, 6to4, Teredo) are judged by their embedded IPv4 address because
    Python 3.10's ipaddress.is_private wrongly reports several of them as
    private (e.g. ::ffff:169.254.169.254, Teredo 2001::/32).
    """
    if isinstance(address, ipaddress.IPv6Address):
        if address.is_loopback:
            return True
        if address.ipv4_mapped is not None:
            return _is_local_address(address.ipv4_mapped)
        sixtofour = getattr(address, "sixtofour", None)
        if sixtofour is not None:
            return _is_local_address(sixtofour)
        teredo = getattr(address, "teredo", None)
        if teredo is not None:
            teredo_server, teredo_client = teredo
            return _is_local_address(teredo_server) and _is_local_address(teredo_client)
        return any(address in network for network in _V6_LOCAL_NETWORKS)
    return (address.is_private or address.is_loopback) and not address.is_link_local


def _is_local_target(hostname: str) -> bool:
    try:
        addresses = {ipaddress.ip_address(hostname)}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            }
        except socket.gaierror:
            return False
    if not addresses:
        return False
    return all(_is_local_address(address) for address in addresses)


class LocalOnlyTransport(httpx.AsyncBaseTransport):
    """Enforces the local-only policy at connect time and pins the resolved
    address, so a DNS answer that changes between validation and connection
    (DNS rebinding) cannot redirect the request to a non-local target."""

    def __init__(self, allow_external: bool, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._allow_external = allow_external
        self._inner = inner or httpx.AsyncHTTPTransport(trust_env=False)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if not self._allow_external and request.url.host:
            loop = asyncio.get_running_loop()
            try:
                infos = await loop.getaddrinfo(request.url.host, None, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise LLMConnectionError(
                    "LLMサーバーに接続できません。Base URLとサーバー状態を確認してください。"
                ) from exc
            addresses = [ipaddress.ip_address(item[4][0]) for item in infos]
            if not addresses or not all(_is_local_address(address) for address in addresses):
                raise LLMConnectionError(
                    "Base URLはローカルネットワーク内のアドレスにしてください。"
                )
            # Pin the validated address: connect to it directly so a later
            # DNS answer cannot change the destination. The pre-built request
            # keeps its original Host header for virtual-hosted servers.
            request.url = request.url.copy_with(host=str(addresses[0]))
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class SecretCipher:
    """Keep the optional LLM credential encrypted in SQLite with a local data-volume key."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path
        self._cipher: Fernet | None = None

    def _get_cipher(self) -> Fernet:
        if self._cipher is not None:
            return self._cipher
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            key = self.key_path.read_bytes().strip()
        except FileNotFoundError:
            key = Fernet.generate_key()
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            try:
                descriptor = os.open(self.key_path, flags, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(key + b"\n")
            except FileExistsError:
                key = self.key_path.read_bytes().strip()
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        try:
            self._cipher = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("The local LLM settings encryption key is invalid") from exc
        return self._cipher

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return self._get_cipher().encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self._get_cipher().decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise RuntimeError("The saved LLM API key could not be decrypted") from exc


class LocalLLMClient:
    def __init__(self, timeout_seconds: int = 120, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _transport_for(self, allow_external: bool) -> httpx.AsyncBaseTransport:
        return LocalOnlyTransport(allow_external, inner=self.transport)

    @staticmethod
    def normalize_base_url(base_url: str, allow_external: bool = False) -> str:
        normalized = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Base URLには有効なhttpまたはhttpsのURLを指定してください。")
        if not allow_external and not _is_local_target(parsed.hostname):
            raise ValueError(
                "Base URLはローカルネットワーク内のアドレスにしてください。"
                "外部APIを使用する場合はLLM_ALLOW_EXTERNAL=trueを有効にしてください。"
            )
        return normalized

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def list_models(self, base_url: str, api_key: str = "", allow_external: bool = False) -> list[dict[str, str]]:
        normalized = self.normalize_base_url(base_url, allow_external)
        try:
            async with httpx.AsyncClient(
                timeout=10.0, trust_env=False, transport=self._transport_for(allow_external)
            ) as client:
                response = await client.get(f"{normalized}/models", headers=self._headers(api_key))
                response.raise_for_status()
                models = parse_models(response.json())

                parsed = urlsplit(normalized)
                if parsed.path.rstrip("/") == "/v1" and any("type" not in model for model in models):
                    native_url = urlunsplit((parsed.scheme, parsed.netloc, "/api/v1/models", "", ""))
                    try:
                        native_response = await client.get(native_url, headers=self._headers(api_key), timeout=3.0)
                        native_response.raise_for_status()
                        native_models = parse_models(native_response.json())
                        if native_models:
                            models = native_models
                    except (httpx.HTTPError, TypeError, ValueError):
                        pass
        except httpx.TimeoutException as exc:
            raise LLMConnectionError("LLMサーバーからのモデル一覧取得がタイムアウトしました。") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMConnectionError(
                f"LLMサーバーからモデル一覧を取得できませんでした（HTTP {exc.response.status_code}）。"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError("LLMサーバーに接続できません。Base URLとサーバー状態を確認してください。") from exc
        except (TypeError, ValueError) as exc:
            raise LLMConnectionError("LLMサーバーのモデル一覧レスポンスを解釈できません。") from exc
        return models

    async def create_report(
        self,
        base_url: str,
        model: str,
        api_key: str,
        context: dict[str, Any],
        system_prompt: str = DEFAULT_LLM_SYSTEM_PROMPT,
        allow_external: bool = False,
    ) -> str:
        normalized = self.normalize_base_url(base_url, allow_external)
        user_content = (
            "次のNetPulse集計を分析し、内部の検討過程を含めず日本語の最終報告だけを返してください。\n"
            + json.dumps(context, ensure_ascii=False)
            + "\n\n【最重要】出力はすべて日本語で記述すること。英語を一切使用しないこと。"
            + "\n出力が同じ記号や繰り返しトークンだけになる場合は、必ず別の表現で日本語の本文を返すこと。"
        )
        # Low-temperature sampling can drive small Gemma E2B-class models into
        # a repetition loop of reserved placeholder tokens. Start moderate
        # with a frequency penalty and escalate temperature + penalty on each
        # retry so the sampler can escape the loop. HTTP and network errors
        # are raised immediately (retrying them would only waste time).
        attempts = (
            {"temperature": 0.5, "frequency_penalty": 0.7},
            {"temperature": 0.8, "frequency_penalty": 1.0},
            {"temperature": 1.1, "frequency_penalty": 1.2},
        )
        for sampling in attempts:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": 2000,
                "reasoning_effort": "none",
                **sampling,
            }
            content = await self._request_chat(normalized, api_key, payload, allow_external)
            if not _is_degenerated(content):
                return content[:50_000]
            logger.warning(
                "LLM report degenerated into placeholder-token loop (temperature=%s); retrying",
                sampling["temperature"],
            )
        raise LLMConnectionError(
            "LLMの応答が繰り返しトークンに収束し、日本語の報告本文として保存できませんでした。"
            "温度やfrequency_penaltyを調整するか、9Bクラスのモデルを使うことを推奨します。"
        )

    async def _request_chat(
        self,
        normalized: str,
        api_key: str,
        payload: dict[str, Any],
        allow_external: bool,
    ) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                trust_env=False,
                transport=self._transport_for(allow_external),
            ) as client:
                response = await client.post(
                    f"{normalized}/chat/completions", headers=self._headers(api_key), json=payload
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMConnectionError("LLM分析がタイムアウトしました。") from exc
        except httpx.HTTPStatusError as exc:
            detail = _response_error_detail(exc.response)
            suffix = f": {detail}" if detail else ""
            raise LLMConnectionError(f"LLM分析に失敗しました（HTTP {exc.response.status_code}）{suffix}") from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError("LLMサーバーに接続できません。") from exc
        except (TypeError, ValueError) as exc:
            raise LLMConnectionError("LLMの応答を解釈できません。") from exc

        try:
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMConnectionError("LLMの応答に報告本文がありません。") from exc
        if isinstance(content, list):
            content = "\n".join(
                str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("text")
            )
        if not isinstance(content, str) or not content.strip():
            raise LLMConnectionError("LLMの応答に報告本文がありません。")
        return content.strip()


class LLMReporter:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        snapshot_provider: SnapshotProvider,
        client: LocalLLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.snapshot_provider = snapshot_provider
        self.client = client or LocalLLMClient(settings.llm_request_timeout)
        self.cipher = SecretCipher(settings.data_dir / ".llm-settings.key")
        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._run_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await self.database.ensure_llm_settings(
            {
                "enabled": self.settings.llm_report_enabled,
                "base_url": self.settings.llm_base_url,
                "model": self.settings.llm_model,
                "system_prompt": self.settings.llm_system_prompt,
                "interval_minutes": self.settings.llm_report_interval,
                "lookback_minutes": self.settings.llm_report_lookback,
                "flavor_scope": "last_3",
                "api_key_encrypted": self.cipher.encrypt(self.settings.llm_api_key),
            }
        )
        values = await self.database.llm_settings()
        if not values.get("system_prompt", "").strip():
            await self.database.update_llm_settings({"system_prompt": self.settings.llm_system_prompt})
        if values.get("base_url"):
            try:
                self.client.normalize_base_url(values["base_url"], self.settings.llm_allow_external)
            except ValueError as exc:
                # Never block app startup on the optional LLM feature; report the problem instead.
                logger.warning("LLM Base URL is invalid: %s", exc)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._schedule_loop(), name="llm-network-reporter")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def public_settings(self) -> dict[str, Any]:
        values = await self.database.llm_settings()
        return {
            "enabled": values["enabled"],
            "base_url": values["base_url"],
            "model": values["model"],
            "system_prompt": values["system_prompt"],
            "interval_minutes": values["interval_minutes"],
            "lookback_minutes": values["lookback_minutes"],
            "flavor_scope": values["flavor_scope"],
            "api_key_configured": bool(values["api_key_encrypted"]),
            "updated_at": values["updated_at"],
            "running": self._run_lock.locked(),
        }

    async def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(updates)
        current = await self.database.llm_settings()
        if "base_url" in normalized:
            normalized["base_url"] = self.client.normalize_base_url(
                str(normalized["base_url"]), self.settings.llm_allow_external
            )
            if normalized["base_url"] != current["base_url"] and "api_key" not in normalized:
                # A credential belongs to one endpoint. Moving to another host
                # without entering a new key must not forward the old secret.
                normalized["api_key_encrypted"] = ""
        if "model" in normalized:
            normalized["model"] = str(normalized["model"]).strip()
        if "system_prompt" in normalized:
            normalized["system_prompt"] = str(normalized["system_prompt"]).strip()
            if not normalized["system_prompt"]:
                raise ValueError("システムプロンプトを入力してください。")
        if "flavor_scope" in normalized and normalized["flavor_scope"] not in LLM_FLAVOR_SCOPES:
            raise ValueError("表示するLLM報告の範囲が不正です。")
        if "api_key" in normalized:
            normalized["api_key_encrypted"] = self.cipher.encrypt(str(normalized.pop("api_key")).strip())
        await self.database.update_llm_settings(normalized)
        return await self.public_settings()

    async def list_models(self, base_url: str, api_key: str | None = None) -> list[dict[str, str]]:
        saved = await self.database.llm_settings()
        normalized = self.client.normalize_base_url(base_url, self.settings.llm_allow_external)
        saved_url = ""
        if saved["base_url"]:
            try:
                saved_url = self.client.normalize_base_url(saved["base_url"], self.settings.llm_allow_external)
            except ValueError:
                # The endpoint the key belongs to is no longer permitted (e.g.
                # LLM_ALLOW_EXTERNAL was disabled); never match it again.
                saved_url = ""
        # Never forward a persisted credential to a caller-supplied endpoint.
        # The saved key is reusable only for the exact endpoint it was saved with.
        credential = api_key.strip() if api_key is not None else (
            self.cipher.decrypt(saved["api_key_encrypted"]) if normalized == saved_url else ""
        )
        return await self.client.list_models(normalized, credential, allow_external=self.settings.llm_allow_external)

    async def reports(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self.database.llm_reports(limit)

    async def flavor_reports(self) -> dict[str, Any]:
        values = await self.database.llm_settings()
        scope = values.get("flavor_scope", "last_3")
        if scope not in LLM_FLAVOR_SCOPES:
            scope = "last_3"
        items = await self.database.llm_flavor_reports(scope)
        return {"scope": scope, "label": LLM_FLAVOR_SCOPES[scope], "items": items}

    async def run_report(self, trigger: str = "manual") -> dict[str, Any]:
        if self._run_lock.locked():
            raise ReportInProgressError("LLM分析はすでに実行中です。")
        async with self._run_lock:
            values = await self.database.llm_settings()
            if not values["base_url"] or not values["model"]:
                raise ValueError("Base URLとモデルを設定してください。")
            period_end = time.time()
            period_start = period_end - int(values["lookback_minutes"]) * 60
            context = await self._analysis_context(int(values["lookback_minutes"]), trigger)
            sample_count = int(context["samples"].get("sample_count") or 0)
            if sample_count == 0:
                raise ValueError("分析対象期間に監視サンプルがありません。")
            try:
                content = await self.client.create_report(
                    values["base_url"], values["model"], self.cipher.decrypt(values["api_key_encrypted"]),
                    context, values["system_prompt"], allow_external=self.settings.llm_allow_external,
                )
            except Exception as exc:
                error = str(exc)[:500]
                report = await self.database.save_llm_report(
                    period_start=period_start,
                    period_end=period_end,
                    model=values["model"],
                    status="error",
                    error=error,
                    context={"trigger": trigger, "sample_count": sample_count},
                )
                await self.database.add_event("warning", "llm", "LLM report failed", error)
                raise
            report = await self.database.save_llm_report(
                period_start=period_start,
                period_end=period_end,
                model=values["model"],
                status="completed",
                content=content,
                context={"trigger": trigger, "sample_count": sample_count},
            )
            await self.database.add_event(
                "success", "llm", "Network report generated", f"Analyzed {sample_count} samples with {values['model']}.",
            )
            return report

    async def _analysis_context(self, lookback_minutes: int, trigger: str) -> dict[str, Any]:
        now = time.time()
        snapshot, samples, connectivity, snmp, events, devices, agents = await asyncio.gather(
            self.snapshot_provider(),
            self.database.sample_statistics(lookback_minutes),
            self.database.connectivity_statistics(lookback_minutes),
            self.database.snmp_statistics(lookback_minutes),
            self.database.events_since(now - lookback_minutes * 60, 40),
            self.database.devices(),
            self.database.agents(self.settings.agent_offline_after),
        )
        device_items = [
            {
                "ip": item["ip"],
                "name": item.get("display_name") or item.get("hostname") or item["ip"],
                "type": item.get("device_type"),
                "status": item.get("status"),
                "trusted": bool(item.get("is_trusted")),
                "last_seen": item.get("last_seen"),
            }
            for item in devices[:100]
        ]
        agent_items = [
            {
                "hostname": item["hostname"], "os": item["os_name"], "status": item["status"],
                "cpu_percent": item["cpu_percent"], "memory_percent": item["memory_percent"],
                "disk_percent": item["disk_percent"], "last_seen": item["last_seen"],
            }
            for item in agents[:100]
        ]
        return {
            "generated_at": now,
            "trigger": trigger,
            "lookback_minutes": lookback_minutes,
            "samples": _rounded_numbers(samples),
            "connectivity": _rounded_numbers(connectivity),
            "snmp_history": _rounded_numbers(snmp),
            "current": {
                "system": snapshot.get("system", {}),
                "network": snapshot.get("network", {}),
                "summary": snapshot.get("summary", {}),
                "connectivity": snapshot.get("connectivity", {}),
                "snmp": snapshot.get("snmp", {}),
                "anomaly": snapshot.get("insights", {}),
            },
            "devices": device_items,
            "agents": agent_items,
            "events": [
                {
                    "ts": event["ts"], "severity": event["severity"], "category": event["category"],
                    "title": event["title"], "detail": event["detail"],
                }
                for event in events
            ],
        }

    async def _schedule_loop(self) -> None:
        await asyncio.sleep(5)
        while self._running:
            try:
                values = await self.database.llm_settings()
                last_report_at = await self.database.last_llm_report_at()
                due = last_report_at is None or time.time() - last_report_at >= int(values["interval_minutes"]) * 60
                if values["enabled"] and values["model"] and due:
                    await self.run_report("scheduled")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(30)


def parse_models(payload: object) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        raise ValueError("Model response must be an object")
    items = payload.get("data")
    if not isinstance(items, list):
        items = payload.get("models")
    if not isinstance(items, list):
        raise ValueError("Model response does not contain a model list")
    models: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items[:500]:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("key")
        if not isinstance(model_id, str) or not model_id.strip() or model_id.strip() in seen:
            continue
        model_type = item.get("type")
        if isinstance(model_type, str) and model_type.lower() in {"embedding", "embeddings"}:
            continue
        model = {"id": model_id.strip()}
        for field_name in ("display_name", "type", "state", "owned_by"):
            value = item.get(field_name)
            if isinstance(value, str) and value.strip():
                model[field_name] = value.strip()
        seen.add(model["id"])
        models.append(model)
    return sorted(models, key=lambda item: item["id"].casefold())


def _response_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", payload) if isinstance(payload, dict) else {}
        detail = error.get("message") if isinstance(error, dict) else ""
        return str(detail)[:300] if detail else ""
    except (TypeError, ValueError):
        return ""


def _rounded_numbers(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {key: _rounded_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded_numbers(item) for item in value]
    return value
