from __future__ import annotations

import httpx
import pytest

from verba.config.schema import HttpOptions, ProviderConfig
from verba.models.translation import Lang, TranslationRequest
from verba.providers.errors import NetworkError, ProviderError, ProviderNotAvailable, QuotaExceeded
from verba.providers.google import GoogleFreeTranslator, google_target_code
from verba.utils.http import HttpError, HttpClient


def test_google_target_code_mapping() -> None:
    assert google_target_code(Lang.ZH_HANS) == "zh-CN"
    assert google_target_code(Lang.ZH_HANT) == "zh-TW"
    assert google_target_code(Lang.EN) == "en"
    assert google_target_code(Lang.AUTO) == "auto"


def test_google_translate_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "translate.googleapis.com" in str(request.url)
        body = [[["你好，世界", "Hello world", None, None]], None, "en", None]
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    result = provider.translate(
        TranslationRequest(text="Hello world", target=Lang.ZH_HANS)
    )
    assert result.text == "你好，世界"
    assert result.detected_source == Lang.EN
    assert result.provider == "google"


def test_google_translate_http_error_maps_to_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, NetworkError)
    assert not isinstance(exc.value, HttpError)
    assert not isinstance(exc.value, httpx.HTTPStatusError)


def test_google_translate_quota_maps_to_quota_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, QuotaExceeded)


def test_google_translate_empty_body_raises_not_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, ProviderNotAvailable)


def test_google_translate_null_first_segment_raises_not_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[None, "en"])

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, ProviderNotAvailable)


def test_google_maps_zh_tw_detection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = [[["世界", "world", None, None]], None, "zh-TW", None]
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    provider = GoogleFreeTranslator(ProviderConfig(), HttpClient(HttpOptions(), transport))
    result = provider.translate(TranslationRequest(text="world", target=Lang.ZH_HANS))
    assert result.detected_source == Lang.ZH_HANT
