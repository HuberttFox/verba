from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tomllib
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytestqt.qtbot import QtBot

from verba.config.schema import AppConfig, DesktopOptions
from verba.desktop.hotkeys import HotkeyManager
from verba.desktop.windows.settings import SettingsWindow


def test_settings_loads_current_values(qtbot: QtBot) -> None:
    config = AppConfig(desktop=DesktopOptions(hotkey_selection="Ctrl+Shift+A"))
    window = SettingsWindow(config, HotkeyManager())
    qtbot.addWidget(window)
    assert window.hotkey_selection_text() == "Ctrl+Shift+A"


def test_settings_rejects_bad_hotkey(qtbot: QtBot) -> None:
    window = SettingsWindow(AppConfig(), HotkeyManager())
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("no-modifier")
    assert window.save() is False


def test_settings_save_emits_and_writes_toml(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from verba.config import loader

    monkeypatch.setattr(loader, "user_config_path", lambda: tmp_path / "config.toml")
    window = SettingsWindow(AppConfig(), HotkeyManager())
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("Ctrl+Shift+Y")
    with qtbot.waitSignal(window.config_changed, timeout=1000) as blocker:
        assert window.save() is True
    saved = tomllib.loads((tmp_path / "config.toml").read_text("utf-8"))
    assert saved["desktop"]["hotkey_selection"] == "Ctrl+Shift+Y"


def test_settings_save_preserves_other_sections(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from verba.config import loader

    target = tmp_path / "config.toml"
    target.write_text(
        '[providers]\n[providers.deepl]\nenabled = true\n', encoding="utf-8"
    )
    monkeypatch.setattr(loader, "user_config_path", lambda: target)
    window = SettingsWindow(AppConfig(), HotkeyManager())
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("Ctrl+Shift+Y")
    assert window.save() is True
    saved = tomllib.loads(target.read_text("utf-8"))
    assert saved["providers"]["deepl"]["enabled"] is True
    assert saved["desktop"]["hotkey_selection"] == "Ctrl+Shift+Y"


def test_settings_save_rebinds_hotkeys(qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from verba.config import loader
    from verba.desktop.hotkeys import HOTKEY_SELECTION_ID, parse_hotkey

    monkeypatch.setattr(loader, "user_config_path", lambda: tmp_path / "config.toml")

    manager = HotkeyManager()
    calls: list[tuple[int, object]] = []
    manager.rebind = lambda hotkey_id, spec: calls.append((hotkey_id, spec))  # type: ignore[method-assign]  # ignore: test stub
    window = SettingsWindow(AppConfig(), manager)
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("Ctrl+Shift+Z")
    assert window.save() is True
    assert (HOTKEY_SELECTION_ID, parse_hotkey("Ctrl+Shift+Z")) in calls
