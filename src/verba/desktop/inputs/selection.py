"""划词捕获:热键触发 -> 模拟 Ctrl+C -> 轮询剪贴板 -> 立即恢复原内容。

Clipboard/send_ctrl_c are injectable so the state machine is fully
testable off-Windows. Restore happens immediately after capture, BEFORE
translation, so user copies made during translation are never clobbered.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal

from verba.inputs.base import InputPayload, InputSource
from verba.providers.errors import ProviderError


class ClipboardGateway(Protocol):
    def text(self) -> str: ...
    def mime_data(self) -> QMimeData: ...
    def set_mime(self, mime: QMimeData) -> None: ...


def send_ctrl_c_win32() -> None:
    """Send a Ctrl+C keypress via SendInput (Windows only)."""
    if sys.platform != "win32":
        raise ProviderError("simulated copy is Windows-only")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_C = 0x43

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT)]

    def press(vk: int, keyup: bool) -> None:
        inp = INPUT(INPUT_KEYBOARD, KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if keyup else 0, 0, None))
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ProviderError("SendInput failed (elevated target window?)")

    press(VK_CONTROL, False)
    press(VK_C, False)
    press(VK_C, True)
    press(VK_CONTROL, True)


class _QtClipboard(ClipboardGateway):
    def __init__(self) -> None:
        from PySide6.QtWidgets import QApplication

        self._clip = QApplication.clipboard()

    def text(self) -> str:
        return self._clip.text()

    def mime_data(self) -> QMimeData:
        mime = self._clip.mimeData()
        if mime is None:
            return QMimeData()
        return QMimeData(mime)  # type: ignore[call-arg]  # Qt copy ctor; stubs miss it

    def set_mime(self, mime: QMimeData) -> None:
        self._clip.setMimeData(QMimeData(mime))  # type: ignore[call-arg]  # Qt copy ctor; stubs miss it


class SelectionCapturer(QObject):
    """Simulate copy, capture the new clipboard text, restore the old one."""

    captured = Signal(str)
    nothing = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        clipboard: ClipboardGateway | None = None,
        send_ctrl_c: Callable[[], None] | None = None,
        poll_interval_ms: int = 50,
        timeout_ms: int = 1000,
    ) -> None:
        super().__init__(parent)
        self._clip = clipboard or _QtClipboard()
        self._send = send_ctrl_c or send_ctrl_c_win32
        self._poll_interval_ms = poll_interval_ms
        self._timeout_ms = timeout_ms
        self._original: QMimeData | None = None
        self._retries_left = 1
        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._original = self._clip.mime_data()
        self._retries_left = 1
        self._elapsed = 0
        self._attempt()

    def _attempt(self) -> None:
        try:
            self._send()
        except ProviderError:
            self._finish_restore()
            self.nothing.emit()
            return
        self._elapsed = 0
        self._timer.start()

    def _poll(self) -> None:
        self._elapsed += self._poll_interval_ms
        text = self._clip.text()
        if text and text.strip() and text != self._original_text():
            self._finish_restore()
            self.captured.emit(text)
            return
        if self._elapsed >= self._timeout_ms:
            if self._retries_left > 0:
                self._retries_left -= 1
                self._attempt()
                return
            self._timer.stop()
            self._finish_restore()
            self.nothing.emit()

    def _original_text(self) -> str:
        return self._original.text() if self._original is not None else ""

    def _finish_restore(self) -> None:
        self._timer.stop()
        if self._original is not None:
            self._clip.set_mime(self._original)


class SelectionInputSource(InputSource):
    name = "selection"

    def __init__(self) -> None:
        self._last: str | None = None

    def attach(self, capturer: SelectionCapturer) -> None:
        capturer.captured.connect(self._store)

    def _store(self, text: str) -> None:
        self._last = text

    def capture(self) -> InputPayload:
        if self._last is None:
            raise ProviderError("selection source: nothing captured yet")
        return InputPayload(kind="text", text=self._last)
