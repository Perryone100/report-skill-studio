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
