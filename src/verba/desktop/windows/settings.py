"""Settings window: hotkeys, default provider, target language."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from verba.config import loader
from verba.config.schema import AppConfig
from verba.desktop.hotkeys import (
    HOTKEY_INPUT_ID,
    HOTKEY_SELECTION_ID,
    HotkeyError,
    HotkeyManager,
    parse_hotkey,
)
from verba.models.translation import Lang


class SettingsWindow(QWidget):
    config_changed = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        hotkeys: HotkeyManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._hotkeys = hotkeys
        self.setWindowTitle("verba 设置")

        form = QFormLayout(self)
        self._selection_hotkey = QLineEdit(config.desktop.hotkey_selection)
        self._input_hotkey = QLineEdit(config.desktop.hotkey_input)
        self._target_lang = QComboBox()
        for lang in (Lang.ZH_HANS, Lang.ZH_HANT, Lang.EN, Lang.JA, Lang.KO, Lang.FR):
            self._target_lang.addItem(lang.value, lang)
        index = self._target_lang.findData(config.desktop.default_target)
        if index < 0:
            lang = config.desktop.default_target
            self._target_lang.addItem(lang.value, lang)
            index = self._target_lang.count() - 1
        self._target_lang.setCurrentIndex(index)

        form.addRow("划词热键", self._selection_hotkey)
        form.addRow("输入热键", self._input_hotkey)
        form.addRow("目标语言", self._target_lang)

        save = QPushButton("保存")
        save.clicked.connect(self.save)
        form.addRow(save)

        self._error = QLineEdit()
        self._error.setReadOnly(True)
        self._error.setStyleSheet("color:#c0392b; border:none;")
        form.addRow(self._error)

    def hotkey_selection_text(self) -> str:
        return self._selection_hotkey.text()

    def set_hotkey_selection_text(self, text: str) -> None:
        self._selection_hotkey.setText(text)

    def save(self) -> bool:
        try:
            selection_spec = parse_hotkey(self._selection_hotkey.text())
            input_spec = parse_hotkey(self._input_hotkey.text())
        except HotkeyError as exc:
            self._error.setText(str(exc))
            return False
        self._error.clear()

        # 先重绑热键,失败回滚旧绑定
        old_selection = parse_hotkey(self._config.desktop.hotkey_selection)
        old_input = parse_hotkey(self._config.desktop.hotkey_input)
        try:
            self._hotkeys.rebind(HOTKEY_SELECTION_ID, selection_spec)
            try:
                self._hotkeys.rebind(HOTKEY_INPUT_ID, input_spec)
            except HotkeyError:
                self._hotkeys.rebind(HOTKEY_SELECTION_ID, old_selection)
                raise
        except HotkeyError as exc:
            self._hotkeys.rebind(HOTKEY_SELECTION_ID, old_selection)
            self._hotkeys.rebind(HOTKEY_INPUT_ID, old_input)
            self._error.setText(str(exc))
            return False

        config = self._config.model_copy(deep=True)
        config = config.model_copy(
            update={
                "desktop": config.desktop.model_copy(
                    update={
                        "hotkey_selection": self._selection_hotkey.text(),
                        "hotkey_input": self._input_hotkey.text(),
                        "default_target": Lang(self._target_lang.currentData()),
                    }
                )
            }
        )
        self._write_toml(config)
        self.config_changed.emit(config)
        self.close()
        return True

    @staticmethod
    def _write_toml(config: AppConfig) -> None:
        """Merge the desktop section into the existing TOML (never clobber)."""
        path: Path = loader.user_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if path.is_file():
            with path.open("rb") as fh:
                existing = tomllib.load(fh)
        existing["desktop"] = {
            "hotkey_selection": config.desktop.hotkey_selection,
            "hotkey_input": config.desktop.hotkey_input,
            "default_target": config.desktop.default_target.value,
            "popup_auto_close_ms": config.desktop.popup_auto_close_ms,
            "click_to_copy": config.desktop.click_to_copy,
        }
        with path.open("wb") as fh:
            tomli_w.dump(existing, fh)
