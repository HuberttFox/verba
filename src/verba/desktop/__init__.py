"""Desktop layer for verba — PySide6-only UI plumbing."""

from verba.desktop.hotkeys import (
    HOTKEY_INPUT_ID,
    HOTKEY_SELECTION_ID,
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

__all__ = [
    "HOTKEY_INPUT_ID",
    "HOTKEY_SELECTION_ID",
    "HotkeyError",
    "HotkeyManager",
    "HotkeySpec",
    "MOD_ALT",
    "MOD_CONTROL",
    "MOD_SHIFT",
    "MOD_WIN",
    "create_hotkey_manager",
    "parse_hotkey",
]
