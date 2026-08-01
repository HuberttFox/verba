from __future__ import annotations

import pytest

from verba.core.events import (
    InputCaptured,
    OcrCompleted,
    PipelineFailed,
    TranslationCompleted,
)
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import ServiceRegistry
from verba.inputs.base import InputPayload, InputSource, InputSourceRegistry
from verba.models.image import ImageSource
from verba.models.ocr import OCRRequest, OCRResult
from verba.models.translation import Lang, TranslationResult
from verba.outputs.base import OutputHandler, OutputHub
from verba.providers.base import BaseOCR, BaseTranslator
from verba.providers.demo import EchoOCR, EchoTranslator
from verba.utils.cache import TTLCache


class RecordingHandler(OutputHandler):
    name = "recorder"
    results: list[TranslationResult] = []

    def present(self, result: TranslationResult) -> None:
        RecordingHandler.results.append(result)


class ManualSource(InputSource):
    name = "manual"

    def __init__(self, text: str) -> None:
        self.text = text

    def capture(self) -> InputPayload:
        return InputPayload(kind="text", text=self.text)


class FixedOCR(BaseOCR):
    meta = EchoOCR.meta

    def __init__(self, text: str) -> None:
        self.text = text

    def recognize(self, request: OCRRequest) -> OCRResult:
        return OCRResult(text=self.text, provider=self.meta.name)


def make_pipeline(*, with_cache: bool = True) -> Pipeline:
    translators: ServiceRegistry[BaseTranslator] = ServiceRegistry()
    translators.register("echo", EchoTranslator())
    ocr: ServiceRegistry[BaseOCR] = ServiceRegistry()
    ocr.register("fixed", FixedOCR("ocr text"))
    outputs = OutputHub()
    outputs.register(RecordingHandler())
    return Pipeline(
        translators=translators,
        ocr=ocr,
        inputs=InputSourceRegistry(),
        outputs=outputs,
        cache=TTLCache() if with_cache else None,
    )


def test_text_translation_end_to_end() -> None:
    pipeline = make_pipeline()
    result = pipeline.translate_text("hello", Lang.ZH_HANS, provider="echo")

    assert result.provider == "echo"
    assert "hello" in result.text
    assert result.target == Lang.ZH_HANS
    assert len(RecordingHandler.results) == 1


def test_ocr_translation_path() -> None:
    pipeline = make_pipeline()
    events: list[object] = []
    pipeline.bus.subscribe(events.append, OcrCompleted)
    pipeline.bus.subscribe(events.append, InputCaptured)

    result = pipeline.run(
        PipelineAction(
            name="screen", needs_ocr=True, ocr_provider="fixed",
            translator_provider="echo",
        ),
        image=ImageSource(data=b"fake-png"),
    )

    assert "ocr text" in result.text
    assert any(isinstance(e, InputCaptured) for e in events)
    assert any(isinstance(e, OcrCompleted) for e in events)


def test_cache_hit_marks_from_cache() -> None:
    pipeline = make_pipeline()
    first = pipeline.translate_text("hello", Lang.ZH_HANS, provider="echo")
    assert not first.from_cache

    second = pipeline.translate_text("hello", Lang.ZH_HANS, provider="echo")
    assert second.from_cache
    assert second.text == first.text


def test_failure_publishes_pipeline_failed() -> None:
    pipeline = make_pipeline()
    failed: list[PipelineFailed] = []
    pipeline.bus.subscribe(
        lambda event: failed.append(event) if isinstance(event, PipelineFailed) else None,
        PipelineFailed,
    )

    with pytest.raises(Exception):
        pipeline.translate_text("", Lang.ZH_HANS, provider="echo")

    assert len(failed) == 1
    assert failed[0].action_name == "inline"


def test_input_source_resolution() -> None:
    pipeline = make_pipeline()
    pipeline.inputs.register(ManualSource("from source"))
    result = pipeline.run(
        PipelineAction(name="src", input_source="manual", translator_provider="echo")
    )
    assert "from source" in result.text
