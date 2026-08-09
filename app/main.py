from __future__ import annotations

import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings
from app.database import Database
from app.llm import LLMConnectionError, LLMReporter, ReportInProgressError
from app.service import MonitorService


STATIC_DIR = Path(__file__).parent / "static"
AGENT_DIR = Path(__file__).parent.parent / "agent"
AGENT_DOWNLOADS = {
    "install-windows.ps1": "text/plain; charset=utf-8",
    "install-linux.sh": "text/plain; charset=utf-8",
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
    uptime_seconds: int = Field(ge=0)
    rx_bps: float = Field(default=0, ge=0)
    tx_bps: float = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMSettingsUpdate(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=8_000)
    interval_minutes: int | None = Field(default=None, ge=15, le=10_080)
    lookback_minutes: int | None = Field(default=None, ge=15, le=43_200)
    api_key: str | None = Field(default=None, max_length=2_000)


class LLMModelsRequest(BaseModel):
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str | None = Field(default=None, max_length=2_000)


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


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    hub = WebSocketHub()
    database = Database(resolved.database_path)
    service = MonitorService(resolved, database, hub.broadcast)
    reporter = LLMReporter(resolved, database, service.snapshot)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await database.connect()
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

    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH"],
            allow_headers=["Content-Type"],
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok", "collector": "running" if service._running else "stopped",
            "latest_sample_at": service.latest.get("generated_at"), "websocket_clients": len(hub.clients),
            "connectivity": service.connectivity_latest.get("status"),
            "snmp": service.snmp_latest.get("status"),
            "llm_reporter": "running" if reporter._running else "stopped",
        }

    @app.get("/api/v1/snapshot")
    async def snapshot() -> dict[str, Any]:
        return await service.snapshot()

    @app.get("/api/v1/history")
    async def history(minutes: int = Query(60, ge=1, le=43_200)) -> dict[str, Any]:
        return {"minutes": minutes, "samples": await database.history(minutes)}

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

    @app.get("/api/v1/connectivity")
    async def connectivity(minutes: int = Query(60, ge=1, le=43_200)) -> dict[str, Any]:
        return {"current": service.connectivity_latest, "history": await database.connectivity_history(minutes)}

    @app.get("/api/v1/snmp")
    async def snmp(minutes: int = Query(60, ge=1, le=43_200)) -> dict[str, Any]:
        return {"current": service.snmp_latest, "history": await database.snmp_history(minutes)}

    @app.get("/api/v1/agents")
    async def agents() -> dict[str, Any]:
        items = await database.agents(resolved.agent_offline_after)
        return {
            "configured": bool(resolved.agent_token),
            "online": sum(item["status"] == "online" for item in items),
            "total": len(items),
            "items": items,
        }

    @app.post("/api/v1/agent/heartbeat")
    async def agent_heartbeat(request: Request) -> dict[str, Any]:
        if not resolved.agent_token:
            raise HTTPException(status_code=503, detail="Agent enrollment is not configured")
        timestamp_text = request.headers.get("x-agent-timestamp", "")
        signature = request.headers.get("x-agent-signature", "")
        try:
            timestamp = int(timestamp_text)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid agent timestamp") from exc
        if abs(time.time() - timestamp) > 90:
            raise HTTPException(status_code=401, detail="Expired agent request")
        body = await request.body()
        if len(body) > 65_536:
            raise HTTPException(status_code=413, detail="Agent payload is too large")
        expected = hmac.new(
            resolved.agent_token.encode("utf-8"), timestamp_text.encode("ascii") + b"." + body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid agent signature")
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
            "netpulse_agents_online": snap.get("agents", {}).get("online") or 0,
            "netpulse_active_anomalies": len(snap.get("insights", {}).get("active", [])),
            "netpulse_snmp_wan_receive_bytes_per_second": snap.get("snmp", {}).get("metrics", {}).get("wan_rx_bps") or 0,
            "netpulse_snmp_wan_transmit_bytes_per_second": snap.get("snmp", {}).get("metrics", {}).get("wan_tx_bps") or 0,
        }
        return "\n".join(f"# TYPE {name} gauge\n{name} {value}" for name, value in values.items()) + "\n"

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket) -> None:
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


app = create_app()
