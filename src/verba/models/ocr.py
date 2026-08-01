from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from verba.models.image import ImageSource
from verba.models.translation import Lang


class TextBox(BaseModel):
    """A word/line box detected by OCR, in pixels relative to the image."""

    model_config = ConfigDict(frozen=True)

    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float | None = None


class OCRRequest(BaseModel):
    """Input for any OCR provider."""

    model_config = ConfigDict(frozen=True)

    image: ImageSource
    source_langs: list[Lang] | None = None
    detect_language: bool = False


class OCRResult(BaseModel):
    """Output produced by an OCR provider."""

    model_config = ConfigDict(frozen=True)

    text: str
    provider: str
    boxes: list[TextBox] = Field(default_factory=list)
    language: Lang | None = None
    confidence: float | None = None
