import ipaddress
import json

import httpx
import pytest

from app.llm import LLMConnectionError, LocalLLMClient, parse_models


def test_parse_models_supports_openai_and_filters_embeddings():
    models = parse_models(
        {
            "data": [
                {"id": "z-chat", "owned_by": "local"},
                {"id": "embedding", "type": "embedding"},
                {"id": "a-chat"},
                {"id": "a-chat"},
            ]
        }
    )
    assert [model["id"] for model in models] == ["a-chat", "z-chat"]


def test_parse_models_supports_lm_studio_native_shape():
    models = parse_models(
        {"models": [{"key": "chat", "display_name": "Chat", "type": "llm"}]}
    )
    assert models == [{"id": "chat", "display_name": "Chat", "type": "llm"}]


def test_base_url_validation_rejects_credentials_query_and_non_http():
    for value in (
        "ftp://192.168.10.20/v1",
        "http://user:secret@192.168.10.20:1234/v1",
        "http://192.168.10.20:1234/v1?token=secret",
    ):
        try:
            LocalLLMClient.normalize_base_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected invalid Base URL: {value}")


def test_base_url_validation_rejects_external_addresses_by_default():
    for value in (
        "http://api.openai.com/v1",
        "https://example.com:8443/v1",
        "http://8.8.8.8:1234/v1",
        "http://169.254.169.254/latest/meta-data/",
    ):
        try:
            LocalLLMClient.normalize_base_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected externally-blocked Base URL: {value}")


def test_base_url_validation_allows_external_only_when_enabled():
    assert (
        LocalLLMClient.normalize_base_url("http://api.openai.com/v1", allow_external=True)
        == "http://api.openai.com/v1"
    )
    assert (
        LocalLLMClient.normalize_base_url("https://api.openai.com/v1/", allow_external=True)
        == "https://api.openai.com/v1"
    )
    assert LocalLLMClient.normalize_base_url("http://192.168.10.20:8080/v1") == "http://192.168.10.20:8080/v1"


@pytest.mark.asyncio
async def test_local_client_rejects_external_report_url_by_default():
    client = LocalLLMClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    with pytest.raises(ValueError):
        await client.create_report("http://api.openai.com/v1", "model", "", {}, "prompt")


@pytest.mark.asyncio
async def test_local_client_uses_openai_compatible_chat_without_exposing_reasoning():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer local-secret"
        payload = __import__("json").loads(request.content)
        assert payload["model"] == "network-model"
        assert payload["messages"][0] == {"role": "system", "content": "必ず日本語だけで報告してください。"}
        assert "sample_count" in payload["messages"][1]["content"]
        assert payload["reasoning_effort"] == "none"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "総評\n正常です。", "reasoning_content": "internal"}}]},
        )

    client = LocalLLMClient(transport=httpx.MockTransport(handler))
    content = await client.create_report(
        "http://192.168.10.20:1234/v1", "network-model", "local-secret", {"sample_count": 10},
        "必ず日本語だけで報告してください。",
    )
    assert content == "総評\n正常です。"


@pytest.mark.asyncio
async def test_local_client_rejects_reasoning_without_final_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"reasoning_content": "internal"}}]})

    client = LocalLLMClient(transport=httpx.MockTransport(handler))
    with pytest.raises(LLMConnectionError, match="報告本文"):
        await client.create_report("http://127.0.0.1:1234/v1", "model", "", {})


@pytest.mark.asyncio
async def test_local_client_enriches_lm_studio_models_and_excludes_embedding():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "chat"}, {"id": "embed"}]})
        assert request.url.path == "/api/v1/models"
        return httpx.Response(
            200,
            json={"models": [{"key": "chat", "type": "llm"}, {"key": "embed", "type": "embedding"}]},
        )

    client = LocalLLMClient(transport=httpx.MockTransport(handler))
    assert await client.list_models("http://192.168.10.20:1234/v1") == [{"id": "chat", "type": "llm"}]


