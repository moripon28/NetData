from __future__ import annotations

import pytest

from app.service import MonitorService


class _BrokenDatabase:
    async def add_event(self, *args, **kwargs):
        raise OSError("disk full")


class _BrokenNotifier:
    async def notify(self, *args, **kwargs):
        raise RuntimeError("webhook down")


def _service(database, notifier=None) -> MonitorService:
    service = MonitorService.__new__(MonitorService)
    service.database = database
    service.notifier = notifier
    return service


async def test_record_event_swallows_database_failure():
    service = _service(_BrokenDatabase())
    await service._record_event("error", "collector", "Collection failed", "boom")


async def test_record_event_skips_notifier_when_database_fails():
    service = _service(_BrokenDatabase(), notifier=_BrokenNotifier())
    await service._record_event("warning", "device", "Device went offline", "gone")


async def test_record_event_still_reports_notifier_failure(tmp_path):
    from app.database import Database

    database = Database(tmp_path / "netpulse.db")
    await database.connect()
    try:
        service = _service(database, notifier=_BrokenNotifier())
        await service._record_event("info", "test", "Stored but delivery failed", "ok")
        events = await database.events()
        assert events, "event should be persisted when only the notifier fails"
    finally:
        await database.close()
