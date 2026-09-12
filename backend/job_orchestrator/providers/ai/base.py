from __future__ import annotations

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


class AIProvider(Protocol):
    """Minimal boundary used by the product's optional AI services."""

    provider_id: str
    model: str

    def structured_completion(
        self,
        *,
        system_prompt: str,
        data: dict[str, Any],
        output_model: type[OutputT],
    ) -> OutputT: ...
