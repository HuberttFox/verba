# verba Windows 桌面层(划词 + 输入翻译)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 verba 仓库实现 Windows 桌面层:全局热键划词翻译 + 输入翻译,Bob 风格浮窗,托盘,免费+API key 翻译服务。

**Architecture:** 新增 `src/verba/desktop/` 层(唯一允许 import PySide6 的层)。热键(ctypes RegisterHotKey + nativeEventFilter)→ Qt 主线程 → `PipelineWorker(QThread)` 跑阻塞 pipeline → 信号回主线程 → `ResultPopup` 渲染。复用现有 Pipeline/EventBus/Registry/OutputHandler 抽象,核心包不动(唯一例外:HttpClient 加可选 transport 参数供测试)。

**Tech Stack:** Python >=3.12, PySide6 (Qt6), httpx, pydantic, pytest-qt (dev)。

## Global Constraints

- 版本底线:Python >=3.12;PySide6 >= 6.6(运行时依赖,直接进 `dependencies`);pytest-qt 进 `dev` 依赖
- 分层:仅 `verba.desktop.*` 可以 `import PySide6`;`verba.core`/`models`/`providers`/`config`/`inputs`(旧)/`outputs`(旧)/`utils` 一律不得 import GUI
- mypy strict 覆盖 `src` + `tests`(含 desktop);`# type: ignore` 仅允许带原因注释(如 `# ignore: PySide6 stub 缺 QWizard 重载`)
- 现有 24 测试保持绿;测试命令 `uv run pytest`,类型检查 `uv run mypy`
- GUI 测试:文件顶部 `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`(必须在 import PySide6 之前),pytest-qt `qtbot` 驱动
- Windows 专属调用(RegisterHotKey/SendInput)必须 `if sys.platform == "win32"` 守卫,非 Windows 走 no-op fallback —— 所有单测在 Linux/WSL 可跑
- UI 文案中文;代码/commit 注释英文,沿用仓库既有风格(conventional commits)
- 划词剪贴板:捕获成功**立即恢复**原 `QMimeData`(含图片等非文本格式),不得等翻译完成
- 错误映射两条错误树分开捕获:`ProviderError`(`ProviderNotAvailable`/`QuotaExceeded`/`NetworkError`)+ `HttpError`(utils/http.py,独立,携带 status_code)
- UAC 已知限制(不解决,文档标注):目标应用以管理员运行 → SendInput 静默失败

**规范:** 设计 spec 见 `docs/superpowers/specs/2026-08-01-verba-desktop-design.md`。

---

### Task 1: 依赖 + 配置扩展(DesktopOptions)

**Files:**
- Modify: `pyproject.toml`(dependencies / dev / scripts / pytest 配置)
- Modify: `src/verba/config/schema.py`(加 `DesktopOptions`)
- Test: `tests/test_config_desktop.py`(新建)

**Interfaces:**
- Consumes: `AppConfig`(pydantic BaseModel,schema.py:35)
- Produces: `DesktopOptions`(字段见下);script 入口 `verba-desktop = "verba.desktop.app:main"`

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pydantic import ValidationError
import pytest

from verba.config.schema import AppConfig, DesktopOptions
from verba.models.translation import Lang


def test_desktop_options_defaults() -> None:
    cfg = AppConfig()
    assert cfg.desktop.hotkey_selection == "Ctrl+Alt+D"
    assert cfg.desktop.hotkey_input == "Ctrl+Alt+L"
    assert cfg.desktop.default_target == Lang.ZH_HANS
    assert cfg.desktop.popup_auto_close_ms == 8000
    assert cfg.desktop.click_to_copy is True


def test_desktop_options_override_from_toml() -> None:
    cfg = AppConfig.model_validate(
        {"desktop": {"hotkey_selection": "Ctrl+Shift+X", "popup_auto_close_ms": 3000}}
    )
    assert cfg.desktop.hotkey_selection == "Ctrl+Shift+X"
    assert cfg.desktop.popup_auto_close_ms == 3000
    assert cfg.desktop.hotkey_input == "Ctrl+Alt+L"


def test_popup_auto_close_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"desktop": {"popup_auto_close_ms": 0}})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/test_config_desktop.py -v`
Expected: FAIL — `AttributeError: 'AppConfig' object has no attribute 'desktop'`

- [ ] **Step 3: 实现**

`src/verba/config/schema.py` 追加(schema.py:35 `AppConfig` 之前):

```python
class DesktopOptions(BaseModel):
    """GUI behavior. GUI reads these; core never touches them."""

    hotkey_selection: str = "Ctrl+Alt+D"
    hotkey_input: str = "Ctrl+Alt+L"
    default_target: Lang = Lang.ZH_HANS
    popup_auto_close_ms: int = 8000
    click_to_copy: bool = True

    @field_validator("popup_auto_close_ms")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("popup_auto_close_ms must be positive")
        return value
```

`AppConfig` 加字段:

```python
    desktop: DesktopOptions = Field(default_factory=DesktopOptions)
```

import 加 `field_validator`(pydantic 2:`from pydantic import BaseModel, Field, SecretStr, field_validator`)。

`pyproject.toml`:
- `dependencies` 加 `"PySide6>=6.6"`
- `dev` 加 `"pytest-qt>=4.4"`
- `[project.scripts]` 加 `verba-desktop = "verba.desktop.app:main"`
- `[tool.pytest.ini_options]` 改为:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  qt_api = "pyside6"
  ```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv sync` 然后 `uv run pytest tests/test_config_desktop.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 24 旧测试 + 3 新测试全绿;mypy strict 无错误

```bash
git add pyproject.toml uv.lock src/verba/config/schema.py tests/test_config_desktop.py
git commit -m "feat: desktop config options and PySide6 deps"
```

---

### Task 2: 热键解析 + HotkeyManager(Win32 RegisterHotKey)

**Files:**
- Create: `src/verba/desktop/__init__.py`, `src/verba/desktop/hotkeys.py`
- Test: `tests/desktop/test_hotkeys.py`(新建)

**Interfaces:**
- Consumes: 无(纯 stdlib + PySide6)
- Produces:
  - `parse_hotkey(spec: str) -> HotkeySpec`,其中 `HotkeySpec(modifiers: int, vk: int)`(dataclass frozen)
  - `class HotkeyManager(QObject)`,信号 `hotkey_triggered = Signal(int)`(发出 hotkey id)
  - 方法:`bind(hotkey_id: int, spec: HotkeySpec) -> None`(返回前失败抛 `HotkeyError`)、`unbind(hotkey_id: int) -> None`、`rebind(hotkey_id: int, spec: HotkeySpec) -> None`(unbind+bind)
  - `MOD_*` 常量:MOD_ALT=0x1, MOD_CONTROL=0x2, MOD_SHIFT=0x4, MOD_WIN=0x8;VK 查表 A-Z/F1-F24
  - `HOTKEY_SELECTION_ID = 1`、`HOTKEY_INPUT_ID = 2`(模块常量)
  - `create_hotkey_manager(parent: QObject) -> HotkeyManager`:win32 下真实实现,其他平台 fallback(注册空操作)

- [ ] **Step 0: mypy strict + PySide6 spike**

PySide6 自带类型 stub,`Signal(...)`/`connect` 在 strict 下通常可直接过;已知痛点:signal 槽函数参数类型放宽、`nativeEventFilter` 重载。**政策**:先写最小 PySide6 文件跑 `uv run mypy`,能过就保持;过不了的调用点加带原因注释的 `# type: ignore[...]`,不建 per-file 例外。本任务后续步骤即按此政策执行。

- [ ] **Step 1: 写失败测试(解析纯函数)**

```python
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_hotkeys.py -v`
Expected: FAIL — ModuleNotFoundError: verba.desktop.hotkeys

- [ ] **Step 3: 实现 hotkeys.py**

