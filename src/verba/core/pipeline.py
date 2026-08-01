"""Pipeline orchestration: input -> (OCR) -> translate -> present."""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict

from verba.core.events import (
    EventBus,
    InputCaptured,
    OcrCompleted,
    PipelineFailed,
    TranslationCompleted,
)
from verba.core.registry import ServiceRegistry
from verba.inputs.base import InputPayload, InputSourceRegistry
from verba.models.image import ImageSource
from verba.models.ocr import OCRRequest
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.outputs.base import OutputHub
from verba.providers.base import BaseOCR, BaseTranslator
from verba.providers.errors import ProviderError, ProviderNotAvailable
from verba.utils.cache import TTLCache

log = logging.getLogger(__name__)


class PipelineAction(BaseModel):
    """Declarative description of one user action (translation, OCR translate...)."""

    model_config = ConfigDict(frozen=True)

    name: str
    input_source: str | None = None
    needs_ocr: bool = False
    ocr_provider: str | None = None
    translator_provider: str | None = None
    target_lang: Lang = Lang.ZH_HANS
    context: str | None = None
    output: str | None = None


class Pipeline:
    """Composes inputs, providers and outputs behind one run() call.

    Headless by design: it knows nothing about GUI. A desktop app builds
    a Pipeline, subscribes to its EventBus and routes events to widgets.
    """

    def __init__(
        self,
        translators: ServiceRegistry[BaseTranslator],
        ocr: ServiceRegistry[BaseOCR] | None = None,
        inputs: InputSourceRegistry | None = None,
        outputs: OutputHub | None = None,
        bus: EventBus | None = None,
        cache: TTLCache[TranslationResult] | None = None,
    ) -> None:
        self.translators = translators
        self.ocr = ocr or ServiceRegistry()
        self.inputs = inputs or InputSourceRegistry()
        self.outputs = outputs or OutputHub()
        self.bus = bus or EventBus()
        self.cache = cache

    def run(
        self,
        action: PipelineAction,
        *,
        text: str | None = None,
        image: ImageSource | None = None,
    ) -> TranslationResult:
        """Execute an action end-to-end.

        - ``text`` / ``image`` override the configured input source.
        - Publishing is event-driven; failures also surface as PipelineFailed.
        """
        try:
            payload = self._capture(action, text, image)
            self.bus.publish(InputCaptured(payload))

            source_text = payload.text or ""
            if action.needs_ocr:
                source_text = self._run_ocr(action, payload)

            result = self._translate(action, source_text)
            self.bus.publish(TranslationCompleted(result))
            self.outputs.present_all(result, only=action.output)
            return result
        except Exception as exc:
            self.bus.publish(PipelineFailed(action.name, exc))
            raise

    def translate_text(
        self,
        text: str,
        target_lang: Lang,
        source: Lang = Lang.AUTO,
        provider: str | None = None,
        context: str | None = None,
    ) -> TranslationResult:
        """Convenience for pure text translation (no input source needed)."""
        return self.run(
            PipelineAction(
                name="inline",
                translator_provider=provider,
                target_lang=target_lang,
                context=context,
            ),
            text=text,
        )

    def _capture(
        self, action: PipelineAction, text: str | None, image: ImageSource | None
    ) -> InputPayload:
        if text is not None:
            return InputPayload(kind="text", text=text)
        if image is not None:
            return InputPayload(kind="image", image=image)
        if action.input_source is None:
            raise ProviderError(f"action '{action.name}' has no input source")
        source = self.inputs.get(action.input_source)
        return source.capture()

    def _run_ocr(self, action: PipelineAction, payload: InputPayload) -> str:
        provider_name = action.ocr_provider or self._default_ocr()
        provider = self.ocr.get(provider_name)
        self._ensure_available(provider, provider_name)
        if payload.image is None:
            raise ProviderError(f"OCR action '{action.name}' received no image")
        request = OCRRequest(image=payload.image)
        result = provider.recognize(request)
        self.bus.publish(OcrCompleted(result))
        log.info("OCR by %s: %d chars", provider_name, len(result.text))
        return result.text

    def _translate(self, action: PipelineAction, source_text: str) -> TranslationResult:
        provider_name = action.translator_provider or self._default_translator()
        provider = self.translators.get(provider_name)
        self._ensure_available(provider, provider_name)

        if not source_text.strip():
            raise ProviderError(f"action '{action.name}' produced empty text")

        cache_key = self._cache_key(provider_name, action, source_text)
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                log.info("translation cache hit (%s)", provider_name)
                return cached.model_copy(update={"from_cache": True})

        request = TranslationRequest(
            text=source_text,
            target=action.target_lang,
            context=action.context,
        )
        start = time.monotonic()
        result = provider.translate(request)
        result = result.model_copy(
            update={"duration_ms": (time.monotonic() - start) * 1000}
        )
        if self.cache is not None:
            self.cache.set(cache_key, result)
        log.info(
            "translated %d chars via %s (%s -> %s)",
            len(source_text),
            provider_name,
            request.source.value,
            request.target.value,
        )
        return result

    def _default_translator(self) -> str:
        names = self.translators.names()
        if not names:
            raise ProviderError("no translator providers registered")
        return names[0]

    def _default_ocr(self) -> str:
        names = self.ocr.names()
        if not names:
            raise ProviderError("no OCR providers registered")
        return names[0]

    @staticmethod
    def _ensure_available(provider: Any, name: str) -> None:
        if not provider.is_available():
            raise ProviderNotAvailable(
                f"provider '{name}' is unavailable (missing credentials?)"
            )

    @staticmethod
    def _cache_key(
        provider_name: str, action: PipelineAction, source_text: str
    ) -> str:
        return f"{provider_name}|{action.target_lang.value}|{source_text}"
