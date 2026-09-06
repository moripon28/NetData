from __future__ import annotations

import base64
import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Path as PathParameter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings, validate_agent_token, validate_web_auth_configuration
from app.database import Database
from app.llm import LLMConnectionError, LLMReporter, ReportInProgressError
from app.notify import NotificationService
from app.service import MonitorService


STATIC_DIR = Path(__file__).parent / "static"
AGENT_DIR = Path(__file__).parent.parent / "agent"
AGENT_DOWNLOADS = {
    "install-windows.ps1": "text/plain; charset=utf-8",
    "install-linux.sh": "text/plain; charset=utf-8",
    "uninstall-windows.ps1": "text/plain; charset=utf-8",
    "uninstall-linux.sh": "text/plain; charset=utf-8",
    "netpulse_agent.py": "text/x-python; charset=utf-8",
    "requirements.txt": "text/plain; charset=utf-8",
}


class DeviceUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    device_type: str | None = Field(default=None, pattern="^(unknown|router|computer|phone|tablet|tv|iot|server|printer|camera|game)$")
    is_trusted: bool | None = None


class AgentHeartbeat(BaseModel):
    node_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    hostname: str = Field(min_length=1, max_length=255)
    os_name: str = Field(min_length=1, max_length=80)
    os_version: str = Field(default="", max_length=255)
    agent_version: str = Field(default="", max_length=32)
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    temperature_c: float | None = Field(default=None, ge=-50, le=200)
    load_1m: float | None = Field(default=None, ge=0)
    process_count: int | None = Field(default=None, ge=0)
    uptime_seconds: int = Field(ge=0)
    rx_bps: float = Field(default=0, ge=0)
    tx_bps: float = Field(default=0, ge=0)
    socket_count: int | None = Field(default=None, ge=0)
    established_socket_count: int | None = Field(default=None, ge=0)
    listening_socket_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMSettingsUpdate(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=8_000)
    interval_minutes: int | None = Field(default=None, ge=15, le=10_080)
    lookback_minutes: int | None = Field(default=None, ge=15, le=43_200)
    flavor_scope: Literal["last_3", "last_5", "last_10", "hours_24"] | None = None
    api_key: str | None = Field(default=None, max_length=2_000)


class LLMModelsRequest(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=2_000)


class NotifySettingsUpdate(BaseModel):
    enabled: bool | None = None
    server_url: str | None = Field(default=None, max_length=500)
    topic: str | None = Field(default=None, max_length=100)
    priority: int | None = Field(default=None, ge=1, le=5)
    webhook_url: str | None = Field(default=None, max_length=500)
    webhook_token: str | None = Field(default=None, max_length=2_000)
    cooldown_minutes: int | None = Field(default=None, ge=1, le=43_200)


class WebSocketHub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.clients.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        for client in tuple(self.clients):
            try:
                await client.send_json(payload)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            self.disconnect(client)


