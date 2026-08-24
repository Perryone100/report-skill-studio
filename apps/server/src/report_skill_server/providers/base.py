from __future__ import annotations

from typing import Any, Protocol


class ProviderGenerationError(RuntimeError):
    pass


class ChatProvider(Protocol):
    id: str
    name: str
    model: str
    local: bool

    def generate(
        self,
        *,
        transcript: str,
        title: str,
        instructions: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...
