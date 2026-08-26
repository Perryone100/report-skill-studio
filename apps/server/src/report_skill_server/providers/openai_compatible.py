from __future__ import annotations

import json
from typing import Any

import httpx

from .base import ProviderGenerationError


class OpenAICompatibleChatProvider:
    id = "openai-compatible"
    name = "OpenAI-compatible API"
    local = False

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider_id: str | None = None,
        provider_name: str | None = None,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ):
        self.id = provider_id or self.id
        self.name = provider_name or self.name
        normalized_base_url = base_url.rstrip("/")
        endpoint_suffix = "/chat/completions"
        if normalized_base_url.endswith(endpoint_suffix):
            normalized_base_url = normalized_base_url[: -len(endpoint_suffix)]
        self.base_url = normalized_base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.client = client or httpx.Client()

    def generate(
        self,
        *,
        transcript: str,
        title: str,
        instructions: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": (
                    f"{instructions}\n"
                    "只输出符合给定 JSON Schema 的 JSON，不要使用 Markdown 代码块。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"报告标题：{title}\n\n"
                    "JSON Schema："
                    f"{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    f"{prompt}"
                ),
            },
        ]
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderGenerationError(f"model generation failed: {exc}") from exc

        if not isinstance(result, dict):
            raise ProviderGenerationError("model response must be a JSON object")
        return result
