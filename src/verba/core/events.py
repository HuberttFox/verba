"""Synchronous in-process event bus decoupling pipeline stages."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

from verba.inputs.base import InputPayload
from verba.models.ocr import OCRResult
from verba.models.translation import TranslationResult

log = logging.getLogger(__name__)


class Event:
    """Marker base for all pipeline events."""


@dataclass(frozen=True, eq=False)
class InputCaptured(Event):
    payload: InputPayload


@dataclass(frozen=True, eq=False)
class OcrCompleted(Event):
    result: OCRResult


@dataclass(frozen=True, eq=False)
class TranslationCompleted(Event):
    result: TranslationResult


@dataclass(frozen=True, eq=False)
class PipelineFailed(Event):
    action_name: str
    error: Exception


class EventBus:
    """Publish/subscribe bus. Subscribers are called synchronously.

    Handler errors are isolated (logged, not propagated) so one bad
    subscriber never breaks the pipeline.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event] | None, list[Callable[[Event], None]]] = {}
        self._lock = Lock()

    def subscribe(
        self,
        handler: Callable[[Event], None],
        event_type: type[Event] | None = None,
    ) -> None:
        """Register *handler*. ``event_type=None`` subscribes to all events."""
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(
        self,
        handler: Callable[[Event], None],
        event_type: type[Event] | None = None,
    ) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event: Event) -> None:
        """Deliver *event* to subscribers of its type and to wildcard (*) ones."""
        with self._lock:
            exact = self._handlers.get(type(event), [])
            wildcard = self._handlers.get(None, [])
        for handler in exact + wildcard:
            try:
                handler(event)
            except Exception:
                log.exception("event handler %r failed on %s", handler, type(event).__name__)