def build_basic_auth_checker(user: str, password: str):
    """Return a callable that validates an ``Authorization: Basic`` header.

    ``headers`` may be any mapping exposing ``.get`` (HTTP ``request.headers`` or a
    WebSocket's ``.headers``). The username and password are compared in constant
    time over UTF-8 bytes so a non-ASCII credential cannot raise and no timing
    side-channel leaks whether the user or the password was wrong.
    """
    user_bytes = user.encode("utf-8")
    password_bytes = password.encode("utf-8")

    def check(headers: Any) -> bool:
        raw = headers.get("authorization", "")
        scheme, _, payload = raw.partition(" ")
        if scheme.strip().lower() != "basic" or not payload.strip():
            return False
        try:
            decoded = base64.b64decode(payload.strip().encode("ascii"), validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, separator, candidate = decoded.partition(":")
        if not separator:
            return False
        return (
            hmac.compare_digest(username.encode("utf-8"), user_bytes)
            and hmac.compare_digest(candidate.encode("utf-8"), password_bytes)
        )

    return check


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    validate_agent_token(resolved.agent_token)
    validate_web_auth_configuration(resolved.web_auth_user, resolved.web_auth_password, resolved.web_auth_required)
    auth_enabled = bool(resolved.web_auth_user)
    check_basic = build_basic_auth_checker(resolved.web_auth_user, resolved.web_auth_password)
    hub = WebSocketHub()
    database = Database(resolved.database_path)
    notifier = NotificationService(resolved, database)
    service = MonitorService(resolved, database, hub.broadcast, notifier=notifier)
    reporter = LLMReporter(resolved, database, service.snapshot, notifier=notifier)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await database.connect()
        await notifier.initialize()
        await reporter.initialize()
        await service.start()
        await reporter.start()
        yield
        await reporter.stop()
        await service.stop()
        await database.close()

    app = FastAPI(title="NetPulse API", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.database = database
    app.state.monitor = service
    app.state.llm_reporter = reporter
    app.state.notifier = notifier

    if auth_enabled:
        exempt_paths = {"/api/health", "/api/v1/agent/heartbeat"}
        exempt_prefixes = ("/agent/",)

        @app.middleware("http")
        async def require_basic_auth(request: Request, call_next):
            path = request.url.path
            if (
                request.method != "OPTIONS"
                and path not in exempt_paths
                and not path.startswith(exempt_prefixes)
                and not check_basic(request.headers)
            ):
                return PlainTextResponse(
                    "authentication required",
                    status_code=401,
                    headers={
                        "WWW-Authenticate": 'Basic realm="netpulse"',
                        "Cache-Control": "no-store",
                    },
                )
            return await call_next(request)

    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type"],
        )

    @app.middleware("http")
    async def no_cache_for_ui(request: Request, call_next):
        response = await call_next(request)
        if (
            (request.url.path == "/" or request.url.path.startswith("/static/"))
            and "Cache-Control" not in response.headers
        ):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok", "collector": "running" if service._running else "stopped",
            "latest_sample_at": service.latest.get("generated_at"), "websocket_clients": len(hub.clients),
            "connectivity": service.connectivity_latest.get("status"),
            "snmp": service.snmp_latest.get("status"),
            "prometheus_exporters": service.exporters_latest.get("status"),
            "llm_reporter": "running" if reporter._running else "stopped",
        }

    @app.get("/api/v1/snapshot")
    async def snapshot() -> dict[str, Any]:
        return await service.snapshot()

    @app.get("/api/v1/history")
    async def history(minutes: int = Query(60, ge=1, le=43_200)) -> dict[str, Any]:
        return {"minutes": minutes, "samples": await database.history(minutes)}

    @app.get("/api/v1/traffic")
    async def traffic(
        minutes: int = Query(2, ge=1, le=1_440),
        points: int = Query(60, ge=20, le=300),
    ) -> dict[str, Any]:
        return await service.traffic_stream(minutes, points)

    @app.get("/api/v1/devices")
    async def devices() -> dict[str, Any]:
        items = await service.devices()
        return {"total": len(items), "items": items}

    @app.patch("/api/v1/devices/{ip}")
    async def update_device(ip: str, update: DeviceUpdate) -> dict[str, Any]:
        values = update.model_dump(exclude_unset=True)
        updated = await database.update_device(ip, values)
        if updated is None:
            raise HTTPException(status_code=404, detail="Device not found or no fields supplied")
        await database.add_event("info", "device", "Device details updated", f"Updated metadata for {ip}.", {"ip": ip})
        return updated

    @app.get("/api/v1/events")
    async def events(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        return {"items": await database.events(limit)}

    @app.get("/api/v1/llm/settings")
    async def llm_settings() -> dict[str, Any]:
        return await reporter.public_settings()

    @app.put("/api/v1/llm/settings")
    async def update_llm_settings(update: LLMSettingsUpdate) -> dict[str, Any]:
        values = update.model_dump(exclude_unset=True)
        if not values:
            raise HTTPException(status_code=400, detail="No settings to update")
        try:
            return await reporter.update_settings(values)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/llm/models")
    async def llm_models(request: LLMModelsRequest) -> dict[str, Any]:
        try:
            models = await reporter.list_models(request.base_url, request.api_key)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LLMConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"models": models}

    @app.get("/api/v1/llm/reports")
    async def llm_reports(limit: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
        items = await reporter.reports(limit)
        return {"total": len(items), "items": items, "running": reporter._run_lock.locked()}

    @app.get("/api/v1/llm/flavor-reports")
    async def llm_flavor_reports() -> dict[str, Any]:
        return await reporter.flavor_reports()

    @app.post("/api/v1/llm/reports/run")
    async def run_llm_report() -> dict[str, Any]:
        try:
            return await reporter.run_report("manual")
        except ReportInProgressError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LLMConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/v1/notify/settings")
    async def notify_settings() -> dict[str, Any]:
        return await notifier.public_settings()

    @app.put("/api/v1/notify/settings")
    async def update_notify_settings(update: NotifySettingsUpdate) -> dict[str, Any]:
        values = update.model_dump(exclude_unset=True)
        if not values:
            raise HTTPException(status_code=400, detail="No settings to update")
        try:
            return await notifier.update_settings(values)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/notify/test")
    async def test_notification() -> dict[str, Any]:
        try:
            return await notifier.test_notification()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/v1/notify/log")
    async def notify_log(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        return {"items": await notifier.log(limit)}

    @app.get("/api/v1/summary/daily")
    async def summary_daily(days: int = Query(7, ge=1, le=30)) -> dict[str, Any]:
        return await database.daily_traffic_summary(days, resolved.sample_interval)

    @app.get("/api/v1/summary/ranking")
    async def summary_ranking(
        hours: int = Query(24, ge=1, le=744), limit: int = Query(5, ge=1, le=20)
    ) -> dict[str, Any]:
        return await database.device_traffic_ranking(hours, limit, resolved.sample_interval)

    @app.get("/api/v1/connectivity")
    async def connectivity(minutes: int = Query(60, ge=1, le=43_200)) -> dict[str, Any]:
        return {"current": service.connectivity_latest, "history": await database.connectivity_history(minutes)}

    @app.get("/api/v1/snmp")
    async def snmp(minutes: int = Query(60, ge=1, le=43_200)) -> dict[str, Any]:
        return {"current": service.snmp_latest, "history": await database.snmp_history(minutes)}

    @app.get("/api/v1/agents")
    async def agents() -> dict[str, Any]:
        items = await service.agent_nodes()
        return {
            "configured": bool(resolved.agent_token),
            "online": sum(item["status"] == "online" for item in items),
            "total": len(items),
            "items": items,
        }

    @app.delete("/api/v1/agents/{node_id}")
    async def delete_agent(
        node_id: str = PathParameter(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    ) -> dict[str, Any]:
        deleted = await database.delete_agent(node_id)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Agent registration not found")
        live_snapshot = await service.snapshot()
        service.latest = live_snapshot
        await hub.broadcast(live_snapshot)
        return {"status": "deleted", **deleted}

    @app.get("/api/v1/exporters")
    async def exporters() -> dict[str, Any]:
        return await service.exporters()

    seen_agent_requests: dict[str, float] = {}

    @app.post("/api/v1/agent/heartbeat")
    async def agent_heartbeat(request: Request) -> dict[str, Any]:
        if not resolved.agent_token:
            raise HTTPException(status_code=503, detail="Agent enrollment is not configured")
        timestamp_text = request.headers.get("x-agent-timestamp", "")
        signature = request.headers.get("x-agent-signature", "")
        if not timestamp_text.isascii() or not timestamp_text.isdecimal():
            # int() also accepts Unicode decimal digits, which would break the
            # ASCII MAC below and surface as an unhandled 500.
            raise HTTPException(status_code=401, detail="Invalid agent timestamp")
        timestamp = int(timestamp_text, 10)
        if abs(time.time() - timestamp) > 60:
            raise HTTPException(status_code=401, detail="Expired agent request")
        body = await request.body()
        if len(body) > 65_536:
            raise HTTPException(status_code=413, detail="Agent payload is too large")
        expected = hmac.new(
            resolved.agent_token.encode("utf-8"), timestamp_text.encode("ascii") + b"." + body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature.encode("latin-1", "replace"), expected.encode("ascii")):
            raise HTTPException(status_code=401, detail="Invalid agent signature")
        # The timestamp window (60s) allows replaying a captured valid request,
        # so remember accepted (timestamp, payload) MACs for 2x the window.
        seen_key = hashlib.sha256(timestamp_text.encode("ascii") + b"." + body).hexdigest()
        now = time.time()
        if seen_key in seen_agent_requests:
            raise HTTPException(status_code=401, detail="Duplicate agent request")
        if len(seen_agent_requests) > 4096:
            for key in [k for k, expires in seen_agent_requests.items() if expires <= now]:
                seen_agent_requests.pop(key, None)
        seen_agent_requests[seen_key] = now + 120.0
        try:
            heartbeat = AgentHeartbeat.model_validate_json(body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid agent payload") from exc
        source_ip = request.client.host if request.client else "unknown"
        await database.upsert_agent(heartbeat.model_dump(), source_ip)
        return {"status": "accepted", "server_time": time.time()}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> str:
        snap = service.latest
        system = snap["system"]
        network = snap["network"]
        summary = snap["summary"]
        values = {
            "netpulse_cpu_percent": system.get("cpu_percent") or 0,
            "netpulse_memory_percent": system.get("memory_percent") or 0,
            "netpulse_temperature_celsius": system.get("temperature_c") or 0,
            "netpulse_network_receive_bytes_per_second": network.get("rx_bps") or 0,
            "netpulse_network_transmit_bytes_per_second": network.get("tx_bps") or 0,
            "netpulse_gateway_latency_milliseconds": network.get("gateway_latency_ms") or 0,
            "netpulse_devices_online": summary.get("online_devices") or 0,
            "netpulse_health_score": summary.get("health_score") or 0,
            "netpulse_dns_latency_milliseconds": snap.get("connectivity", {}).get("dns_latency_ms") or 0,
            "netpulse_internet_latency_milliseconds": snap.get("connectivity", {}).get("internet_latency_ms") or 0,
            "netpulse_connectivity_up": 1 if snap.get("connectivity", {}).get("status") == "online" else 0,
            "netpulse_lan_connectivity_up": 1 if snap.get("connectivity", {}).get("lan_status") == "online" else 0,
            "netpulse_agents_online": snap.get("agents", {}).get("online") or 0,
            "netpulse_active_anomalies": len(snap.get("insights", {}).get("active", [])),
            "netpulse_snmp_wan_receive_bytes_per_second": snap.get("snmp", {}).get("metrics", {}).get("wan_rx_bps") or 0,
            "netpulse_snmp_wan_transmit_bytes_per_second": snap.get("snmp", {}).get("metrics", {}).get("wan_tx_bps") or 0,
        }
        lines = [line for name, value in values.items() for line in (f"# TYPE {name} gauge", f"{name} {value}")]

        def labels(values: dict[str, Any]) -> str:
            escaped = []
            for key, value in values.items():
                text = str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
                escaped.append(f'{key}="{text}"')
            return "{" + ",".join(escaped) + "}"

        native_nodes = await service.agent_nodes()
        exporter_nodes = await service.exporter_nodes()
        all_nodes = [("agent", item) for item in native_nodes] + [("prometheus", item) for item in exporter_nodes]
        host_metrics = (
            ("netpulse_host_up", lambda item: 1 if item.get("status") == "online" else 0),
            ("netpulse_host_cpu_percent", lambda item: item.get("cpu_percent") or 0),
            ("netpulse_host_memory_percent", lambda item: item.get("memory_percent") or 0),
            ("netpulse_host_disk_percent", lambda item: item.get("disk_percent") or 0),
            ("netpulse_host_receive_bytes_per_second", lambda item: item.get("rx_bps") or 0),
            ("netpulse_host_transmit_bytes_per_second", lambda item: item.get("tx_bps") or 0),
            ("netpulse_host_uptime_seconds", lambda item: item.get("uptime_seconds") or 0),
        )
        for name, getter in host_metrics:
            lines.append(f"# TYPE {name} gauge")
            for source, item in all_nodes:
                lines.append(
                    f"{name}{labels({'node_id': item['node_id'], 'hostname': item['hostname'], 'source': source, 'os': item['os_name']})} {getter(item)}"
                )
        lines.append("# TYPE netpulse_prometheus_exporter_up gauge")
        for item in service.exporters_latest.get("items", []):
            lines.append(
                f"netpulse_prometheus_exporter_up{labels({'target': item['name'], 'kind': item.get('kind', 'unknown')})} "
                f"{1 if item.get('status') == 'online' else 0}"
            )
        qnap_details = [item for item in snap.get("snmp", {}).get("details", []) if item.get("profile") == "qnap"]
        qnap_system_metrics = (
            ("netpulse_qnap_cpu_percent", "cpu_percent"),
            ("netpulse_qnap_cpu_temperature_celsius", "cpu_temperature_celsius"),
            ("netpulse_qnap_system_temperature_celsius", "system_temperature_celsius"),
            ("netpulse_qnap_memory_total_bytes", "memory_total_bytes"),
            ("netpulse_qnap_memory_free_bytes", "memory_free_bytes"),
            ("netpulse_qnap_memory_available_bytes", "memory_available_bytes"),
            ("netpulse_qnap_memory_used_bytes", "memory_used_bytes"),
            ("netpulse_qnap_uptime_seconds", "uptime_seconds"),
        )
        lines.extend(("# TYPE netpulse_qnap_up gauge", "# TYPE netpulse_qnap_warning_count gauge"))
        for item in qnap_details:
            identity = item.get("identity", {})
            target_labels = labels(
                {"target": item.get("target", ""), "hostname": identity.get("hostname") or "", "model": identity.get("model") or ""}
            )
            lines.append(f"netpulse_qnap_up{target_labels} {1 if item.get('status') in {'online', 'degraded'} else 0}")
            lines.append(f"netpulse_qnap_warning_count{target_labels} {len(item.get('warnings', []))}")
        for metric_name, field in qnap_system_metrics:
            lines.append(f"# TYPE {metric_name} gauge")
            for item in qnap_details:
                raw = item.get("system", {}).get(field)
                if raw is not None:
                    lines.append(f"{metric_name}{labels({'target': item.get('target', '')})} {raw}")
        healthy_states = {"good", "ready", "normal", "ok", "active", "optimal"}
        for metric_name in (
            "netpulse_qnap_disk_temperature_celsius", "netpulse_qnap_disk_capacity_bytes", "netpulse_qnap_disk_status_ok",
        ):
            lines.append(f"# TYPE {metric_name} gauge")
        for item in qnap_details:
            for disk in item.get("disks", []):
                disk_labels = labels(
                    {
                        "target": item.get("target", ""), "disk_id": disk.get("id") or disk.get("index", ""),
                        "model": disk.get("model") or "", "type": disk.get("type") or "",
                    }
                )
                if disk.get("temperature_celsius") is not None:
                    lines.append(f"netpulse_qnap_disk_temperature_celsius{disk_labels} {disk['temperature_celsius']}")
                if disk.get("capacity_bytes") is not None:
                    lines.append(f"netpulse_qnap_disk_capacity_bytes{disk_labels} {disk['capacity_bytes']}")
                disk_ok = str(disk.get("status") or "").strip().lower() in healthy_states
                lines.append(f"netpulse_qnap_disk_status_ok{disk_labels} {1 if disk_ok else 0}")
        for kind, collection in (("raid", "raids"), ("pool", "storage_pools"), ("volume", "volumes")):
            for suffix in ("capacity_bytes", "free_bytes", "status_ok"):
                lines.append(f"# TYPE netpulse_qnap_{kind}_{suffix} gauge")
            for item in qnap_details:
                for storage in item.get(collection, []):
                    storage_labels = labels(
                        {"target": item.get("target", ""), f"{kind}_id": storage.get("id") or storage.get("index", "")}
                    )
                    if storage.get("capacity_bytes") is not None:
                        lines.append(f"netpulse_qnap_{kind}_capacity_bytes{storage_labels} {storage['capacity_bytes']}")
                    if storage.get("free_bytes") is not None:
                        lines.append(f"netpulse_qnap_{kind}_free_bytes{storage_labels} {storage['free_bytes']}")
                    status_ok = str(storage.get("status") or "").strip().lower() in healthy_states
                    lines.append(f"netpulse_qnap_{kind}_status_ok{storage_labels} {1 if status_ok else 0}")
        lines.extend(("# TYPE netpulse_probe_up gauge", "# TYPE netpulse_probe_latency_milliseconds gauge"))
        for item in snap.get("connectivity", {}).get("checks", []):
            probe_labels = labels({"target": item.get("target", ""), "type": item.get("check_type", "unknown")})
            lines.append(f"netpulse_probe_up{probe_labels} {1 if item.get('success') else 0}")
            if item.get("latency_ms") is not None:
                lines.append(f"netpulse_probe_latency_milliseconds{probe_labels} {item['latency_ms']}")
        lines.append("# TYPE netpulse_device_up gauge")
        for item in await service.devices():
            lines.append(
                f"netpulse_device_up{labels({'ip': item['ip'], 'hostname': item.get('hostname') or '', 'type': item.get('device_type') or 'unknown'})} "
                f"{1 if item.get('status') == 'online' else 0}"
            )
        return "\n".join(lines) + "\n"

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket) -> None:
        # Browsers cannot send an Authorization header on a WebSocket, so a
        # rejected handshake answers the upgrade request with 403 before accept.
        if auth_enabled and not check_basic(websocket.headers):
            await websocket.close(code=1008, reason="authentication required")
            return
        await hub.connect(websocket)
        await websocket.send_json(await service.snapshot())
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            hub.disconnect(websocket)

    @app.get("/agent/{filename}", include_in_schema=False)
    async def download_agent_file(filename: str) -> FileResponse:
        media_type = AGENT_DOWNLOADS.get(filename)
        path = AGENT_DIR / filename
        if media_type is None or not path.is_file():
            raise HTTPException(status_code=404, detail="Agent download not found")
        return FileResponse(
            path,
            media_type=media_type,
            headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"},
        )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app
