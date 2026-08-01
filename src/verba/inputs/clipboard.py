"""Clipboard-based input source (cross-platform via pyperclip)."""

from __future__ import annotations

from verba.inputs.base import InputPayload, InputSource


class ClipboardSource(InputSource):
    """Captures the current clipboard text."""

    name = "clipboard"

    def capture(self) -> InputPayload:
        import pyperclip  # lazy: headless environments have no clipboard

        text = pyperclip.paste()
        return InputPayload(kind="text", text=text)
