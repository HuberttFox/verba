"""Core orchestration: event bus, provider registry, pipeline."""

from verba.core.events import (
    Event,
    EventBus,
    InputCaptured,
    OcrCompleted,
    PipelineFailed,
    TranslationCompleted,
)
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ServiceRegistry,
)

__all__ = [
    "DuplicateProviderError",
    "Event",
    "EventBus",
    "InputCaptured",
    "OcrCompleted",
    "Pipeline",
    "PipelineAction",
    "PipelineFailed",
    "ProviderNotFoundError",
    "ServiceRegistry",
    "TranslationCompleted",
]
