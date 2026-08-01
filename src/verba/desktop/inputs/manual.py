"""Input source fed by the desktop InputWindow."""

from __future__ import annotations

from verba.desktop.windows.inputbox import InputWindow
from verba.inputs.base import InputPayload, InputSource
from verba.providers.errors import ProviderError


class ManualInputSource(InputSource):
    name = "manual"

    def __init__(self) -> None:
        self._last: str | None = None

    def attach(self, window: InputWindow) -> None:
        window.submitted.connect(self._store)

    def _store(self, text: str) -> None:
        self._last = text

    def capture(self) -> InputPayload:
        if self._last is None:
            raise ProviderError("manual input source: nothing submitted yet")
        return InputPayload(kind="text", text=self._last)
