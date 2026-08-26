import json

import httpx
import pytest

from report_skill_server.providers import OpenAICompatibleChatProvider


def test_openai_compatible_provider_returns_json_object() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://model.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["response_format"] == {"type": "json_object"}
        assert "根据逐字稿生成报告" in payload["messages"][1]["content"]
        assert 'JSON Schema：{"type":"object"}' in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"title":"报告","sections":[]}'}}
                ]
            },
        )

    provider = OpenAICompatibleChatProvider(
        base_url="https://model.example/v1/chat/completions",
        api_key="secret",
        model="test-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.generate(
        transcript="逐字稿",
        title="报告",
        instructions="只输出 JSON",
        prompt="根据逐字稿生成报告",
        schema={"type": "object"},
    )

    assert result["title"] == "报告"


def test_provider_constructor_rejects_remote_http_endpoint() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        OpenAICompatibleChatProvider(
            base_url="http://model.example/v1",
            api_key="secret",
            model="test-model",
        )
