"""Immutable data models shared across the framework."""

from verba.models.image import ImageSource
from verba.models.ocr import OCRRequest, OCRResult, TextBox
from verba.models.translation import Lang, TranslationRequest, TranslationResult

__all__ = [
    "ImageSource",
    "Lang",
    "OCRRequest",
    "OCRResult",
    "TextBox",
    "TranslationRequest",
    "TranslationResult",
]
