"""Output handlers: how translation results reach the user.

The core framework never imports a GUI toolkit. A desktop app registers
an OutputHandler that renders results into its own widgets (popup window,
notification, tray, ...).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from verba.core.registry import DuplicateProviderError
from verba.models.translation import TranslationResult


class OutputHandler(ABC):
    """Presents a translation result to the user."""

    name: str

    @abstractmethod
    def present(self, result: TranslationResult) -> None:
        """Render *result* (popup, log line, copy to clipboard...)."""


class OutputHub:
    """Holds all registered handlers; pipeline fans results out to them."""

    def __init__(self) -> None:
        self._handlers: dict[str, OutputHandler] = {}

    def register(self, handler: OutputHandler, *, replace: bool = False) -> None:
        if handler.name in self._handlers and not replace:
            raise DuplicateProviderError(handler.name)
        self._handlers[handler.name] = handler

    def unregister(self, name: str) -> None:
        self._handlers.pop(name, None)

    def names(self) -> list[str]:
        return list(self._handlers)

    def present_all(self, result: TranslationResult, only: str | None = None) -> None:
        """Deliver *result* to every handler, or only to ``only``."""
        targets = (
            [self._handlers[only]] if only is not None else list(self._handlers.values())
        )
        for handler in targets:
            handler.present(result)
