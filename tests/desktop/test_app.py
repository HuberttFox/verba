from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

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

    def translate(self, request):  # type: ignore[no-untyped-def]  # ignore: brief-verbatim demo stub
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


def test_app_builds_and_tray_exists(qtbot: QtBot) -> None:
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    assert app.tray is not None
    assert app.tray.contextMenu() is not None  # offscreen 无系统托盘,不能断言 isVisible
    assert app.input_window is not None


def test_app_selection_flows_to_popup(qtbot: QtBot) -> None:
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    app.selection_capturer.captured.emit("selected word")
    qtbot.waitUntil(lambda: app.popup.isVisible(), timeout=3000)
    assert "selected word" in app.popup.toPlainText()


def test_app_input_flows_to_popup(qtbot: QtBot) -> None:
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    app.input_window.setText("你好")
    app.input_window.submit()
    qtbot.waitUntil(lambda: app.popup.isVisible(), timeout=3000)
    assert "你好" in app.popup.toPlainText()


def test_app_survives_hotkey_conflict(qtbot: QtBot, monkeypatch: MonkeyPatch) -> None:
    from verba.desktop.hotkeys import HotkeyError, HotkeySpec

    def broken_bind(self: object, hotkey_id: int, spec: HotkeySpec) -> None:
        raise HotkeyError("RegisterHotKey failed for id=1 (in use?)")

    monkeypatch.setattr("verba.desktop.app.HotkeyManager.bind", broken_bind)
    app = VerbaApp(AppConfig())  # 不得抛异常
    qtbot.addWidget(app.popup)
    assert app.tray is not None


def test_app_hotkey_conflict_shows_tray_message(qtbot: QtBot, monkeypatch: MonkeyPatch) -> None:
    from verba.desktop.hotkeys import HotkeyError, HotkeySpec

    def broken_bind(self: object, hotkey_id: int, spec: HotkeySpec) -> None:
        raise HotkeyError("RegisterHotKey failed for id=1 (in use?)")

    monkeypatch.setattr("verba.desktop.app.HotkeyManager.bind", broken_bind)
    messages: list[str] = []

    def fake_show_message(
        self: object, title: str, body: str, icon: object = None, ms: int = 0
    ) -> None:
        messages.append(body)

    monkeypatch.setattr("verba.desktop.app.TrayOutputHandler.showMessage", fake_show_message)
    app = VerbaApp(AppConfig())
    qtbot.addWidget(app.popup)
    assert any("热键注册失败" in m for m in messages)
