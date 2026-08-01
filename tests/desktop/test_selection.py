from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData
from pytestqt.qtbot import QtBot

from verba.desktop.inputs.selection import (
    _QtClipboard,
    ClipboardGateway,
    SelectionCapturer,
    SelectionInputSource,
)


class FakeClipboard(ClipboardGateway):
    def __init__(self) -> None:
        self._text = ""
        self._original: QMimeData | None = None
        self.calls: list[str] = []
        self.deliver_after: int | None = None
        self._poll_count = 0

    def text(self) -> str:
        self._poll_count += 1
        if self.deliver_after is not None and self._poll_count >= self.deliver_after:
            return "selected text"
        return self._text

    def mime_data(self) -> QMimeData:
        mime = QMimeData()
        mime.setText(self._text)
        self._original = mime
        return mime

    def set_mime(self, mime: QMimeData) -> None:
        self.calls.append("set_mime")

    @property
    def restored(self) -> bool:
        return "set_mime" in self.calls


def make_capturer(fake: FakeClipboard) -> tuple[SelectionCapturer, list[int]]:
    clicks: list[int] = []

    def fake_send() -> None:
        clicks.append(1)

    return SelectionCapturer(
        clipboard=fake, send_ctrl_c=fake_send, poll_interval_ms=10, timeout_ms=200
    ), clicks


def test_capturer_emits_captured_and_restores(qtbot: QtBot) -> None:
    fake = FakeClipboard()
    fake.deliver_after = 3
    capturer, clicks = make_capturer(fake)
    with qtbot.waitSignal(capturer.captured, timeout=3000) as blocker:
        capturer.start()
    assert blocker.args == ["selected text"]
    assert fake.restored
    assert len(clicks) == 1


def test_capturer_retries_once_then_gives_up(qtbot: QtBot) -> None:
    fake = FakeClipboard()  # never delivers
    capturer, clicks = make_capturer(fake)
    with qtbot.waitSignal(capturer.nothing, timeout=3000):
        capturer.start()
    assert len(clicks) == 2  # initial + one retry
    assert fake.restored  # restored even on failure


def test_capturer_ignores_whitespace(qtbot: QtBot) -> None:
    fake = FakeClipboard()

    class WsClipboard(FakeClipboard):
        def text(self) -> str:
            return "   \n  "

    capturer, clicks = make_capturer(WsClipboard())
    with qtbot.waitSignal(capturer.nothing, timeout=3000):
        capturer.start()


def test_selection_source_wraps_capturer(qtbot: QtBot) -> None:
    fake = FakeClipboard()
    fake.deliver_after = 1
    capturer, _ = make_capturer(fake)
    source = SelectionInputSource()
    source.attach(capturer)
    with qtbot.waitSignal(capturer.captured, timeout=3000):
        capturer.start()
    payload = source.capture()
    assert payload.kind == "text"
    assert payload.text == "selected text"


def test_capturer_restores_on_unexpected_error(qtbot: QtBot) -> None:
    class BoomClipboard(FakeClipboard):
        def text(self) -> str:
            raise RuntimeError("boom")

    fake = BoomClipboard()
    capturer, _ = make_capturer(fake)
    with qtbot.waitSignal(capturer.nothing, timeout=3000):
        capturer.start()
    assert fake.restored


def test_qt_clipboard_roundtrip_preserves_mime(qtbot: QtBot) -> None:
    from PySide6.QtWidgets import QApplication

    source = QMimeData()
    source.setText("hello")
    source.setHtml("<b>hello</b>")
    expected_formats = set(source.formats())
    QApplication.clipboard().setMimeData(source)

    gateway = _QtClipboard()
    copied = gateway.mime_data()
    assert copied.text() == "hello"
    assert copied.html() == "<b>hello</b>"
    assert set(copied.formats()) == expected_formats

    gateway.set_mime(copied)
    restored = QApplication.clipboard().mimeData()
    assert restored is not None
    assert restored.text() == "hello"
    assert restored.html() == "<b>hello</b>"
    assert set(restored.formats()) == expected_formats