```python
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
    if key in _FUNCTION_KEYS:
        vk = _FUNCTION_KEYS[key]
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

        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(self._hwnd, hotkey_id, spec.modifiers, spec.vk):
            raise HotkeyError(f"RegisterHotKey failed for id={hotkey_id} (in use?)")
        self._bindings[hotkey_id] = spec

    def unbind(self, hotkey_id: int) -> None:
        if hotkey_id not in self._bindings:
            return
        if self._hook_installed:
            import ctypes

            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(self._hwnd, hotkey_id)
        del self._bindings[hotkey_id]

    def rebind(self, hotkey_id: int, spec: HotkeySpec) -> None:
        self.unbind(hotkey_id)
        self.bind(hotkey_id, spec)


def create_hotkey_manager(parent: QObject | None = None) -> HotkeyManager:
    return HotkeyManager(parent)
```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_hotkeys.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/ tests/desktop/test_hotkeys.py
git commit -m "feat: hotkey parsing and RegisterHotKey manager"
```

---

### Task 3: 浮窗定位纯函数 + ResultPopup

**Files:**
- Create: `src/verba/desktop/windows/__init__.py`, `src/verba/desktop/windows/popup.py`
- Test: `tests/desktop/test_popup.py`(新建)

**Interfaces:**
- Consumes: `TranslationResult`(models/translation.py:37),`DesktopOptions.click_to_copy / popup_auto_close_ms`
- Produces:
  - `popup_rect(anchor: QPoint, size: QSize, screens: Sequence[QRect], margin: int = 8) -> QRect` 纯函数
  - `class ResultPopup(QWidget)`:信号 `pinned_changed = Signal(bool)`;方法 `show_result(result: TranslationResult, anchor: QPoint, original: str | None = None) -> None`(记录+渲染)、`show_anchor(anchor: QPoint) -> None`(已渲染过的内容换位置)、`show_error(message: str, anchor: QPoint) -> None`(红色错误文案)、`copy_translation() -> None`;属性 `is_pinned: bool`
  - 内部构造 `ResultPopup(options: DesktopOptions, parent: QWidget | None = None)`

- [ ] **Step 1: 写失败测试(定位纯函数 + 浮窗离屏)**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize

from verba.config.schema import DesktopOptions
from verba.desktop.windows.popup import ResultPopup, popup_rect
from verba.models.translation import Lang, TranslationResult

SCREEN = QRect(0, 0, 1920, 1080)
SECONDARY = QRect(1920, 0, 1280, 1024)


def make_result() -> TranslationResult:
    return TranslationResult(
        text="你好,世界",
        source=Lang.AUTO,
        target=Lang.ZH_HANS,
        provider="echo",
    )


def test_rect_near_anchor() -> None:
    r = popup_rect(QPoint(500, 400), QSize(300, 200), [SCREEN])
    assert r.left() == 500
    assert r.top() == 400
    assert r.size() == QSize(300, 200)


def test_rect_clamps_right_bottom() -> None:
    r = popup_rect(QPoint(1800, 1000), QSize(300, 200), [SCREEN])
    assert r.right() <= SCREEN.right() - 8
    assert r.bottom() <= SCREEN.bottom() - 8
    assert r.width() == 300


def test_rect_clamps_left_top() -> None:
    r = popup_rect(QPoint(2, 2), QSize(300, 200), [SCREEN])
    assert r.left() >= SCREEN.left() + 8
    assert r.top() >= SCREEN.top() + 8


def test_rect_uses_anchor_screen() -> None:
    r = popup_rect(QPoint(2000, 500), QSize(300, 200), [SCREEN, SECONDARY])
    assert r.left() >= SECONDARY.left()
    assert r.right() <= SECONDARY.right()


def test_popup_renders_result_and_copies(qtbot) -> None:
    popup = ResultPopup(DesktopOptions())
    qtbot.addWidget(popup)
    popup.show_result(make_result(), QPoint(100, 100))
    assert popup.isVisible()
    assert "你好,世界" in popup.toPlainText()

    popup.copy_translation()
    from PySide6.QtWidgets import QApplication

    clip = QApplication.clipboard().text()
    assert clip == "你好,世界"


def test_popup_pin_disables_auto_close(qtbot) -> None:
    opts = DesktopOptions(popup_auto_close_ms=100)
    popup = ResultPopup(opts)
    qtbot.addWidget(popup)
    popup.show_result(make_result(), QPoint(100, 100))
    qtbot.mouseClick(popup, Qt.MouseButton.LeftButton, pos=popup.rect().topRight() - QPoint(2, 2))
    assert popup.is_pinned
    qtbot.wait(300)
    assert popup.isVisible()
```

(最后一个测试的 `Qt` 从 `PySide6.QtCore` import;若按钮位置不可靠,改为直接调用 `popup._pin_button.click()`,见实现。)

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_popup.py -v`
Expected: FAIL — ModuleNotFoundError: verba.desktop.windows.popup

- [ ] **Step 3: 实现**

`src/verba/desktop/windows/popup.py`:

```python
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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]  # ignore: PySide6 stub widening
        if self._options.click_to_copy and event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or child is self:
                self.copy_translation()
        super().mousePressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # type: ignore[override]
        self.hide()
        event.ignore()
```

测试中的点击固定按钮:将 `qtbot.mouseClick(...)` 替换为 `popup._pin_button.click()`。

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_popup.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/windows/ tests/desktop/test_popup.py
git commit -m "feat: result popup with geometry clamping and pin"
```

---

### Task 4: InputWindow(输入窗)+ ManualInputSource

**Files:**
- Create: `src/verba/desktop/windows/inputbox.py`, `src/verba/desktop/inputs/__init__.py`, `src/verba/desktop/inputs/manual.py`
- Test: `tests/desktop/test_inputbox.py`(新建)

**Interfaces:**
- Consumes: 无
- Produces:
  - `class InputWindow(QWidget)`:信号 `submitted = Signal(str)`、`dismissed = Signal()`;方法 `open_at(anchor: QPoint) -> None`(清空+定位+显示+聚焦);Enter 提交、Esc 关闭
  - `class ManualInputSource(InputSource)`(`verba.inputs.base` 的 `InputSource`,name = "manual"):`attach(window: InputWindow) -> None`;`capture() -> InputPayload` 返回最近一次 submitted 文本(未提交抛 `ProviderError`)

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from verba.desktop.inputs.manual import ManualInputSource
from verba.desktop.windows.inputbox import InputWindow


