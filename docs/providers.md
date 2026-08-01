# 扩展指南:写一个 Provider

三步接入一个真实翻译/OCR 服务。以 DeepL 风格翻译 API 为例。

## 第一步:实现接口

```python
# myapp/providers/myservice.py
from verba.providers.base import BaseTranslator, ProviderMeta
from verba.providers.errors import NetworkError, QuotaExceeded
from verba.models.translation import TranslationRequest, TranslationResult
from verba.utils.http import HttpClient


class MyTranslator(BaseTranslator):
    meta = ProviderMeta(
        name="myservice",
        version="1.0.0",
        capabilities=frozenset({"translate"}),
    )

    def __init__(self, http: HttpClient, api_key: str, base_url: str) -> None:
        self._http = http
        self._api_key = api_key
        self._base_url = base_url

    def is_available(self) -> bool:
        return bool(self._api_key)

    def translate(self, request: TranslationRequest) -> TranslationResult:
        data = self._http.post_json(
            f"{self._base_url}/v1/translate",
            {"text": request.text, "target": request.target.value},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        return TranslationResult(
            text=data["translated_text"],
            source=request.source,
            target=request.target,
            provider=self.meta.name,
        )
```

要点:

- 请求/响应一律用 `models/` 里的不可变模型,不要自造数据结构
- 网络调用走 `HttpClient`(超时、UA、错误映射 `HttpError`/`QuotaExceeded`
  自动处理),不要裸建 `httpx.Client`
- `is_available()` 返回 `False` 时管线直接抛 `ProviderNotAvailable`,
  不会浪费一次请求

## 第二步:注册

```python
from verba.config.loader import load_config
from verba.utils.http import HttpClient
from myapp.providers.myservice import MyTranslator

config = load_config()          # 自动读 ~/.config/verba/config.toml
provider_cfg = config.providers["myservice"]   # 若无:填一个 ProviderConfig

translators.register(
    "myservice",
    MyTranslator(
        http=HttpClient(config.http),
        api_key=provider_cfg.api_key.get_secret_value(),
        base_url=provider_cfg.base_url or "https://api.example.com",
    ),
)
```

密钥配置(三者取其一):

```toml
# ~/.config/verba/config.toml
[providers.myservice]
base_url = "https://api.example.com"
api_key = "put-me-in-env-instead"
```

```bash
export BOBPOT_API_KEY_MYSERVICE="sk-xxx"   # 推荐:环境变量优先于缺省
```

## 第三步:接入管线(可选增强)

```python
from verba.utils.retry import RetryPolicy
from verba.utils.rate_limit import RateLimiter

class ResilientTranslator(BaseTranslator):  # 组合而非继承
    def __init__(self, inner: BaseTranslator, rate: RateLimiter) -> None:
        self.meta = inner.meta
        self._inner = inner
        self._policy = RetryPolicy(retry_on=(NetworkError,))
        self._rate = rate

    def translate(self, request: TranslationRequest) -> TranslationResult:
        self._rate.wait()                      # 限流
        return self._policy.execute(           # 重试(指数退避)
            lambda: self._inner.translate(request)
        )
```

## OCR provider 对照

接口对称:`BaseOCR.recognize(OCRRequest) -> OCRResult`。

```python
class MyOCR(BaseOCR):
    meta = ProviderMeta(name="myocr", version="1.0.0",
                        capabilities=frozenset({"ocr"}))

    def recognize(self, request: OCRRequest) -> OCRResult:
        resp = self._http.post_json(
            f"{self._base}/ocr",
            {"image": base64.b64encode(request.image.as_bytes()).decode()},
        )
        return OCRResult(
            text=resp["text"],
            provider=self.meta.name,
            language=Lang(resp.get("lang", "auto")),
            confidence=resp.get("confidence"),
        )
```

图片统一用 `request.image.as_bytes()` 取字节,provider 自己决定
base64 / multipart 上传。

## 常见服务对照(方向性参考)

| 能力 | 免费/自托管 | 商业 |
|---|---|---|
| 翻译 | LibreTranslate, 本地 LLM | DeepL, 百度翻译, Google Translate |
| OCR | Tesseract, PaddleOCR | Google Vision, 腾讯/百度 OCR |

接口是同步的:远程调用直接阻塞,本地模型自行包线程池或协程。
