from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject

from verba.desktop.hotkeys import (
    HotkeyError,
    HotkeyManager,
    HotkeySpec,
    MOD_ALT,
    MOD_CONTROL,
    MOD_SHIFT,
    MOD_WIN,
    create_hotkey_manager,
    parse_hotkey,
)


def test_parse_simple_letter() -> None:
    spec = parse_hotkey("Ctrl+Alt+D")
    assert spec.modifiers == MOD_CONTROL | MOD_ALT
    assert spec.vk == ord("D")


def test_parse_shift_and_win() -> None:
    spec = parse_hotkey("Shift+Win+F5")
    assert spec.modifiers == MOD_SHIFT | MOD_WIN
    assert spec.vk == 0x74  # VK_F5


def test_parse_lowercase_letter() -> None:
    assert parse_hotkey("ctrl+d").vk == ord("D")


def test_parse_invalid() -> None:
    for bad in ("", "D", "Ctrl+", "Ctrl+Alt+Space", "Ctrl+Alt+DG", "Ctrl+Alt"):
        with pytest.raises(HotkeyError):
            parse_hotkey(bad)


def test_hotkey_error_is_value_error() -> None:
    assert issubclass(HotkeyError, ValueError)
