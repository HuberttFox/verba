from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from verba.desktop.inputs.manual import ManualInputSource
from verba.desktop.windows.inputbox import InputWindow


def test_input_window_submits_text(qtbot: QtBot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    window.open_at(QPoint(50, 50))

    window.setText("hello world")
    with qtbot.waitSignal(window.submitted, timeout=1000) as blocker:
        window.submit()
    assert blocker.args == ["hello world"]


def test_input_window_enter_key_submits(qtbot: QtBot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    window.open_at(QPoint(50, 50))
    window.setText("你好")
    with qtbot.waitSignal(window.submitted, timeout=1000):
        qtbot.keyClick(window, Qt.Key.Key_Return)  # type: ignore[no-untyped-call]  # ignore: pytest-qt stub lacks keyClick signature
    assert window.text() == ""


def test_input_window_escape_dismisses(qtbot: QtBot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    window.open_at(QPoint(50, 50))
    with qtbot.waitSignal(window.dismissed, timeout=1000):
        qtbot.keyClick(window, Qt.Key.Key_Escape)  # type: ignore[no-untyped-call]  # ignore: pytest-qt stub lacks keyClick signature


def test_manual_source_returns_submitted_text(qtbot: QtBot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    source = ManualInputSource()
    source.attach(window)
    window.setText("via source")
    window.submit()
    payload = source.capture()
    assert payload.kind == "text"
    assert payload.text == "via source"


def test_manual_source_errors_without_submission() -> None:
    source = ManualInputSource()
    with pytest.raises(Exception):
        source.capture()
