from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.database import Database
from app.notify import NotificationService, validate_ntfy_server_url, validate_webhook_url


DEFAULTS = {
    "enabled": False,
    "server_url": "",
    "topic": "",
    "priority": 3,
    "webhook_url": "",
    "webhook_token_encrypted": "",
    "cooldown_minutes": 15,
}


@pytest.fixture
async def database(tmp_path):
    db = Database(tmp_path / "netpulse.db")
    await db.connect()
    yield db
    await db.close()


async def _seed(database, **overrides):
    """Create the notify_settings row; ``ensure`` only inserts when absent."""
    values = dict(DEFAULTS)
    values.update(overrides)
    await database.ensure_notify_settings(values)
    return await database.notify_settings()


def _service(settings, database, transport=None):
    return NotificationService(settings, database, transport=transport)


def _mock(handler):
    seen: list[httpx.Request] = []

    async def _inner(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(_inner), seen


def test_ntfy_url_validation_rejects_external_by_default():
    with pytest.raises(ValueError, match="NOTIFY_ALLOW_EXTERNAL"):
        validate_ntfy_server_url("https://ntfy.sh", allow_external=False)
    assert validate_ntfy_server_url("http://192.168.10.5:23710", allow_external=False) == "http://192.168.10.5:23710"
    assert validate_ntfy_server_url("https://ntfy.sh", allow_external=True) == "https://ntfy.sh"


def test_ntfy_rejects_credentials_and_query_and_fragment():
    for bad in (
        "http://user:pass@192.168.10.5:23710",
        "http://192.168.10.5:23710/?x=1",
        "http://192.168.10.5:23710#topic",
        "ftp://192.168.10.5:23710",
    ):
        with pytest.raises(ValueError):
            validate_ntfy_server_url(bad, allow_external=True)
    # Webhook allows query strings.
    assert validate_webhook_url("http://192.168.10.5/hook?token=abc", allow_external=False) == "http://192.168.10.5/hook?token=abc"


@pytest.mark.asyncio
async def test_settings_crud_roundtrip_and_token_hidden(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    service = _service(settings, database)
    await _seed(database, enabled=False)
    public = await service.update_settings(
        {
            "enabled": True,
            "server_url": "http://192.168.10.5:23710",
            "topic": "netpulse",
            "priority": 4,
            "cooldown_minutes": 5,
            "webhook_token": "secret-token",
        }
    )
    assert public["enabled"] is True
    assert public["server_url"] == "http://192.168.10.5:23710"
    assert public["topic"] == "netpulse"
    assert public["priority"] == 4
    assert public["cooldown_minutes"] == 5
    assert public["webhook_token_configured"] is True
    assert "secret-token" not in json.dumps(public)

    raw = await database.notify_settings()
    assert service.cipher.decrypt(raw["webhook_token_encrypted"]) == "secret-token"

    cleared = await service.update_settings({"webhook_token": ""})
    assert cleared["webhook_token_configured"] is False


@pytest.mark.asyncio
async def test_ntfy_send_headers_and_cooldown(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False, notify_timeout=3.0)
    transport, seen = _mock(lambda request: httpx.Response(200, text="ok"))
    service = _service(settings, database, transport=transport)
    await _seed(
        database,
        enabled=True,
        server_url="http://192.168.10.5:23710",
        topic="netpulse",
        priority=5,
        cooldown_minutes=15,
    )

    first = await service.notify("error", "device", "Device offline", "192.168.10.50")
    assert first == "sent"
    assert len(seen) == 1
    request = seen[0]
    assert str(request.url) == "http://192.168.10.5:23710/netpulse"
    assert request.headers["Title"] == "Device offline"
    assert request.headers["Priority"] == "5"
    assert "rotating_light" in request.headers["Tags"]
    assert b"[error] device: Device offline" in request.content

    # Same title/category inside the cooldown window is suppressed.
    second = await service.notify("error", "device", "Device offline", "192.168.10.50")
    assert second == "cooldown"
    assert len(seen) == 1

    # A different title still goes through.
    third = await service.notify("warning", "device", "Unknown device", "192.168.10.99")
    assert third == "sent"
    assert len(seen) == 2

    log = await service.log()
    assert log[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_severity_filtering_info_suppressed_outside_device(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    transport, seen = _mock(lambda request: httpx.Response(200, text="ok"))
    service = _service(settings, database, transport=transport)
    await _seed(database, enabled=True, server_url="http://192.168.10.5:23710", topic="netpulse")

    # info + non-device category is filtered, even with a valid channel.
    assert await service.notify("info", "connectivity", "All good", "ok") == "filtered"
    # info + device is delivered.
    assert await service.notify("info", "device", "New device", "192.168.10.5") == "sent"
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_disabled_short_circuits_before_channel_check(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    service = _service(settings, database, transport=_mock(lambda r: httpx.Response(200))[0])
    await _seed(database, enabled=False, server_url="http://192.168.10.5:23710", topic="netpulse")
    assert await service.notify("error", "device", "x", "y") == "disabled"


@pytest.mark.asyncio
async def test_enabled_but_unconfigured_returns_unconfigured(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    service = _service(settings, database, transport=_mock(lambda r: httpx.Response(200))[0])
    await _seed(database, enabled=True, server_url="", topic="", webhook_url="")
    assert await service.notify("error", "device", "x", "y") == "unconfigured"


@pytest.mark.asyncio
async def test_webhook_send_uses_bearer_token(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    transport, seen = _mock(lambda request: httpx.Response(200, text="ok"))
    service = _service(settings, database, transport=transport)
    await _seed(
        database,
        enabled=True,
        webhook_url="http://192.168.10.70/hook",
        webhook_token_encrypted=service.cipher.encrypt("wh-secret"),
    )
    assert await service.notify("warning", "anomaly", "Traffic spike", "1GB") == "sent"
    request = seen[0]
    assert str(request.url) == "http://192.168.10.70/hook"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Authorization"] == "Bearer wh-secret"
    payload = json.loads(request.content)
    assert payload["source"] == "netpulse"
    assert payload["severity"] == "warning"


@pytest.mark.asyncio
async def test_send_failure_returns_failed_and_is_logged(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    transport, _seen = _mock(lambda request: httpx.Response(500, text="boom"))
    service = _service(settings, database, transport=transport)
    await _seed(database, enabled=True, server_url="http://192.168.10.5:23710", topic="netpulse")
    # Failure must not raise and must not trigger cooldown.
    assert await service.notify("error", "device", "x", "y") == "failed"
    log = await service.log()
    assert log[0]["status"].startswith("failed")
    # Because delivery failed, cooldown was not applied; a retry is still attempted.
    assert await service.notify("error", "device", "x", "y") in {"failed", "sent"}


@pytest.mark.asyncio
async def test_test_notification_requires_channel(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    service = _service(settings, database, transport=_mock(lambda r: httpx.Response(200))[0])
    await _seed(database, enabled=True, server_url="", topic="", webhook_url="")
    with pytest.raises(ValueError):
        await service.test_notification()


@pytest.mark.asyncio
async def test_test_notification_sends(tmp_path, database):
    settings = Settings(data_dir=tmp_path, collector_enabled=False, discovery_enabled=False)
    transport, seen = _mock(lambda request: httpx.Response(200, text="ok"))
    service = _service(settings, database, transport=transport)
    await _seed(database, enabled=False, server_url="http://192.168.10.5:23710", topic="netpulse")
    result = await service.test_notification()
    assert result["status"] == "sent"
    assert result["channel"] == "ntfy"
    assert len(seen) == 1
