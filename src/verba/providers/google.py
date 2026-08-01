"""Free Google Translate endpoint (translate.googleapis.com), no API key.

Unofficial endpoint; works without credentials. Fine for a personal tool.
"""

from __future__ import annotations

from verba.config.schema import HttpOptions, ProviderConfig
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.utils.http import HttpClient

_URL = "https://translate.googleapis.com/translate_a/single"

_LANG_CODES = {
    Lang.ZH_HANS: "zh-CN",
    Lang.ZH_HANT: "zh-TW",
    Lang.EN: "en",
    Lang.JA: "ja",
    Lang.KO: "ko",
    Lang.FR: "fr",
    Lang.DE: "de",
    Lang.ES: "es",
    Lang.RU: "ru",
    Lang.PT: "pt",
    Lang.IT: "it",
}


def google_target_code(lang: Lang) -> str:
    if lang == Lang.AUTO:
        return "auto"
    return _LANG_CODES.get(lang, lang.value)


class GoogleFreeTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="google",
        version="0.1.0",
        capabilities=frozenset({"translate"}),
    )

    def __init__(self, config: ProviderConfig, http: HttpClient) -> None:
        self._config = config
        self._http = http

    def is_available(self) -> bool:
        return True

    def translate(self, request: TranslationRequest) -> TranslationResult:
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": google_target_code(request.target),
            "dt": "t",
            "q": request.text,
        }
        data = self._http.get_json_any(_URL, params=params)
        segments = data[0]
        parts: list[str] = []
        for seg in segments:
            parts.append(str(seg[0]))
        translated = "".join(parts)
        detected_raw = data[2] if len(data) > 2 else None
        detected = self._map_detected(detected_raw)
        return TranslationResult(
            text=translated,
            source=request.source,
            target=request.target,
            provider=self.meta.name,
            detected_source=detected,
        )

    @staticmethod
    def _map_detected(raw: str | None) -> Lang | None:
        if not raw:
            return None
        code = raw.lower()
        if code == "zh-cn":
            return Lang.ZH_HANS
        if code == "zh-tw":
            return Lang.ZH_HANT
        for lang in Lang:
            if lang != Lang.AUTO and lang.value.lower() == code:
                return lang
        return None
