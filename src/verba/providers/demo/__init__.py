"""Demo stub providers. They validate the framework contracts without
touching any real service — replace them with real providers following
docs/providers.md."""

from verba.models.ocr import OCRRequest, OCRResult
from verba.models.translation import TranslationRequest, TranslationResult
from verba.providers.base import BaseOCR, BaseTranslator, ProviderMeta


class EchoTranslator(BaseTranslator):
    """Echoes the input back. Proves the translate path end-to-end."""

    meta = ProviderMeta(
        name="echo",
        version="0.1.0",
        capabilities=frozenset({"translate"}),
    )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(
            text=f"[{request.source.value}->{request.target.value}] {request.text}",
            source=request.source,
            target=request.target,
            provider=self.meta.name,
            alternatives=[request.text],
        )


class EchoOCR(BaseOCR):
    """Returns fixed mock text. Proves the OCR path end-to-end."""

    meta = ProviderMeta(
        name="echo-ocr",
        version="0.1.0",
        capabilities=frozenset({"ocr"}),
    )

    def recognize(self, request: OCRRequest) -> OCRResult:
        return OCRResult(
            text="verba mock ocr output",
            provider=self.meta.name,
            boxes=[],
        )
