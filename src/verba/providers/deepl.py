"""DeepL translation via the official API (api-free.deepl.com)."""

from __future__ import annotations

from pydantic import SecretStr

from verba.config.schema import ProviderConfig
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.providers.errors import NetworkError, ProviderNotAvailable
from verba.utils.http import HttpError, HttpClient

_URL = "https://api-free.deepl.com/v2/translate"


def deepl_target_code(lang: Lang) -> str:
    if lang == Lang.ZH_HANS:
        return "ZH"
    if lang == Lang.AUTO:
        return "EN"
    return lang.value.upper()


# DeepL 返回大写代码,且简繁不分(一律 "ZH" -> 简体)
_DETECTED_MAP: dict[str, Lang] = {
    lang.value.upper(): lang for lang in Lang if lang != Lang.AUTO
}
_DETECTED_MAP["ZH"] = Lang.ZH_HANS


def map_detected(raw: str | None) -> Lang | None:
    if not raw:
        return None
    return _DETECTED_MAP.get(raw.upper())


class DeepLTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="deepl", version="0.1.0", capabilities=frozenset({"translate"})
    )

    def __init__(self, config: ProviderConfig, http: HttpClient) -> None:
        self._config = config
        self._http = http

    def is_available(self) -> bool:
        return self._api_key() is not None

    def _api_key(self) -> str | None:
        key: SecretStr | None = self._config.api_key
        return key.get_secret_value() if key else None

    def translate(self, request: TranslationRequest) -> TranslationResult:
        key = self._api_key()
        if key is None:
            raise ProviderNotAvailable("deepl: missing API key")
        try:
            data = self._http.post_json(
                _URL,
                payload={},
                headers={"Authorization": f"DeepL-Auth-Key {key}"},
                params={
                    "text": request.text,
                    "target_lang": deepl_target_code(request.target),
                },
            )
        except HttpError as exc:
            raise NetworkError(f"deepl: {exc}") from exc
        entries = data.get("translations")
        if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
            raise ProviderNotAvailable("deepl: malformed response payload")
        first = entries[0]
        text = first.get("text")
        if not isinstance(text, str):
            raise ProviderNotAvailable("deepl: malformed response payload")
        detected = map_detected(first.get("detected_source_language"))
        return TranslationResult(
            text=text,
            source=request.source,
            target=request.target,
            provider=self.meta.name,
            detected_source=detected,
        )
