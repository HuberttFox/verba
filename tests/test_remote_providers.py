from __future__ import annotations

import hashlib
import httpx
import pytest

from pydantic import SecretStr

from verba.config.schema import HttpOptions, ProviderConfig
from verba.models.translation import Lang, TranslationRequest
from verba.providers.baidu import BaiduTranslator, baidu_target_code
from verba.providers.deepl import DeepLTranslator, deepl_target_code, map_detected
from verba.providers.errors import (
    NetworkError,
    ProviderError,
    ProviderNotAvailable,
    QuotaExceeded,
)
from verba.utils.http import HttpError, HttpClient


def test_deepl_target_code() -> None:
    assert deepl_target_code(Lang.ZH_HANS) == "ZH"
    assert deepl_target_code(Lang.EN) == "EN"
    assert deepl_target_code(Lang.JA) == "JA"


def test_deepl_unavailable_without_key() -> None:
    provider = DeepLTranslator(ProviderConfig(), HttpClient(HttpOptions()))
    assert not provider.is_available()


def test_deepl_translate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "DeepL-Auth-Key secret"
        return httpx.Response(
            200,
            json={"translations": [{"detected_source_language": "EN", "text": "你好"}]},
        )

    transport = httpx.MockTransport(handler)
    config = ProviderConfig(api_key=SecretStr("secret"))
    provider = DeepLTranslator(config, HttpClient(HttpOptions(), transport))
    result = provider.translate(TranslationRequest(text="hi", target=Lang.ZH_HANS))
    assert result.text == "你好"
    assert result.detected_source == Lang.EN


def test_deepl_maps_zh_detection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"translations": [{"detected_source_language": "ZH", "text": "hi"}]},
        )

    transport = httpx.MockTransport(handler)
    provider = DeepLTranslator(ProviderConfig(api_key=SecretStr("secret")), HttpClient(HttpOptions(), transport))
    result = provider.translate(TranslationRequest(text="你好", target=Lang.EN))
    assert result.detected_source == Lang.ZH_HANS


def test_deepl_http_error_maps_to_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    transport = httpx.MockTransport(handler)
    provider = DeepLTranslator(
        ProviderConfig(api_key=SecretStr("secret")), HttpClient(HttpOptions(), transport)
    )
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, NetworkError)
    assert not isinstance(exc.value, HttpError)


def test_deepl_quota_maps_to_quota_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    transport = httpx.MockTransport(handler)
    provider = DeepLTranslator(
        ProviderConfig(api_key=SecretStr("secret")), HttpClient(HttpOptions(), transport)
    )
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, QuotaExceeded)


def test_deepl_malformed_response_raises_not_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"translations": []})

    transport = httpx.MockTransport(handler)
    provider = DeepLTranslator(
        ProviderConfig(api_key=SecretStr("secret")), HttpClient(HttpOptions(), transport)
    )
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, ProviderNotAvailable)


def test_deepl_map_detected_unknown_code() -> None:
    assert map_detected("XX") is None
    assert map_detected(None) is None


def test_baidu_target_code() -> None:
    assert baidu_target_code(Lang.ZH_HANS) == "zh"
    assert baidu_target_code(Lang.EN) == "en"
    assert baidu_target_code(Lang.JA) == "jp"


def test_baidu_unavailable_without_keys() -> None:
    provider = BaiduTranslator(ProviderConfig(), HttpClient(HttpOptions()))
    assert not provider.is_available()


def test_baidu_translate_signs_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        assert params["appid"] == "app-1"
        assert params["q"] == "hi"
        assert params["from"] == "auto"
        assert params["to"] == "zh"
        signed = hashlib.md5(f"app-1hi{salt}secret".encode()).hexdigest()
        assert params["sign"] == signed
        return httpx.Response(
            200,
            json={"trans_result": [{"src": "hi", "dst": "你好"}]},
        )

    salt = "20260801"
    transport = httpx.MockTransport(handler)
    config = ProviderConfig(
        api_key=SecretStr("secret"), options={"app_id": "app-1", "salt": salt}
    )
    provider = BaiduTranslator(config, HttpClient(HttpOptions(), transport))
    result = provider.translate(TranslationRequest(text="hi", target=Lang.ZH_HANS))
    assert result.text == "你好"


def test_baidu_http_error_maps_to_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={})

    transport = httpx.MockTransport(handler)
    config = ProviderConfig(
        api_key=SecretStr("secret"), options={"app_id": "app-1", "salt": "1"}
    )
    provider = BaiduTranslator(config, HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, NetworkError)
    assert not isinstance(exc.value, HttpError)


def test_baidu_quota_maps_to_quota_exceeded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    transport = httpx.MockTransport(handler)
    config = ProviderConfig(
        api_key=SecretStr("secret"), options={"app_id": "app-1", "salt": "1"}
    )
    provider = BaiduTranslator(config, HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, QuotaExceeded)


def test_baidu_malformed_response_raises_not_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"trans_result": []})

    transport = httpx.MockTransport(handler)
    config = ProviderConfig(
        api_key=SecretStr("secret"), options={"app_id": "app-1", "salt": "1"}
    )
    provider = BaiduTranslator(config, HttpClient(HttpOptions(), transport))
    with pytest.raises(ProviderError) as exc:
        provider.translate(TranslationRequest(text="x", target=Lang.ZH_HANS))
    assert isinstance(exc.value, ProviderNotAvailable)
