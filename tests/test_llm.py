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
