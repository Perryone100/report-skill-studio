import json

import pytest

from report_skill_server.config import Settings
from report_skill_server.main import build_provider_registry


def test_multiple_openai_compatible_models_are_independent_options() -> None:
    settings = Settings(
        _env_file=None,
        openai_compatible_base_url="https://model.example/v1",
        openai_compatible_api_key="secret",
        openai_compatible_models="writing-standard, writing-economy\nwriting-standard",
    )

    assert settings.openai_compatible_model_names == [
        "writing-standard",
        "writing-economy",
    ]
    assert [provider.model for provider in build_provider_registry(settings).list()] == [
        "deterministic-mock",
        "writing-standard",
        "writing-economy",
    ]
    assert [provider.id for provider in build_provider_registry(settings).list()][1:] == [
        "openai-compatible:writing-standard",
        "openai-compatible:writing-economy",
    ]


def test_singular_model_setting_remains_compatible() -> None:
    settings = Settings(
        _env_file=None,
        openai_compatible_model="legacy-model",
    )

    assert settings.openai_compatible_model_names == ["legacy-model"]


def test_multiple_connections_keep_independent_addresses_keys_and_models() -> None:
    settings = Settings(
        _env_file=None,
        openai_compatible_connections=json.dumps(
            [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "base_url": "https://api.deepseek.example/v1",
                    "api_key": "deepseek-secret",
                    "models": ["deepseek-chat", "deepseek-reasoner"],
                },
                {
                    "id": "private-gateway",
                    "name": "内部网关",
                    "base_url": "http://127.0.0.1:9000/openai/v1/",
                    "api_key": "gateway-secret",
                    "models": ["writing-model"],
                },
            ]
        ),
    )

    registry = build_provider_registry(settings)
    infos = registry.list()
    assert [info.id for info in infos[1:]] == [
        "openai-compatible:deepseek:deepseek-chat",
        "openai-compatible:deepseek:deepseek-reasoner",
        "openai-compatible:private-gateway:writing-model",
    ]
    assert [info.name for info in infos[1:]] == ["DeepSeek", "DeepSeek", "内部网关"]
    deepseek = registry.get("openai-compatible:deepseek:deepseek-chat")
    gateway = registry.get("openai-compatible:private-gateway:writing-model")
    assert deepseek.base_url == "https://api.deepseek.example/v1"  # type: ignore[attr-defined]
    assert deepseek.api_key == "deepseek-secret"  # type: ignore[attr-defined]
    assert gateway.base_url == "http://127.0.0.1:9000/openai/v1"  # type: ignore[attr-defined]
    assert gateway.api_key == "gateway-secret"  # type: ignore[attr-defined]


def test_duplicate_connection_ids_are_rejected_without_exposing_keys() -> None:
    settings = Settings(
        _env_file=None,
        openai_compatible_connections=json.dumps(
            [
                {"id": "same", "name": "A", "base_url": "https://a.example/v1", "api_key": "secret-a", "models": ["a"]},
                {"id": "same", "name": "B", "base_url": "https://b.example/v1", "api_key": "secret-b", "models": ["b"]},
            ]
        ),
    )

    with pytest.raises(ValueError, match="must be unique") as caught:
        _ = settings.openai_compatible_connection_configs
    assert "secret-a" not in str(caught.value)
    assert "secret-b" not in str(caught.value)