def test_local_address_policy_handles_ipv6_embedding_formats():
    """Python 3.10 reports several IPv6 embedding formats as is_private=True
    (v4-mapped link-local, Teredo 2001::/32), which would be an SSRF bypass."""
    from app.llm import _is_local_address

    # Sanity-check the fixtures themselves first (teredo/6to4 parsing).
    # Server is groups 3-4, client is the 0xFFFFFFFF-XOR-obfuscated groups 7-8.
    teredo_local = "2001:0:c0a8:0001:0:0:3f57:fffd"
    assert ipaddress.ip_address(teredo_local).teredo == (
        ipaddress.IPv4Address("192.168.0.1"),
        ipaddress.IPv4Address("192.168.0.2"),
    )

    cases = {
        # v4-mapped formats are judged by the embedded IPv4 address.
        "::ffff:169.254.169.254": False,  # cloud metadata via v4-mapped
        "::ffff:192.168.10.20": True,
        "::ffff:127.0.0.1": True,
        "::ffff:8.8.8.8": False,
        # 6to4 embeds the IPv4 base address.
        "2002:808:808::1": False,  # 8.8.8.8 tunnel base
        "2002:ac10:1::1": True,  # 172.16.0.1 tunnel base
        # Teredo embeds server/client IPv4 addresses.
        "2001:0:4860:4860:0:64ff:fe00:0": False,
        teredo_local: True,
        # Plain IPv6: loopback and unique-local only.
        "::1": True,
        "fd00::1": True,
        "fc00::1": True,
        "fe80::1": False,  # link-local (IPv6 metadata/SSRF vector)
        "2001:4860:4860::8888": False,  # public
        # IPv4 sanity.
        "10.0.0.5": True,
        "192.168.10.20": True,
        "169.254.169.254": False,
        "8.8.8.8": False,
    }
    for text, expected in cases.items():
        assert _is_local_address(ipaddress.ip_address(text)) is expected, text


@pytest.mark.asyncio
async def test_dns_rebinding_cannot_redirect_after_validation(monkeypatch):
    """Validation and connection must be bound: a rebinding resolver that
    answers loopback for the validation query but a public IP for the
    connection-time query must be rejected (and the pinned IP used)."""
    import socket as socket_module

    responses = [
        [(2, 1, 6, "", ("127.0.0.1", 0))],  # validation-time answer
        [(2, 1, 6, "", ("8.8.8.8", 0))],  # connection-time answer (attacker)
    ]

    def rebinding_dns(host, port, family=0, type=0, proto=0, flags=0):  # type: ignore[no-untyped-def]
        answer = responses.pop(0) if len(responses) > 1 else responses[0]
        return answer

    monkeypatch.setattr(socket_module, "getaddrinfo", rebinding_dns)
    seen: list[httpx.Request] = []
    handler = httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200, json={"data": []}))[1])
    client = LocalLLMClient(transport=handler)

    with pytest.raises(LLMConnectionError):
        await client.list_models("http://rebind.evil.example/v1")
    assert seen == []  # the pinned-target request was never dispatched


@pytest.mark.asyncio
async def test_connect_pins_resolved_address_and_keeps_host_header(monkeypatch):
    import socket as socket_module

    monkeypatch.setattr(
        socket_module,
        "getaddrinfo",
        lambda host, port, family=0, type=0, proto=0, flags=0: [(2, 1, 6, "", ("192.168.10.55", 0))],
    )
    seen: list[httpx.Request] = []
    handler = httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200, json={"data": []}))[1])
    client = LocalLLMClient(transport=handler)

    await client.list_models("http://llm.home.lan:1234/v1")
    (request,) = seen
    # Connected to the pinned IP, but the Host header keeps the original name.
    assert request.url.host == "192.168.10.55"
    assert request.headers["host"] == "llm.home.lan:1234"
    assert request.url.path == "/v1/models"


@pytest.mark.asyncio
async def test_external_transport_is_not_pinned_when_flag_enabled(monkeypatch):
    import socket as socket_module

    def no_dns(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("external mode must not run local DNS policy checks")

    monkeypatch.setattr(socket_module, "getaddrinfo", no_dns)
    seen: list[httpx.Request] = []
    handler = httpx.MockTransport(lambda request: (seen.append(request), httpx.Response(200, json={"data": []}))[1])
    client = LocalLLMClient(transport=handler)

    await client.list_models("http://api.openai.com:443/v1", allow_external=True)
    (request,) = seen
    assert request.url.host == "api.openai.com"
