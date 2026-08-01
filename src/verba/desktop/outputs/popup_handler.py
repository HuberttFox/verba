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
