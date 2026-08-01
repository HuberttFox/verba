"""Reference handlers: console printing and log-based notification."""

from __future__ import annotations

import logging

from verba.models.translation import TranslationResult
from verba.outputs.base import OutputHandler

log = logging.getLogger(__name__)


class ConsoleOutputHandler(OutputHandler):
    """Prints the result to stdout (used by the CLI demo)."""

    name = "console"

    def present(self, result: TranslationResult) -> None:
        print(result.text)


class NotificationHandler(OutputHandler):
    """Writes the result to the framework log for external collection."""

    name = "notification"

    def present(self, result: TranslationResult) -> None:
        log.info(
            "translation result [%s %s->%s]: %s",
            result.provider,
            result.source.value,
            result.target.value,
            result.text,
        )
