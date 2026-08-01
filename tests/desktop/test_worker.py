from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from pytestqt.qtbot import QtBot

from verba.config.schema import DesktopOptions
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import ServiceRegistry
from verba.desktop.outputs.popup_handler import QPopupOutputHandler
from verba.desktop.workers import PipelineWorker
from verba.desktop.windows.popup import ResultPopup
from verba.models.image import ImageSource
from verba.models.translation import Lang, TranslationResult
from verba.providers.base import BaseTranslator


class FakePipeline(Pipeline):
    def __init__(self) -> None:
        super().__init__(ServiceRegistry[BaseTranslator]())

    def run(
        self,
        action: PipelineAction,
        *,
        text: str | None = None,
        image: ImageSource | None = None,
    ) -> TranslationResult:
        return TranslationResult(
            text="worker ok",
            source=Lang.AUTO,
            target=Lang.ZH_HANS,
            provider="fake",
        )


class FailingPipeline(Pipeline):
    def __init__(self) -> None:
        super().__init__(ServiceRegistry[BaseTranslator]())

    def run(
        self,
        action: PipelineAction,
        *,
        text: str | None = None,
        image: ImageSource | None = None,
    ) -> TranslationResult:
        raise ValueError("boom")


def test_worker_emits_success(qtbot: QtBot) -> None:
    worker = PipelineWorker(FakePipeline())
    with qtbot.waitSignal(worker.finished_ok, timeout=3000) as blocker:
        worker.submit(PipelineAction(name="t", translator_provider="fake"), text="hi")
    assert blocker.args[0].text == "worker ok"
    worker.wait()


def test_worker_emits_failure(qtbot: QtBot) -> None:
    worker = PipelineWorker(FailingPipeline())
    with qtbot.waitSignal(worker.failed, timeout=3000) as blocker:
        worker.submit(PipelineAction(name="t", translator_provider="fake"), text="hi")
    assert isinstance(blocker.args[1], ValueError)
    assert str(blocker.args[1]) == "boom"
    worker.wait()


def test_handler_renders_into_popup(qtbot: QtBot) -> None:
    popup = ResultPopup(DesktopOptions())
    qtbot.addWidget(popup)
    handler = QPopupOutputHandler(popup, get_anchor=lambda: QPoint(10, 10))
    result = TranslationResult(
        text="你好", source=Lang.AUTO, target=Lang.ZH_HANS, provider="echo"
    )
    handler.present(result)
    assert popup.isVisible()
    assert "你好" in popup.toPlainText()