def test_input_window_submits_text(qtbot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    window.open_at(QPoint(50, 50))

    window.setText("hello world")
    with qtbot.waitSignal(window.submitted, timeout=1000) as blocker:
        window.submit()
    assert blocker.args == ["hello world"]


def test_input_window_enter_key_submits(qtbot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    window.open_at(QPoint(50, 50))
    window.setText("你好")
    with qtbot.waitSignal(window.submitted, timeout=1000):
        qtbot.keyClick(window, Qt.Key.Key_Return)
    assert window.text() == ""


def test_input_window_escape_dismisses(qtbot) -> None:
    window = InputWindow()
    qtbot.addWidget(window)
    window.open_at(QPoint(50, 50))
    with qtbot.waitSignal(window.dismissed, timeout=1000):
        qtbot.keyClick(window, Qt.Key.Key_Escape)


def test_manual_source_returns_submitted_text(qtbot) -> None:
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
```

(最后一条用 `Exception` 基类即可;pipeline 会包装成 PipelineFailed。)

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_inputbox.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现**

`src/verba/desktop/windows/inputbox.py`:

```python
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
        self.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]  # ignore: PySide6 stub widening
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
```

`src/verba/desktop/inputs/manual.py`:

```python
"""Input source fed by the desktop InputWindow."""

from __future__ import annotations

from verba.desktop.windows.inputbox import InputWindow
from verba.inputs.base import InputPayload, InputSource
from verba.providers.errors import ProviderError


class ManualInputSource(InputSource):
    name = "manual"

    def __init__(self) -> None:
        self._last: str | None = None

    def attach(self, window: InputWindow) -> None:
        window.submitted.connect(self._store)

    def _store(self, text: str) -> None:
        self._last = text

    def capture(self) -> InputPayload:
        if self._last is None:
            raise ProviderError("manual input source: nothing submitted yet")
        return InputPayload(kind="text", text=self._last)
```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_inputbox.py -v`
Expected: PASS (5 passed)。`popup_rect` 需要 `self.size()` 非零,先 setFixedSize 再算位置(实现里已这样)。

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/windows/inputbox.py src/verba/desktop/inputs/
git commit -m "feat: input translation window and manual input source"
```

---

### Task 5: PipelineWorker + QPopupOutputHandler

**Files:**
- Create: `src/verba/desktop/workers.py`, `src/verba/desktop/outputs/__init__.py`, `src/verba/desktop/outputs/popup_handler.py`
- Test: `tests/desktop/test_worker.py`(新建)

**Interfaces:**
- Consumes: `Pipeline`(core/pipeline.py:46),`PipelineAction`(:31),`TranslationResult`(:37),`ResultPopup`
- Produces:
  - `class PipelineWorker(QThread)`:信号 `finished_ok = Signal(object)`(TranslationResult)、`failed = Signal(str, object)`(action_name, **异常对象**);`submit(action: PipelineAction, *, text: str | None = None) -> None`(启动线程执行一次)
  - `class QPopupOutputHandler(OutputHandler)`:name = "popup";`present(result: TranslationResult) -> None` → 调 popup 渲染(handler 构造时注入 `get_anchor: Callable[[], QPoint]`)

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint

from verba.config.schema import DesktopOptions
from verba.core.pipeline import PipelineAction
from verba.desktop.outputs.popup_handler import QPopupOutputHandler
from verba.desktop.workers import PipelineWorker
from verba.desktop.windows.popup import ResultPopup
from verba.models.translation import Lang, TranslationResult


class FakePipeline:
    def run(self, action, *, text=None):
        return TranslationResult(
            text="worker ok",
            source=Lang.AUTO,
            target=Lang.ZH_HANS,
            provider="fake",
        )


class FailingPipeline:
    def run(self, action, *, text=None):
        raise ValueError("boom")


def test_worker_emits_success(qtbot) -> None:
    worker = PipelineWorker(FakePipeline())
    with qtbot.waitSignal(worker.finished_ok, timeout=3000) as blocker:
        worker.submit(PipelineAction(name="t", translator_provider="fake"), text="hi")
    assert blocker.args[0].text == "worker ok"
    worker.wait()


def test_worker_emits_failure(qtbot) -> None:
    worker = PipelineWorker(FailingPipeline())
    with qtbot.waitSignal(worker.failed, timeout=3000) as blocker:
        worker.submit(PipelineAction(name="t", translator_provider="fake"), text="hi")
    assert isinstance(blocker.args[1], ValueError)
    assert str(blocker.args[1]) == "boom"
    worker.wait()


def test_handler_renders_into_popup(qtbot) -> None:
    popup = ResultPopup(DesktopOptions())
    qtbot.addWidget(popup)
    handler = QPopupOutputHandler(popup, get_anchor=lambda: QPoint(10, 10))
    result = TranslationResult(
        text="你好", source=Lang.AUTO, target=Lang.ZH_HANS, provider="echo"
    )
    handler.present(result)
    assert popup.isVisible()
    assert "你好" in popup.toPlainText()
```

(worker 是无父对象 QThread;信号断言后必须 `worker.wait()` 确保线程退出后再回收,防止析构崩溃。)

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_worker.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现**

`src/verba/desktop/workers.py`:

```python
"""Run blocking pipeline work off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from verba.core.pipeline import Pipeline, PipelineAction
from verba.models.translation import TranslationResult


class PipelineWorker(QThread):
    """Executes one pipeline.run() per submit()."""

    finished_ok = Signal(object)
    failed = Signal(str, object)

    def __init__(self, pipeline: Pipeline) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._action: PipelineAction | None = None
        self._text: str | None = None

    def submit(self, action: PipelineAction, *, text: str | None = None) -> None:
        if self.isRunning():
            return
        self._action = action
        self._text = text
        self.start()

    def run(self) -> None:  # type: ignore[override]  # ignore: PySide6 stub widens
        action = self._action
        if action is None:
            return
        try:
            result = self._pipeline.run(action, text=self._text)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - surfaced to UI
            self.failed.emit(action.name, exc)
```

`src/verba/desktop/outputs/popup_handler.py`:

```python
"""OutputHandler that renders results into the ResultPopup."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint

from verba.desktop.windows.popup import ResultPopup
from verba.models.translation import TranslationResult
from verba.outputs.base import OutputHandler


class QPopupOutputHandler(OutputHandler):
    name = "popup"

    def __init__(
        self,
        popup: ResultPopup,
        get_anchor: Callable[[], QPoint],
        get_original: Callable[[], str | None] = lambda: None,
    ) -> None:
        self._popup = popup
        self._get_anchor = get_anchor
        self._get_original = get_original

    def present(self, result: TranslationResult) -> None:
        self._popup.show_result(
            result, self._get_anchor(), original=self._get_original()
        )
```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_worker.py -v`
Expected: PASS (3 passed;worker 测试用 `PipelineAction(name="t", translator_provider="fake")`)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/workers.py src/verba/desktop/outputs/
git commit -m "feat: pipeline worker thread and popup output handler"
```

---

### Task 6: SelectionCapturer(划词核心:模拟复制 + 剪贴板立即恢复)

**Files:**
- Create: `src/verba/desktop/inputs/selection.py`
- Test: `tests/desktop/test_selection.py`(新建)

**Interfaces:**
- Consumes: `QApplication.clipboard()`(仅主线程操作)
- Produces:
  - `class SelectionCapturer(QObject)`:信号 `captured = Signal(str)`(选中文本)、`nothing = Signal()`;构造 `SelectionCapturer(parent=None, clipboard: ClipboardGateway | None = None, send_ctrl_c: Callable[[], None] | None = None)`
  - `start() -> None`:保存原 QMimeData → 发 Ctrl+C → 轮询(50ms 间隔,1s 上限)→ 失败整体重试一次 → 恢复原剪贴板;成功则**立即恢复**再 emit
  - `ClipboardGateway`(protocol):`text() -> str`、`mime_data() -> QMimeData`、`set_mime(mime: QMimeData) -> None`
  - `default_clipboard() -> ClipboardGateway`(包 QClipboard)、`send_ctrl_c_win32() -> None`(SendInput;非 win32 抛 `HotkeyError`)
  - `class SelectionInputSource(InputSource)`:name = "selection",`attach(capturer: SelectionCapturer) -> None`(captured → 存 last),`capture() -> InputPayload`

- [ ] **Step 1: 写失败测试(注入假剪贴板与假按键)**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData

from verba.desktop.inputs.selection import (
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


def make_capturer(fake: FakeClipboard):
    clicks = []

    def fake_send() -> None:
        clicks.append(1)

    return SelectionCapturer(
        clipboard=fake, send_ctrl_c=fake_send, poll_interval_ms=10, timeout_ms=200
    ), clicks


def test_capturer_emits_captured_and_restores(qtbot) -> None:
    fake = FakeClipboard()
    fake.deliver_after = 3
    capturer, clicks = make_capturer(fake)
    qtbot.addWidget(capturer)
    with qtbot.waitSignal(capturer.captured, timeout=3000) as blocker:
        capturer.start()
    assert blocker.args == ["selected text"]
    assert fake.restored
    assert len(clicks) == 1


def test_capturer_retries_once_then_gives_up(qtbot) -> None:
    fake = FakeClipboard()  # never delivers
    capturer, clicks = make_capturer(fake)
    qtbot.addWidget(capturer)
    with qtbot.waitSignal(capturer.nothing, timeout=3000):
        capturer.start()
    assert len(clicks) == 2  # initial + one retry
    assert fake.restored  # restored even on failure


def test_capturer_ignores_whitespace(qtbot) -> None:
    fake = FakeClipboard()

    class WsClipboard(FakeClipboard):
        def text(self) -> str:
            return "   \n  "

    capturer, clicks = make_capturer(WsClipboard())
    qtbot.addWidget(capturer)
    with qtbot.waitSignal(capturer.nothing, timeout=3000):
        capturer.start()


def test_selection_source_wraps_capturer(qtbot) -> None:
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_selection.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现**

`src/verba/desktop/inputs/selection.py`:

```python
"""划词捕获:热键触发 -> 模拟 Ctrl+C -> 轮询剪贴板 -> 立即恢复原内容。

Clipboard/send_ctrl_c are injectable so the state machine is fully
testable off-Windows. Restore happens immediately after capture, BEFORE
translation, so user copies made during translation are never clobbered.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QMimeData, QObject, QTimer, Signal

from verba.inputs.base import InputPayload, InputSource
from verba.providers.errors import ProviderError


class ClipboardGateway(Protocol):
    def text(self) -> str: ...
    def mime_data(self) -> QMimeData: ...
    def set_mime(self, mime: QMimeData) -> None: ...


def send_ctrl_c_win32() -> None:
    """Send a Ctrl+C keypress via SendInput (Windows only)."""
    if sys.platform != "win32":
        raise ProviderError("simulated copy is Windows-only")
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_C = 0x43

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT)]

    def press(vk: int, keyup: bool) -> None:
        inp = INPUT(INPUT_KEYBOARD, KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if keyup else 0, 0, None))
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ProviderError("SendInput failed (elevated target window?)")

    press(VK_CONTROL, False)
    press(VK_C, False)
    press(VK_C, True)
    press(VK_CONTROL, True)


class _QtClipboard(ClipboardGateway):
    def __init__(self) -> None:
        from PySide6.QtWidgets import QApplication

        self._clip = QApplication.clipboard()

    def text(self) -> str:
        return self._clip.text()

    def mime_data(self) -> QMimeData:
        mime = self._clip.mimeData()
        if mime is None:
            return QMimeData()
        return QMimeData(mime)  # copy; clipboard owns the original

    def set_mime(self, mime: QMimeData) -> None:
        self._clip.setMimeData(QMimeData(mime))


class SelectionCapturer(QObject):
    """Simulate copy, capture the new clipboard text, restore the old one."""

    captured = Signal(str)
    nothing = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        clipboard: ClipboardGateway | None = None,
        send_ctrl_c: Callable[[], None] | None = None,
        poll_interval_ms: int = 50,
        timeout_ms: int = 1000,
    ) -> None:
        super().__init__(parent)
        self._clip = clipboard or _QtClipboard()
        self._send = send_ctrl_c or send_ctrl_c_win32
        self._poll_interval_ms = poll_interval_ms
        self._timeout_ms = timeout_ms
        self._original: QMimeData | None = None
        self._retries_left = 1
        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.setInterval(poll_interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._original = self._clip.mime_data()
        self._retries_left = 1
        self._elapsed = 0
        self._attempt()

    def _attempt(self) -> None:
        try:
            self._send()
        except ProviderError:
            self._finish_restore()
            self.nothing.emit()
            return
        self._elapsed = 0
        self._timer.start()

    def _poll(self) -> None:
        self._elapsed += self._poll_interval_ms
        text = self._clip.text()
        if text and text.strip() and text != self._original_text():
            self._finish_restore()
            self.captured.emit(text)
            return
        if self._elapsed >= self._timeout_ms:
            if self._retries_left > 0:
                self._retries_left -= 1
                self._attempt()
                return
            self._timer.stop()
            self._finish_restore()
            self.nothing.emit()

    def _original_text(self) -> str:
        return self._original.text() if self._original is not None else ""

    def _finish_restore(self) -> None:
        self._timer.stop()
        if self._original is not None:
            self._clip.set_mime(self._original)


class SelectionInputSource(InputSource):
    name = "selection"

    def __init__(self) -> None:
        self._last: str | None = None

    def attach(self, capturer: SelectionCapturer) -> None:
        capturer.captured.connect(self._store)

    def _store(self, text: str) -> None:
        self._last = text

    def capture(self) -> InputPayload:
        if self._last is None:
            raise ProviderError("selection source: nothing captured yet")
        return InputPayload(kind="text", text=self._last)
```

注意:恢复操作会触发 `QClipboard.dataChanged`,但不影响本状态机(轮询只读 text)。

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_selection.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/inputs/selection.py tests/desktop/test_selection.py
git commit -m "feat: selection capture with immediate clipboard restore"
```

---

### Task 7: 托盘 + VerbaApp 组装 + 入口脚本

**Files:**
- Create: `src/verba/desktop/outputs/tray.py`, `src/verba/desktop/app.py`
- Modify: `src/verba/__init__.py`(可选,加版本常量;不需要则跳过)
- Test: `tests/desktop/test_app.py`(新建)

**Interfaces:**
- Consumes: 全部前述产物;`Pipeline`/`PipelineAction`/`ServiceRegistry`/`InputSourceRegistry`/`OutputHub`/`TTLCache`/`load_config`
- Produces:
  - `class TrayOutputHandler(QSystemTrayIcon)`:信号 `action_translate = Signal()`, `action_input = Signal()`, `action_settings = Signal()`, `action_quit = Signal()`
  - `def select_default_provider(registry: ServiceRegistry[BaseTranslator], priority: list[str]) -> str`:返回 priority 中第一个 `is_available()` 的 provider 名;全不可用返回 priority[0]
  - `def describe_error(exc: BaseException) -> str`:按错误树映射中文提示:`ProviderNotAvailable`→"服务不可用(缺少凭据?)"、`QuotaExceeded`→"请求超限,请稍后再试"、`NetworkError`→"网络错误,请检查连接"、`HttpError`→"HTTP {status_code}: {message}"(utils/http.py:14,独立错误树)、其余→str(exc)
  - `class VerbaApp(QObject)`:构造 `VerbaApp(config: AppConfig) -> None`(**普通 QObject,不继承 QApplication** —— 测试复用 pytest-qt 的 QApplication,避免双实例崩溃);公开属性 `popup`/`input_window`/`tray`/`worker`/`hotkeys`/`selection_capturer`;方法 `_run_selection()`、`_open_input()`
  - `def create_app(config: AppConfig) -> VerbaApp`;`def main(argv: list[str] | None = None) -> int`(创建 QApplication + VerbaApp + exec)
  - 划词动作:`PipelineAction(name="selection", input_source="selection", translator_provider=..., target_lang=config.desktop.default_target)`
  - **渲染路径**:pipeline 内 `OutputHub` 不注册 GUI handler(防 worker 线程跨线程操作 widget);worker `finished_ok` → 主线程 `popup.show_result(...)`
  - provider 注册:Task 7 只注册 echo;Task 8 在 `_build_translators` 里加 google,Task 9 加 deepl/baidu

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from verba.config.schema import AppConfig
from verba.core.registry import ServiceRegistry
from verba.desktop.app import VerbaApp, describe_error, select_default_provider
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.providers.demo import EchoTranslator
from verba.providers.errors import (
    NetworkError,
    ProviderNotAvailable,
    QuotaExceeded,
)
from verba.utils.http import HttpError


class UnavailableTranslator(BaseTranslator):
    meta = ProviderMeta(name="dead", version="0.1.0")

    def is_available(self) -> bool:
        return False

    def translate(self, request):
        raise AssertionError("never called")


def test_select_default_provider_skips_unavailable() -> None:
    registry: ServiceRegistry[BaseTranslator] = ServiceRegistry()
    registry.register("dead", UnavailableTranslator())
    registry.register("echo", EchoTranslator())
    assert select_default_provider(registry, ["dead", "echo"]) == "echo"


def test_select_default_provider_falls_back() -> None:
    registry: ServiceRegistry[BaseTranslator] = ServiceRegistry()
    registry.register("dead", UnavailableTranslator())
    assert select_default_provider(registry, ["dead"]) == "dead"


def test_describe_error_maps_error_trees() -> None:
    assert "缺少凭据" in describe_error(ProviderNotAvailable("x"))
    assert "超限" in describe_error(QuotaExceeded("x"))
    assert "网络" in describe_error(NetworkError("x"))
    assert "HTTP 429" in describe_error(HttpError(429, "rate limited"))
    assert "boom" in describe_error(ValueError("boom"))


def test_app_builds_and_tray_exists(qtbot) -> None:
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    assert app.tray is not None
    assert app.tray.contextMenu() is not None  # offscreen 无系统托盘,不能断言 isVisible
    assert app.input_window is not None


def test_app_selection_flows_to_popup(qtbot) -> None:
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    app.selection_capturer.captured.emit("selected word")
    qtbot.waitUntil(lambda: app.popup.isVisible(), timeout=3000)
    assert "selected word" in app.popup.toPlainText()


def test_app_input_flows_to_popup(qtbot) -> None:
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    app.input_window.setText("你好")
    app.input_window.submit()
    qtbot.waitUntil(lambda: app.popup.isVisible(), timeout=3000)
    assert "你好" in app.popup.toPlainText()
```

(离线环境 `QSystemTrayIcon.isVisible()` 恒 False(offscreen 无系统托盘),故断言 contextMenu 存在;`isVisible` 断言仅真机清单。)`

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_app.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现**

`src/verba/desktop/outputs/tray.py`:

```python
"""System tray icon with the main menu."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayOutputHandler(QSystemTrayIcon):
    action_translate = Signal()
    action_input = Signal()
    action_settings = Signal()
    action_quit = Signal()

    def __init__(self, parent=None) -> None:
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
```

`src/verba/desktop/app.py`:

```python
"""VerbaApp: assemble config, pipeline, hotkeys, tray and windows.

Plain QObject (NOT a QApplication subclass): tests reuse pytest-qt's
QApplication without clashing. main() owns the QApplication.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QPoint
from PySide6.QtWidgets import QApplication

from verba.config.loader import load_config
from verba.config.schema import AppConfig
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import ServiceRegistry
from verba.desktop.hotkeys import (
    HOTKEY_INPUT_ID,
    HOTKEY_SELECTION_ID,
    HotkeyManager,
    create_hotkey_manager,
    parse_hotkey,
)
from verba.desktop.inputs.manual import ManualInputSource
from verba.desktop.inputs.selection import SelectionCapturer, SelectionInputSource
from verba.desktop.outputs.tray import TrayOutputHandler
from verba.desktop.workers import PipelineWorker
from verba.desktop.windows.inputbox import InputWindow
from verba.desktop.windows.popup import ResultPopup
from verba.inputs.base import InputSourceRegistry
from verba.outputs.base import OutputHub
from verba.providers.base import BaseTranslator
from verba.providers.demo import EchoTranslator
from verba.providers.errors import NetworkError, ProviderNotAvailable, QuotaExceeded
from verba.utils.cache import TTLCache
from verba.utils.http import HttpError
from verba.utils.log import setup_logging

log = logging.getLogger(__name__)

PROVIDER_PRIORITY = ["google", "deepl", "baidu", "echo"]


def select_default_provider(
    registry: ServiceRegistry[BaseTranslator], priority: list[str]
) -> str:
    for name in priority:
        try:
            if registry.get(name).is_available():
                return name
        except Exception:  # noqa: BLE001 - unknown provider in priority list
            continue
    return priority[0]


def describe_error(exc: BaseException) -> str:
    """Map the two independent error trees to Chinese user-facing text."""
    if isinstance(exc, ProviderNotAvailable):
        return "服务不可用(缺少凭据?)"
    if isinstance(exc, QuotaExceeded):
        return "请求超限,请稍后再试"
    if isinstance(exc, NetworkError):
        return "网络错误,请检查连接"
    if isinstance(exc, HttpError):
        return f"HTTP {exc.status_code}: {exc.message}"
    return str(exc)


class VerbaApp(QObject):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._last_original: str | None = None

        self.popup = ResultPopup(config.desktop)
        self.input_window = InputWindow()
        self.manual_source = ManualInputSource()
        self.manual_source.attach(self.input_window)
        self.selection_capturer = SelectionCapturer()
        self.selection_source = SelectionInputSource()
        self.selection_source.attach(self.selection_capturer)

        self.translators = self._build_translators()

        inputs = InputSourceRegistry()
        inputs.register(self.selection_source)
        inputs.register(self.manual_source)

        self.pipeline = Pipeline(
            translators=self.translators,
            inputs=inputs,
            outputs=OutputHub(),  # GUI 渲染走 Qt signal,不走 pipeline 派发
            cache=TTLCache(
                ttl_seconds=config.cache.ttl_seconds,
                max_entries=config.cache.max_entries,
            ),
        )
        self.worker = PipelineWorker(self.pipeline)
        self.worker.finished_ok.connect(self._on_worker_ok)
        self.worker.failed.connect(self._on_worker_failed)

        self.hotkeys = create_hotkey_manager(self)
        self._bind_hotkeys()

        self.tray = TrayOutputHandler(self)
        self.tray.action_translate.connect(self._run_selection)
        self.tray.action_input.connect(self._open_input)
        self.tray.action_settings.connect(self._on_tray_settings)
        self.tray.action_quit.connect(QApplication.instance().quit)

        self.selection_capturer.captured.connect(self._on_selection_captured)
        self.input_window.submitted.connect(self._on_input_submitted)

    # -- wiring ---------------------------------------------------------------

    def _build_translators(self) -> ServiceRegistry[BaseTranslator]:
        registry: ServiceRegistry[BaseTranslator] = ServiceRegistry()
        registry.register("echo", EchoTranslator())
        # Task 8/9 在此追加:google / deepl / baidu 真实 provider,
        # 按 config.providers 的 enabled/api_key 条件注册。
        return registry

    def _bind_hotkeys(self) -> None:
        self.hotkeys.unbind(HOTKEY_SELECTION_ID)
        self.hotkeys.unbind(HOTKEY_INPUT_ID)
        self.hotkeys.bind(
            HOTKEY_SELECTION_ID, parse_hotkey(self._config.desktop.hotkey_selection)
        )
        self.hotkeys.bind(
            HOTKEY_INPUT_ID, parse_hotkey(self._config.desktop.hotkey_input)
        )
        self.hotkeys.hotkey_triggered.connect(self._on_hotkey)

    def _on_hotkey(self, hotkey_id: int) -> None:
        if hotkey_id == HOTKEY_SELECTION_ID:
            self._run_selection()
        elif hotkey_id == HOTKEY_INPUT_ID:
            self._open_input()

    def _run_selection(self) -> None:
        self.selection_capturer.start()

    def _open_input(self) -> None:
        self.input_window.open_at(self.cursor_pos())

    def _cursor_pos(self) -> QPoint:
        return QApplication.instance().cursor().pos() if QApplication.instance() else QPoint(0, 0)

    def cursor_pos(self) -> QPoint:  # public for tests to monkeypatch
        return self._cursor_pos()

    def _on_selection_captured(self, text: str) -> None:
        self._last_original = text
        self._submit_translation(self._selection_action())

    def _on_input_submitted(self, text: str) -> None:
        self._last_original = text
        action = PipelineAction(
            name="input",
            translator_provider=self._default_provider(),
            target_lang=self._config.desktop.default_target,
        )
        self.worker.submit(action, text=text)

    def _selection_action(self) -> PipelineAction:
        return PipelineAction(
            name="selection",
            input_source="selection",
            translator_provider=self._default_provider(),
            target_lang=self._config.desktop.default_target,
        )

    def _default_provider(self) -> str:
        return select_default_provider(self.translators, PROVIDER_PRIORITY)

    def _on_worker_ok(self, result) -> None:
        self.popup.show_result(
            result, self.cursor_pos(), original=self._last_original
        )
        self._last_original = None

    def _on_worker_failed(self, action_name: str, exc: BaseException) -> None:
        self.popup.show_error(describe_error(exc), self.cursor_pos())
        log.error("action %s failed: %s", action_name, exc)

    def _on_tray_settings(self) -> None:
        from verba.desktop.windows.settings import SettingsWindow

        self._settings_window = SettingsWindow(self._config, self.hotkeys)
        self._settings_window.config_changed.connect(self._reload_config)
        self._settings_window.show()

    def _reload_config(self, config: AppConfig) -> None:
        self._config = config
        self._bind_hotkeys()


def create_app(config: AppConfig) -> VerbaApp:
    return VerbaApp(config)


def main(argv: list[str] | None = None) -> int:
    setup_logging(logging.INFO)
    app = QApplication(argv if argv is not None else sys.argv)
    verba = create_app(load_config())
    verba.tray.show()
    return app.exec()
```

注意:
- `QApplication.instance().quit` 在测试里不可用(无实例退出语义)—— 托盘 quit 信号在测试中不触发,安全
- `_bind_hotkeys` 每次先 unbind 再 bind,支持设置页重绑(回滚见 Task 10)
- `cursor_pos()` 暴露为公开方法便于测试 monkeypatch

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_app.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/outputs/tray.py src/verba/desktop/app.py tests/desktop/test_app.py
git commit -m "feat: tray, app assembly and hotkey wiring"
```

---

### Task 8: HttpClient transport 注入 + GoogleFreeTranslator

**Files:**
- Modify: `src/verba/utils/http.py`(加可选 transport 参数)
- Modify: `src/verba/desktop/app.py`(`_build_translators` 注册 google)
- Create: `src/verba/providers/google.py`, `src/verba/providers/__init__.py` 更新导出
- Test: `tests/test_google_provider.py`(新建)

**Interfaces:**
- Consumes: `HttpClient`(utils/http.py:23),`ProviderConfig`/`HttpOptions`(config/schema.py)
- Produces:
  - `HttpClient(options: HttpOptions | None = None, transport: httpx.BaseTransport | None = None)`(向后兼容)
  - `HttpClient.get_json_any(url, headers=None, params=None) -> Any`:同 get_json 但接受任意 JSON 形状(数组等;Google 返回顶层数组,get_json 的 dict 校验会拒收)
  - `class GoogleFreeTranslator(BaseTranslator)`:meta name="google";`translate(request: TranslationRequest) -> TranslationResult`;`google_target_code(lang: Lang) -> str`(纯函数:zh-Hans→"zh-CN", zh-Hant→"zh-TW", en→"en", 其余 passthrough)

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import httpx
import pytest

from verba.config.schema import HttpOptions, ProviderConfig
from verba.models.translation import Lang, TranslationRequest
from verba.providers.google import GoogleFreeTranslator, google_target_code
from verba.utils.http import HttpClient


def test_google_target_code_mapping() -> None:
    assert google_target_code(Lang.ZH_HANS) == "zh-CN"
    assert google_target_code(Lang.ZH_HANT) == "zh-TW"
    assert google_target_code(Lang.EN) == "en"
    assert google_target_code(Lang.AUTO) == "auto"


def test_google_translate_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "translate.googleapis.com" in str(request.url)
        body = [[["你好，世界", "Hello world", None, None]], None, "en", None]
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    result = provider.translate(
        TranslationRequest(text="Hello world", target=Lang.ZH_HANS)
    )
    assert result.text == "你好，世界"
    assert result.detected_source == Lang.EN
    assert result.provider == "google"


def test_google_translate_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    with pytest.raises(Exception) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, httpx.HTTPStatusError) or "503" in str(exc.value)
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/test_google_provider.py -v`
Expected: FAIL — ModuleNotFoundError: verba.providers.google

- [ ] **Step 3: 实现**

`src/verba/utils/http.py` 构造签名改为:

```python
    def __init__(
        self,
        options: HttpOptions | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        opts = options or HttpOptions()
        self._options = opts
        self._client = httpx.Client(
            timeout=opts.timeout,
            headers={"User-Agent": opts.user_agent},
            follow_redirects=True,
            transport=transport,
        )

    def get_json_any(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Like get_json but accepts any JSON shape (arrays, scalars).

        Google's free endpoint returns a top-level array, which the
        ``isinstance(data, dict)`` check in get_json would reject.
        """
        try:
            response = self._client.get(url, headers=headers, params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise self._map_error(exc) from exc
        except httpx.HTTPError as exc:
            raise NetworkError(str(exc)) from exc
        return response.json()
```

(import 加 `Any` 已存在:`from typing import Any` http.py:5。)

`src/verba/providers/google.py`:

```python
"""Free Google Translate endpoint (translate.googleapis.com), no API key.

Unofficial endpoint; works without credentials. Fine for a personal tool.
"""

from __future__ import annotations

from verba.config.schema import HttpOptions, ProviderConfig
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.utils.http import HttpClient

_URL = "https://translate.googleapis.com/translate_a/single"

_LANG_CODES = {
    Lang.ZH_HANS: "zh-CN",
    Lang.ZH_HANT: "zh-TW",
    Lang.EN: "en",
    Lang.JA: "ja",
    Lang.KO: "ko",
    Lang.FR: "fr",
    Lang.DE: "de",
    Lang.ES: "es",
    Lang.RU: "ru",
    Lang.PT: "pt",
    Lang.IT: "it",
}


def google_target_code(lang: Lang) -> str:
    if lang == Lang.AUTO:
        return "auto"
    return _LANG_CODES.get(lang, lang.value)


class GoogleFreeTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="google",
        version="0.1.0",
        capabilities=frozenset({"translate"}),
    )

    def __init__(self, config: ProviderConfig, http: HttpClient) -> None:
        self._config = config
        self._http = http

    def is_available(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResult:
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": google_target_code(request.target),
            "dt": "t",
            "q": request.text,
        }
        data = self._http.get_json_any(_URL, params=params)
        segments = data[0]
        parts: list[str] = []
        for seg in segments:
            parts.append(str(seg[0]))
        translated = "".join(parts)
        detected_raw = data[2] if len(data) > 2 else None
        detected = self._map_detected(detected_raw)
        return TranslationResult(
            text=translated,
            source=request.source,
            target=request.target,
            provider=self.meta.name,
            detected_source=detected,
        )

    @staticmethod
    def _map_detected(raw: str | None) -> Lang | None:
        if not raw:
            return None
        code = raw.lower()
        if code == "zh-cn":
            return Lang.ZH_HANS
        for lang in Lang:
            if lang != Lang.AUTO and (lang.value.lower() == code or code == "zh-cn"):
                return lang
        return None
```

`_map_detected` 说明:zh-CN→ZH_HANS,zh-TW→ZH_HANT;其余按 code 小写匹配 Lang.value。上面循环版即可,注意 "zh-cn" 单独处理防止撞 Lang.ZH_HANT。若 mypy 对 `data[0]` 报 Any,translate 里已用 `parts: list[str]` + `str(seg[0])` 收敛。

`src/verba/desktop/app.py` 的 `_build_translators` 注册 google(Task 7 只注册 echo):

```python
    def _build_translators(self) -> ServiceRegistry[BaseTranslator]:
        from verba.providers.google import GoogleFreeTranslator
        from verba.utils.http import HttpClient

        registry: ServiceRegistry[BaseTranslator] = ServiceRegistry()
        registry.register("echo", EchoTranslator())
        http = HttpClient(self._config.http)
        google_cfg = self._config.providers.get("google")
        if google_cfg is None or google_cfg.enabled:
            registry.register("google", GoogleFreeTranslator(google_cfg or ProviderConfig(), http))
        return registry
```

import 加 `from verba.config.schema import AppConfig, ProviderConfig`(ProviderConfig 仅此处用)。

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/test_google_provider.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/utils/http.py src/verba/providers/google.py tests/test_google_provider.py
git commit -m "feat: google free translator provider"
```

---

### Task 9: DeepL + Baidu providers

**Files:**
- Create: `src/verba/providers/deepl.py`, `src/verba/providers/baidu.py`
- Modify: `src/verba/providers/__init__.py` 导出
- Test: `tests/test_remote_providers.py`(新建)

**Interfaces:**
- Produces:
  - `class DeepLTranslator(BaseTranslator)`:meta name="deepl";`is_available()` = `bool(config.api_key)`;`deepl_target_code(lang) -> str`(zh-Hans→"ZH", 其余大写)
  - `class BaiduTranslator(BaseTranslator)`:meta name="baidu";`is_available()` = `api_key 和 options["app_id"]` 都在;`baidu_target_code(lang) -> str`(zh-Hans→"zh", en→"en", 其余 passthrough)

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import hashlib
import httpx

from pydantic import SecretStr

from verba.config.schema import HttpOptions, ProviderConfig
from verba.models.translation import Lang, TranslationRequest
from verba.providers.baidu import BaiduTranslator, baidu_target_code
from verba.providers.deepl import DeepLTranslator, deepl_target_code
from verba.utils.http import HttpClient


def test_deepl_target_code() -> None:
    assert deepl_target_code(Lang.ZH_HANS) == "ZH"
    assert deepl_target_code(Lang.EN) == "EN"
    assert deepl_target_code(Lang.JA) == "JA"


def test_deepl_unavailable_without_key() -> None:
    provider = DeepLTranslator(ProviderConfig(), HttpClient(HttpOptions()))
    assert not provider.is_available()


def test_deepl_translate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "DeepL-Auth-Key secret"
        return httpx.Response(
            200,
            json={"translations": [{"detected_source_language": "EN", "text": "你好"}]},
        )

    transport = httpx.MockTransport(handler)
    config = ProviderConfig(api_key=SecretStr("secret"))
    provider = DeepLTranslator(config, HttpClient(HttpOptions(), transport))
    result = provider.translate(TranslationRequest(text="hi", target=Lang.ZH_HANS))
    assert result.text == "你好"
    assert result.detected_source == Lang.EN


def test_baidu_target_code() -> None:
    assert baidu_target_code(Lang.ZH_HANS) == "zh"
    assert baidu_target_code(Lang.EN) == "en"
    assert baidu_target_code(Lang.JA) == "jp"


def test_baidu_unavailable_without_keys() -> None:
    provider = BaiduTranslator(ProviderConfig(), HttpClient(HttpOptions()))
    assert not provider.is_available()


def test_baidu_translate_signs_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        assert params["appid"] == "app-1"
        assert params["q"] == "hi"
        assert params["from"] == "auto"
        assert params["to"] == "zh"
        signed = hashlib.md5(f"app-1hi{salt}secret".encode()).hexdigest()
        assert params["sign"] == signed
        return httpx.Response(
            200,
            json={"trans_result": [{"src": "hi", "dst": "你好"}]},
        )

    salt = "20260801"
    transport = httpx.MockTransport(handler)
    config = ProviderConfig(
        api_key=SecretStr("secret"), options={"app_id": "app-1", "salt": salt}
    )
    provider = BaiduTranslator(config, HttpClient(HttpOptions(), transport))
    result = provider.translate(TranslationRequest(text="hi", target=Lang.ZH_HANS))
    assert result.text == "你好"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/test_remote_providers.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现**

`src/verba/providers/deepl.py`:

```python
"""DeepL translation via the official API (api-free.deepl.com)."""

from __future__ import annotations

from pydantic import SecretStr

from verba.config.schema import ProviderConfig
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.utils.http import HttpClient

_URL = "https://api-free.deepl.com/v2/translate"


def deepl_target_code(lang: Lang) -> str:
    if lang == Lang.ZH_HANS:
        return "ZH"
    if lang == Lang.AUTO:
        return "EN"
    return lang.value.upper()


class DeepLTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="deepl", version="0.1.0", capabilities=frozenset({"translate"})
    )

    def __init__(self, config: ProviderConfig, http: HttpClient) -> None:
        self._config = config
        self._http = http

    def is_available(self) -> bool:
        return self._api_key() is not None

    def _api_key(self) -> str | None:
        key: SecretStr | None = self._config.api_key
        return key.get_secret_value() if key else None

    def translate(self, request: TranslationRequest) -> TranslationResult:
        key = self._api_key()
        if key is None:
            from verba.providers.errors import ProviderNotAvailable

            raise ProviderNotAvailable("deepl: missing API key")
        data = self._http.post_json(
            _URL,
            payload={},
            headers={"Authorization": f"DeepL-Auth-Key {key}"},
            params={
                "text": request.text,
                "target_lang": deepl_target_code(request.target),
            },
        )
        entries = data["translations"]
        first = entries[0]
        detected_raw = first.get("detected_source_language")
        detected = Lang(detected_raw.lower()) if detected_raw else None
        return TranslationResult(
            text=first["text"],
            source=request.source,
            target=request.target,
            provider=self.meta.name,
            detected_source=detected,
        )
```

`src/verba/providers/baidu.py`:

```python
"""Baidu translation API (fanyi-api.baidu.com). Requires app_id + secret."""

from __future__ import annotations

import hashlib
import time

from pydantic import SecretStr

from verba.config.schema import ProviderConfig
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.utils.http import HttpClient

_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"

_BAIDU_CODES = {
    Lang.ZH_HANS: "zh",
    Lang.ZH_HANT: "cht",
    Lang.JA: "jp",
    Lang.KO: "kor",
    Lang.FR: "fra",
    Lang.DE: "de",
    Lang.ES: "spa",
    Lang.RU: "ru",
    Lang.PT: "pt",
    Lang.IT: "it",
}


def baidu_target_code(lang: Lang) -> str:
    if lang == Lang.AUTO:
        return "auto"
    return _BAIDU_CODES.get(lang, lang.value)


class BaiduTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="baidu", version="0.1.0", capabilities=frozenset({"translate"})
    )

    def __init__(self, config: ProviderConfig, http: HttpClient) -> None:
        self._config = config
        self._http = http

    def is_available(self) -> bool:
        return self._app_id() is not None and self._api_key() is not None

    def _app_id(self) -> str | None:
        return self._config.options.get("app_id")

    def _api_key(self) -> str | None:
        key: SecretStr | None = self._config.api_key
        return key.get_secret_value() if key else None

    def translate(self, request: TranslationRequest) -> TranslationResult:
        app_id = self._app_id()
        secret = self._api_key()
        if app_id is None or secret is None:
            from verba.providers.errors import ProviderNotAvailable

            raise ProviderNotAvailable("baidu: missing app_id/api_key")
        salt = self._config.options.get("salt") or str(int(time.time()))
        sign = hashlib.md5(f"{app_id}{request.text}{salt}{secret}".encode()).hexdigest()
        data = self._http.get_json(
            _URL,
            params={
                "q": request.text,
                "from": "auto",
                "to": baidu_target_code(request.target),
                "appid": app_id,
                "salt": salt,
                "sign": sign,
            },
        )
        entries = data["trans_result"]
        text = "".join(entry["dst"] for entry in entries)
        return TranslationResult(
            text=text,
            source=request.source,
            target=request.target,
            provider=self.meta.name,
        )
```

`src/verba/providers/__init__.py` 追加导出:`BaiduTranslator`、`DeepLTranslator`、`GoogleFreeTranslator`。

`src/verba/desktop/app.py` 的 `_build_translators` 补 deepl/baidu(google 在 Task 8):

```python
    def _build_translators(self) -> ServiceRegistry[BaseTranslator]:
        from verba.providers.baidu import BaiduTranslator
        from verba.providers.deepl import DeepLTranslator
        from verba.providers.google import GoogleFreeTranslator
        from verba.utils.http import HttpClient

        registry: ServiceRegistry[BaseTranslator] = ServiceRegistry()
        registry.register("echo", EchoTranslator())
        http = HttpClient(self._config.http)
        for name, cls in (
            ("google", GoogleFreeTranslator),
            ("deepl", DeepLTranslator),
            ("baidu", BaiduTranslator),
        ):
            cfg = self._config.providers.get(name)
            if cfg is None or cfg.enabled:
                registry.register(name, cls(cfg or ProviderConfig(), http))
        return registry
```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/test_remote_providers.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/providers/deepl.py src/verba/providers/baidu.py src/verba/providers/__init__.py tests/test_remote_providers.py
git commit -m "feat: deepl and baidu providers"
```

---

### Task 10: 设置页 + 热键重绑

**Files:**
- Create: `src/verba/desktop/windows/settings.py`
- Test: `tests/desktop/test_settings.py`(新建)

**Interfaces:**
- Consumes: `AppConfig`、`HotkeyManager`、`parse_hotkey`
- Produces:
  - `class SettingsWindow(QWidget)`:信号 `config_changed = Signal(object)`(AppConfig);构造 `SettingsWindow(config: AppConfig, hotkeys: HotkeyManager, parent=None)`;字段:两个热键输入框、目标语言下拉;`save() -> bool`:校验热键格式 → `hotkeys.rebind` 两个热键(失败回滚旧绑定)→ 写 TOML 到 `user_config_path()` → emit config_changed
  - `save() -> bool`:False 表示校验失败(不关闭窗口)

- [ ] **Step 1: 写失败测试**

```python
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tomllib
from pathlib import Path

import pytest

from verba.config.schema import AppConfig
from verba.desktop.hotkeys import HotkeyManager
from verba.desktop.windows.settings import SettingsWindow


def test_settings_loads_current_values(qtbot) -> None:
    config = AppConfig(desktop={"hotkey_selection": "Ctrl+Shift+A"})
    window = SettingsWindow(config, HotkeyManager())
    qtbot.addWidget(window)
    assert window.hotkey_selection_text() == "Ctrl+Shift+A"


def test_settings_rejects_bad_hotkey(qtbot) -> None:
    window = SettingsWindow(AppConfig(), HotkeyManager())
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("no-modifier")
    assert window.save() is False


def test_settings_save_emits_and_writes_toml(qtbot, tmp_path: Path, monkeypatch) -> None:
    from verba.config import loader

    monkeypatch.setattr(loader, "user_config_path", lambda: tmp_path / "config.toml")
    window = SettingsWindow(AppConfig(), HotkeyManager())
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("Ctrl+Shift+Y")
    with qtbot.waitSignal(window.config_changed, timeout=1000) as blocker:
        assert window.save() is True
    saved = tomllib.loads((tmp_path / "config.toml").read_text("utf-8"))
    assert saved["desktop"]["hotkey_selection"] == "Ctrl+Shift+Y"


def test_settings_save_rebinds_hotkeys(qtbot) -> None:
    from verba.desktop.hotkeys import HOTKEY_SELECTION_ID, parse_hotkey

    manager = HotkeyManager()
    calls: list[tuple[int, object]] = []
    manager.rebind = lambda hotkey_id, spec: calls.append((hotkey_id, spec))  # type: ignore[method-assign]  # ignore: test stub
    window = SettingsWindow(AppConfig(), manager)
    qtbot.addWidget(window)
    window.set_hotkey_selection_text("Ctrl+Shift+Z")
    assert window.save() is True
    assert (HOTKEY_SELECTION_ID, parse_hotkey("Ctrl+Shift+Z")) in calls
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/desktop/test_settings.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现**

`src/verba/desktop/windows/settings.py`:

```python
"""Settings window: hotkeys, default provider, target language."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from verba.config.loader import user_config_path
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
        self._target_lang.setCurrentIndex(
            max(0, self._target_lang.findData(config.desktop.default_target))
        )

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
                        "default_target": self._target_lang.currentData(),
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
        path: Path = user_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'[desktop]\n'
            f'hotkey_selection = "{config.desktop.hotkey_selection}"\n'
            f'hotkey_input = "{config.desktop.hotkey_input}"\n'
            f'default_target = "{config.desktop.default_target.value}"\n'
            f'popup_auto_close_ms = {config.desktop.popup_auto_close_ms}\n'
            f'click_to_copy = {"true" if config.desktop.click_to_copy else "false"}\n',
            encoding="utf-8",
        )
```

(provider 选择不在设置页暴露:默认 provider 由 `select_default_provider` 按 PROVIDER_PRIORITY + `is_available()` 自动决定,设置页仅管理热键与目标语言。)

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/desktop/test_settings.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add src/verba/desktop/windows/settings.py tests/desktop/test_settings.py
git commit -m "feat: settings window with hotkey rebind"
```

---

### Task 11: 真机验证清单 + 文档

**Files:**
- Create: `docs/windows-verification.md`
- Modify: `README.md`

- [ ] **Step 1: 写验证清单**

`docs/windows-verification.md`(Windows 真机手动清单):

```markdown
# Windows 真机验证清单

前置:`uv sync`,`uv run verba-desktop`(或打包后 exe)。

## 启动
- [ ] 托盘图标出现,菜单四项(划词翻译/输入翻译/设置/退出)
- [ ] 日志无异常;第二次启动时提示热键占用(可选,可关首个实例验证)

## 划词翻译
- [ ] 任意编辑器选中文字,按 Ctrl+Alt+D → 浮窗出现,显示原文+译文
- [ ] 浮窗定位在鼠标附近,不超出屏幕
- [ ] 点击浮窗任意处 → 剪贴板变为译文,按钮显示"已复制"
- [ ] 翻译期间用户复制其他内容 → 不被覆盖(剪贴板立即恢复)
- [ ] 剪贴板原内容(如图片)在划词后被完整还原
- [ ] 空选区(未选中)按热键 → 无浮窗
- [ ] 大选区(如整页 Word)等待 < 2s 有结果(重试路径)
- [ ] Esc / 点击外部 → 浮窗关闭;固定按钮 → 不再自动关闭,可移开

## 输入翻译
- [ ] Ctrl+Alt+L → 输入窗出现在鼠标处,Enter 翻译,结果浮窗在其下方
- [ ] Esc 关闭输入窗,不翻译

## 托盘
- [ ] 托盘"划词翻译"等效热键;"退出"干净退出

## 设置
- [ ] 改热键保存 → TOML 落盘、立即生效(旧热键失效)
- [ ] 非法热键 → 校验提示,不落盘

## 已知限制
- 目标应用以管理员权限运行 → 模拟复制无效(无解,Windows 权限模型)
```

- [ ] **Step 2: README 更新**

`README.md` 加:
- 功能清单:划词翻译(Ctrl+Alt+D)、输入翻译(Ctrl+Alt+L)、托盘、设置
- 快速开始:`uv sync && uv run verba-desktop`
- 配置示例(`~/.config/verba/config.toml`):hotkey、目标语言、provider key
  (`BOBPOT_API_KEY_BAIDU` / `BOBPOT_API_KEY_DEEPL` 环境变量)
- 已知限制:UAC 提权窗口、Google 接口稳定性
- 链接 `docs/windows-verification.md`

- [ ] **Step 3: 回归 + 提交**

Run: `uv run pytest && uv run mypy`
Expected: 全绿

```bash
git add docs/windows-verification.md README.md
git commit -m "docs: windows verification checklist and desktop quickstart"
```

---

## 里程碑映射

- **M1(desktop 骨架+输入翻译)**:Task 1-5,7
- **M2(划词)**:Task 6
- **M3(真实服务+设置页)**:Task 8,9,10
- **验证**:Task 11(Windows 真机手动)
