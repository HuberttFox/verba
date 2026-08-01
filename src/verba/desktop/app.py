"""VerbaApp: assemble config, pipeline, hotkeys, tray and windows.

Plain QObject (NOT a QApplication subclass): tests reuse pytest-qt's
QApplication without clashing. main() owns the QApplication.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from verba.config.loader import load_config
from verba.config.schema import AppConfig, ProviderConfig
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import ServiceRegistry
from verba.desktop.hotkeys import (
    HOTKEY_INPUT_ID,
    HOTKEY_SELECTION_ID,
    HotkeyError,
    HotkeyManager,
    create_hotkey_manager,
    parse_hotkey,
)
from verba.desktop.inputs.manual import ManualInputSource
from verba.desktop.inputs.selection import SelectionCapturer, SelectionInputSource
from verba.desktop.outputs.popup_handler import QPopupOutputHandler
from verba.desktop.outputs.tray import TrayOutputHandler
from verba.desktop.workers import PipelineWorker
from verba.desktop.windows.inputbox import InputWindow
from verba.desktop.windows.popup import ResultPopup
from verba.inputs.base import InputSourceRegistry
from verba.models.translation import TranslationResult
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
        self.hotkeys.hotkey_triggered.connect(self._on_hotkey)  # 只连一次,reload 不重复

        self.tray = TrayOutputHandler(self)
        self.tray.action_translate.connect(self._run_selection)
        self.tray.action_input.connect(self._open_input)
        self.tray.action_settings.connect(self._on_tray_settings)
        app = QApplication.instance()
        assert app is not None  # VerbaApp is only constructed under a QApplication
        self.tray.action_quit.connect(app.quit)

        self._bind_hotkeys_safe()  # tray 已建,冲突提示才能发气泡

        self.selection_capturer.captured.connect(self._on_selection_captured)
        self.input_window.submitted.connect(self._on_input_submitted)

        self._popup_handler = QPopupOutputHandler(
            self.popup, get_anchor=self.cursor_pos, get_original=lambda: self._last_original
        )

    # -- wiring ---------------------------------------------------------------

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

    def _bind_hotkeys(self) -> None:
        """Unbind-then-bind both hotkeys. Caller handles HotkeyError."""
        self.hotkeys.unbind(HOTKEY_SELECTION_ID)
        self.hotkeys.unbind(HOTKEY_INPUT_ID)
        self.hotkeys.bind(
            HOTKEY_SELECTION_ID, parse_hotkey(self._config.desktop.hotkey_selection)
        )
        self.hotkeys.bind(
            HOTKEY_INPUT_ID, parse_hotkey(self._config.desktop.hotkey_input)
        )

    def _bind_hotkeys_safe(self) -> None:
        """Startup/rebind path: on conflict, disable the hotkey + tray notice."""
        try:
            self._bind_hotkeys()
        except HotkeyError as exc:
            self.hotkeys.unbind(HOTKEY_SELECTION_ID)
            self.hotkeys.unbind(HOTKEY_INPUT_ID)
            self.tray.showMessage("verba", f"热键注册失败: {exc}", TrayOutputHandler.MessageIcon.Warning, 3000)

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
        return QCursor.pos()

    def cursor_pos(self) -> QPoint:  # public for tests to monkeypatch
        return self._cursor_pos()

    def _on_selection_captured(self, text: str) -> None:
        self._last_original = text
        self._submit_translation(self._selection_action())

    def _submit_translation(self, action: PipelineAction) -> None:
        self.worker.submit(action, text=self._last_original)

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

    def _on_worker_ok(self, result: TranslationResult) -> None:
        self._popup_handler.present(result)
        self._last_original = None

    def _on_worker_failed(self, action_name: str, exc: BaseException) -> None:
        self.popup.show_error(describe_error(exc), self.cursor_pos())
        log.error("action %s failed: %s", action_name, exc)

    def _on_tray_settings(self) -> None:
        from verba.desktop.windows.settings import (  # type: ignore[import-untyped]  # ignore: settings window ships in Task 10
            SettingsWindow,
        )

        self._settings_window = SettingsWindow(self._config, self.hotkeys)
        self._settings_window.config_changed.connect(self._reload_config)
        self._settings_window.show()

    def _reload_config(self, config: AppConfig) -> None:
        self._config = config
        self._bind_hotkeys_safe()


def create_app(config: AppConfig) -> VerbaApp:
    return VerbaApp(config)


def main(argv: list[str] | None = None) -> int:
    setup_logging(logging.INFO)
    app = QApplication(argv if argv is not None else sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关设置窗不退出;托盘退出是唯一出口
    verba = create_app(load_config())
    verba.tray.show()
    return app.exec()
