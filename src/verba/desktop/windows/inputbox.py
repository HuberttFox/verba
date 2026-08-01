"""Input-only translation window. Results always go to ResultPopup."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

from verba.desktop.windows.popup import popup_rect


class InputWindow(QWidget):
    submitted = Signal(str)
    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("verbaInput")
        self._line = QLineEdit(self)
        self._line.setPlaceholderText("输入要翻译的文本,Enter 翻译")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self._line)
        self.setStyleSheet(
            "QWidget#verbaInput { background-color: rgba(255,255,255,245); border-radius: 8px; }"
        )

    def open_at(self, anchor: QPoint) -> None:
        self._line.clear()
        width = 360
        height = self._line.sizeHint().height() + 30
        screens = [s.geometry() for s in QApplication.screens()]
        self.setFixedSize(width, height)
        self.setGeometry(popup_rect(anchor, self.size(), screens))
        self.show()
        self.raise_()
        self._line.setFocus()

    def setText(self, text: str) -> None:
        self._line.setText(text)

    def text(self) -> str:
        return self._line.text()

    def submit(self) -> None:
        text = self._line.text().strip()
        if not text:
            return
        self.submitted.emit(text)
        self._line.clear()
        self.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.submit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.dismissed.emit()
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)
