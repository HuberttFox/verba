"""Bob-style result popup: frameless, rounded, always visible near cursor.

Uses Qt.Popup so clicks outside / Esc close it for free (no mouse hooks).
Pinned mode switches window flags to Qt.Tool so it survives outside clicks.
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from verba.config.schema import DesktopOptions
from verba.models.translation import TranslationResult

_MARGIN = 8
_BUTTON_HEIGHT = 26


def popup_rect(
    anchor: QPoint,
    size: QSize,
    screens: Sequence[QRect],
    margin: int = _MARGIN,
) -> QRect:
    """Place a popup of *size* near *anchor*, clamped into its screen."""
    screen = _pick_screen(anchor, screens)
    x = max(screen.left() + margin, min(anchor.x(), screen.right() - size.width() - margin))
    y = max(screen.top() + margin, min(anchor.y(), screen.bottom() - size.height() - margin))
    return QRect(x, y, size.width(), size.height())


def _pick_screen(anchor: QPoint, screens: Sequence[QRect]) -> QRect:
    for screen in screens:
        if screen.contains(anchor):
            return screen
    return screens[0]


class ResultPopup(QWidget):
    pinned_changed = Signal(bool)

    def __init__(self, options: DesktopOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._options = options
        self._result: TranslationResult | None = None
        self._pinned = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._auto_close)

        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("verbaPopup")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(6)

        self._browser = QTextBrowser(self)
        self._browser.setOpenExternalLinks(False)
        self._browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        self._browser.setReadOnly(True)
        layout.addWidget(self._browser)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self._copy_button = QPushButton("复制", self)
        self._pin_button = QPushButton("固定", self)
        self._close_button = QPushButton("关闭", self)
        for btn in (self._copy_button, self._pin_button, self._close_button):
            btn.setFixedHeight(_BUTTON_HEIGHT)
            buttons.addWidget(btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._copy_button.clicked.connect(self.copy_translation)
        self._pin_button.clicked.connect(self.toggle_pin)
        self._close_button.clicked.connect(self.hide)

        self.setStyleSheet(
            """
            QWidget#verbaPopup { background-color: rgba(255,255,255,245); border-radius: 8px; }
            QTextBrowser { border: none; background: transparent; }
            """
        )

    # -- public API ----------------------------------------------------------

    @property
    def is_pinned(self) -> bool:
        return self._pinned

    def toPlainText(self) -> str:
        return self._browser.toPlainText()

    def show_result(self, result: TranslationResult, anchor: QPoint, original: str | None = None) -> None:
        self._result = result
        self._original = original
        self._render()
        self.show_anchor(anchor)

    def show_error(self, message: str, anchor: QPoint) -> None:
        self._result = None
        self._original = None
        self._browser.setHtml(f'<div style="color:#c0392b;">{html.escape(message)}</div>')
        self.show_anchor(anchor)

    def show_anchor(self, anchor: QPoint) -> None:
        self.adjustSize()
        size = QSize(max(self.width(), 320), max(self.height(), 140))
        screens = [s.geometry() for s in QGuiApplication.screens()]
        rect = popup_rect(anchor, size, screens)
        self.setGeometry(rect)
        self.show()
        self.raise_()
        self._schedule_close()

    def copy_translation(self) -> None:
        if self._result is None:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._result.text)
        self._copy_button.setText("已复制")
        QTimer.singleShot(1200, lambda: self._copy_button.setText("复制"))

    def toggle_pin(self) -> None:
        self._pinned = not self._pinned
        self._pin_button.setText("取消固定" if self._pinned else "固定")
        flags = (
            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint
            if self._pinned
            else Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setWindowFlags(flags)
        self.show()  # re-show with new flags
        self._schedule_close()
        self.pinned_changed.emit(self._pinned)

    # -- internals -----------------------------------------------------------

    def _render(self) -> None:
        assert self._result is not None
        translated = html.escape(self._result.text)
        parts = []
        if self._original:
            parts.append(f'<div style="color:#888;font-size:12px;">{html.escape(self._original)}</div>')
        parts.append(f'<div style="font-size:15px;margin-top:6px;">{translated}</div>')
        self._browser.setHtml("".join(parts))

    def _schedule_close(self) -> None:
        self._timer.stop()
        if not self._pinned:
            self._timer.start(self._options.popup_auto_close_ms)

    def _auto_close(self) -> None:
        if not self._pinned:
            self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._options.click_to_copy and event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or child is self:
                self.copy_translation()
        super().mousePressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hide()
        event.ignore()
