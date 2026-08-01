"""Global hotkeys on Windows via RegisterHotKey + Qt native event filter.

Win32 primitives are guarded by sys.platform so tests run anywhere;
a no-op fallback keeps the rest of the app functional off-Windows.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QWidget

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

HOTKEY_SELECTION_ID = 1
HOTKEY_INPUT_ID = 2

_FUNCTION_KEYS = {f"F{i}": 0x6F + i for i in range(1, 25)}  # VK_F1=0x70

_MODIFIER_NAMES = {
    "ctrl": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}


class HotkeyError(ValueError):
    """Malformed hotkey spec or registration failure."""


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: int
    vk: int


def parse_hotkey(spec: str) -> HotkeySpec:
    """Parse 'Ctrl+Alt+D' / 'Shift+Win+F5' (case-insensitive) into a spec."""
    parts = [p.strip().lower() for p in spec.split("+")]
    if not parts or any(not p for p in parts):
        raise HotkeyError(f"invalid hotkey: {spec!r}")
    key = parts[-1]
    modifiers = 0
    for mod in parts[:-1]:
        value = _MODIFIER_NAMES.get(mod)
        if value is None:
            raise HotkeyError(f"unknown modifier: {mod!r}")
        modifiers |= value
    if not modifiers:
        raise HotkeyError("hotkey needs at least one modifier")
    if key.upper() in _FUNCTION_KEYS:
        vk = _FUNCTION_KEYS[key.upper()]
    elif len(key) == 1 and key.isascii() and key.isalpha():
        vk = ord(key.upper())
    else:
        raise HotkeyError(f"unsupported key: {key!r}")
    return HotkeySpec(modifiers=modifiers, vk=vk)


class _HiddenMessageWindow(QWidget):
    """Never shown; exists only to own an HWND for RegisterHotKey."""

    def __init__(self) -> None:
        super().__init__()  # created only after QApplication exists (win32)
        self.setObjectName("verbaHotkeyHost")


class _NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, manager: "HotkeyManager") -> None:
        super().__init__()
        self._manager = manager

    def nativeEventFilter(self, event_type: bytes, message: int) -> tuple[bool, int]:  # type: ignore[override]  # ignore: PySide6 stub widens params
        if sys.platform != "win32":
            return False, 0
        import ctypes
        import ctypes.wintypes

        msg = ctypes.wintypes.MSG.from_address(message)
        if msg.message == 0x0312:  # WM_HOTKEY
            self._manager.hotkey_triggered.emit(int(msg.wParam))
            return True, 0
        return False, 0


class HotkeyManager(QObject):
    """Binds hotkey_id -> (modifiers, vk) via RegisterHotKey on Windows."""

    hotkey_triggered = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bindings: dict[int, HotkeySpec] = {}
        self._hwnd: int | None = None
        self._hidden: QWidget | None = None
        self._hook_installed = False
        if sys.platform == "win32":
            self._install_win32()

    def _install_win32(self) -> None:
        from PySide6.QtWidgets import QApplication

        hidden = _HiddenMessageWindow()
        self._hwnd = int(hidden.winId())
        self._hidden = hidden  # keep a reference alive
        app = QApplication.instance()
        assert app is not None
        app.installNativeEventFilter(_NativeHotkeyFilter(self))
        self._hook_installed = True

    def bind(self, hotkey_id: int, spec: HotkeySpec) -> None:
        if not self._hook_installed:
            self._bindings[hotkey_id] = spec  # no-op fallback off-Windows
            return
        import ctypes

        user32 = getattr(ctypes, "windll").user32
        if not user32.RegisterHotKey(self._hwnd, hotkey_id, spec.modifiers, spec.vk):
            raise HotkeyError(f"RegisterHotKey failed for id={hotkey_id} (in use?)")
        self._bindings[hotkey_id] = spec

    def unbind(self, hotkey_id: int) -> None:
        if hotkey_id not in self._bindings:
            return
        if self._hook_installed:
            import ctypes

            user32 = getattr(ctypes, "windll").user32
            user32.UnregisterHotKey(self._hwnd, hotkey_id)
        del self._bindings[hotkey_id]

    def rebind(self, hotkey_id: int, spec: HotkeySpec) -> None:
        self.unbind(hotkey_id)
        self.bind(hotkey_id, spec)


def create_hotkey_manager(parent: QObject | None = None) -> HotkeyManager:
    return HotkeyManager(parent)
