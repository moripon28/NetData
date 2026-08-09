from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.config import DEFAULT_LLM_SYSTEM_PROMPT, Settings
from app.database import Database


SnapshotProvider = Callable[[], Awaitable[dict[str, Any]]]


class LLMConnectionError(RuntimeError):
    pass


class ReportInProgressError(RuntimeError):
    pass


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

    @staticmethod
    def normalize_base_url(base_url: str) -> str:
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
        return normalized

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def list_models(self, base_url: str, api_key: str = "") -> list[dict[str, str]]:
        normalized = self.normalize_base_url(base_url)
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False, transport=self.transport) as client:
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
    ) -> str:
        normalized = self.normalize_base_url(base_url)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "次のNetPulse集計を分析し、内部の検討過程を含めず日本語の最終報告だけを返してください。\n"
                    + json.dumps(context, ensure_ascii=False),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 2000,
            "reasoning_effort": "none",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, trust_env=False, transport=self.transport
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
        return content.strip()[:50_000]


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
                "api_key_encrypted": self.cipher.encrypt(self.settings.llm_api_key),
            }
        )
        values = await self.database.llm_settings()
        if not values.get("system_prompt", "").strip():
            await self.database.update_llm_settings({"system_prompt": self.settings.llm_system_prompt})

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
            "api_key_configured": bool(values["api_key_encrypted"]),
            "updated_at": values["updated_at"],
            "running": self._run_lock.locked(),
        }

    async def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(updates)
        current = await self.database.llm_settings()
        if "base_url" in normalized:
            normalized["base_url"] = self.client.normalize_base_url(str(normalized["base_url"]))
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
        if "api_key" in normalized:
            normalized["api_key_encrypted"] = self.cipher.encrypt(str(normalized.pop("api_key")).strip())
        await self.database.update_llm_settings(normalized)
        return await self.public_settings()

    async def list_models(self, base_url: str, api_key: str | None = None) -> list[dict[str, str]]:
        saved = await self.database.llm_settings()
        normalized = self.client.normalize_base_url(base_url)
        saved_url = self.client.normalize_base_url(saved["base_url"]) if saved["base_url"] else ""
        # Never forward a persisted credential to a caller-supplied endpoint.
        # The saved key is reusable only for the exact endpoint it was saved with.
        credential = api_key.strip() if api_key is not None else (
            self.cipher.decrypt(saved["api_key_encrypted"]) if normalized == saved_url else ""
        )
        return await self.client.list_models(normalized, credential)

    async def reports(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self.database.llm_reports(limit)

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
                    context, values["system_prompt"],
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
