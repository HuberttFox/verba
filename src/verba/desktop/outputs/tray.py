"""System tray icon with the main menu."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayOutputHandler(QSystemTrayIcon):
    action_translate = Signal()
    action_input = Signal()
    action_settings = Signal()
    action_quit = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        pixmap = QPixmap(16, 16)
        pixmap.fill(0x3B82F6)
        self.setIcon(QIcon(pixmap))
        self.setToolTip("verba")
        menu = QMenu()
        self._action_translate = menu.addAction("划词翻译")
        self._action_input = menu.addAction("输入翻译")
        menu.addSeparator()
        self._action_settings = menu.addAction("设置")
        self._action_quit = menu.addAction("退出")
        self.setContextMenu(menu)
        self._action_translate.triggered.connect(self.action_translate.emit)
        self._action_input.triggered.connect(self.action_input.emit)
        self._action_settings.triggered.connect(self.action_settings.emit)
        self._action_quit.triggered.connect(self.action_quit.emit)
        self.show()
