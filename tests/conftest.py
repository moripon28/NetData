"""Test-scoped environment overrides.

``create_app`` refuses to start when basic auth is required but not configured
(``WEB_AUTH_REQUIRED`` defaults to ``true`` in production). Most of the API test
suite exercises the unauthenticated surface, so pin the switch off for every
test; individual tests can opt back in with ``monkeypatch``.
"""
import pytest


@pytest.fixture(autouse=True)
def _web_auth_not_required_for_tests(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_REQUIRED", "false")
    monkeypatch.delenv("WEB_AUTH_USER", raising=False)
    monkeypatch.delenv("WEB_AUTH_PASSWORD", raising=False)
