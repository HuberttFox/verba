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

    def run(self) -> None:
        action = self._action
        if action is None:
            return
        try:
            result = self._pipeline.run(action, text=self._text)
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - surfaced to UI
            self.failed.emit(action.name, exc)
