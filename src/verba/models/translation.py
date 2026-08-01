from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Lang(StrEnum):
    """Common BCP-47 language codes. Providers may accept more."""

    AUTO = "auto"
    ZH_HANS = "zh-Hans"
    ZH_HANT = "zh-Hant"
    EN = "en"
    JA = "ja"
    KO = "ko"
    FR = "fr"
    DE = "de"
    ES = "es"
    RU = "ru"
    PT = "pt"
    IT = "it"


class TranslationRequest(BaseModel):
    """Input for any translator provider."""

    model_config = ConfigDict(frozen=True)

    text: str
    source: Lang = Lang.AUTO
    target: Lang
    context: str | None = None
    suggest_replacement: bool = False


class TranslationResult(BaseModel):
    """Output produced by a translator provider."""

    model_config = ConfigDict(frozen=True)

    text: str
    source: Lang
    target: Lang
    provider: str
    detected_source: Lang | None = None
    alternatives: list[str] = Field(default_factory=list)
    explanation: str | None = None
    from_cache: bool = False
    duration_ms: float | None = None
