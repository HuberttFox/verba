"""Input sources: where captured content comes from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from verba.core.registry import DuplicateProviderError, ProviderNotFoundError
from verba.models.image import ImageSource


class InputPayload(BaseModel):
    """Uniform capture result: either text or an image."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["text", "image"]
    text: str | None = None
    image: ImageSource | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> InputPayload:
        if self.kind == "text" and self.text is None:
            raise ValueError("text payload requires 'text'")
        if self.kind == "image" and self.image is None:
            raise ValueError("image payload requires 'image'")
        return self


class InputSource(ABC):
    """Captures user content (selection, clipboard, screenshot, manual)."""

    name: str

    @abstractmethod
    def capture(self) -> InputPayload:
        """Block until one payload is available."""


class InputSourceRegistry:
    """Name -> InputSource lookup used by the pipeline."""

    def __init__(self) -> None:
        self._items: dict[str, InputSource] = {}

    def register(self, source: InputSource, *, replace: bool = False) -> None:
        if source.name in self._items and not replace:
            raise DuplicateProviderError(source.name)
        self._items[source.name] = source

    def get(self, name: str) -> InputSource:
        source = self._items.get(name)
        if source is None:
            raise ProviderNotFoundError(name)
        return source

    def names(self) -> list[str]:
        return list(self._items)
