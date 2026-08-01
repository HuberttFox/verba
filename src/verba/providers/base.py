"""Abstract provider interfaces. Implement these to plug in a new service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from verba.models.ocr import OCRRequest, OCRResult
from verba.models.translation import TranslationRequest, TranslationResult


@dataclass(frozen=True)
class ProviderMeta:
    """Static description of a provider, used for discovery and docs."""

    name: str
    version: str
    capabilities: frozenset[str] = frozenset()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities


class BaseTranslator(ABC):
    """A translation service (DeepL, Baidu, local model, ...)."""

    meta: ProviderMeta

    def is_available(self) -> bool:
        """False when credentials are missing — pipeline skips the provider."""
        return True

    @abstractmethod
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate *request.text* into *request.target*."""


class BaseOCR(ABC):
    """An OCR service (Google Vision, WeChat OCR, Tesseract, ...)."""

    meta: ProviderMeta

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def recognize(self, request: OCRRequest) -> OCRResult:
        """Extract text from the image in *request*."""
