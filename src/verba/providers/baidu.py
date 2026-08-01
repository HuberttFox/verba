"""Baidu translation API (fanyi-api.baidu.com). Requires app_id + secret."""

from __future__ import annotations

import hashlib
import time

from pydantic import SecretStr

from verba.config.schema import ProviderConfig
from verba.models.translation import Lang, TranslationRequest, TranslationResult
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.providers.errors import NetworkError, ProviderNotAvailable, QuotaExceeded
from verba.utils.http import HttpError, HttpClient

_URL = "https://fanyi-api.baidu.com/api/trans/vip/translate"

_BAIDU_CODES = {
    Lang.ZH_HANS: "zh",
    Lang.ZH_HANT: "cht",
    Lang.JA: "jp",
    Lang.KO: "kor",
    Lang.FR: "fra",
    Lang.DE: "de",
    Lang.ES: "spa",
    Lang.RU: "ru",
    Lang.PT: "pt",
    Lang.IT: "it",
}


def baidu_target_code(lang: Lang) -> str:
    if lang == Lang.AUTO:
        return "auto"
    return _BAIDU_CODES.get(lang, lang.value)


class BaiduTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="baidu", version="0.1.0", capabilities=frozenset({"translate"})
    )

    def __init__(self, config: ProviderConfig, http: HttpClient) -> None:
        self._config = config
        self._http = http

    def is_available(self) -> bool:
        return self._app_id() is not None and self._api_key() is not None

    def _app_id(self) -> str | None:
        return self._config.options.get("app_id")

    def _api_key(self) -> str | None:
        key: SecretStr | None = self._config.api_key
        return key.get_secret_value() if key else None

    def translate(self, request: TranslationRequest) -> TranslationResult:
        app_id = self._app_id()
        secret = self._api_key()
        if app_id is None or secret is None:
            raise ProviderNotAvailable("baidu: missing app_id/api_key")
        salt = self._config.options.get("salt") or str(int(time.time()))
        sign = hashlib.md5(f"{app_id}{request.text}{salt}{secret}".encode()).hexdigest()
        try:
            data = self._http.get_json(
                _URL,
                params={
                    "q": request.text,
                    "from": "auto",
                    "to": baidu_target_code(request.target),
                    "appid": app_id,
                    "salt": salt,
                    "sign": sign,
                },
            )
        except HttpError as exc:
            raise NetworkError(f"baidu: {exc}") from exc
        entries = data.get("trans_result")
        if entries is None and data.get("error_code") is not None:
            code = str(data.get("error_code"))
            if code == "52001":
                raise NetworkError("baidu: api timeout (52001)")
            if code in ("54003", "54004"):
                raise QuotaExceeded(f"baidu: quota/frequency limit ({code})")
            raise ProviderNotAvailable(f"baidu: api error {code}")
        if not isinstance(entries, list) or not entries:
            raise ProviderNotAvailable("baidu: malformed response payload")
        parts: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ProviderNotAvailable("baidu: malformed response payload")
            dst = entry.get("dst")
            if not isinstance(dst, str):
                raise ProviderNotAvailable("baidu: malformed response payload")
            parts.append(dst)
        text = "".join(parts)
        return TranslationResult(
            text=text,
            source=request.source,
            target=request.target,
            provider=self.meta.name,
        )
