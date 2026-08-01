# verba

UI 无关的 Python 插件框架,用于从 0 构建 **Bob / Pot 类**桌面工具:
划词翻译、截图 OCR、多翻译服务接入。

核心零 GUI 依赖,可独立运行(CLI);桌面 UI 通过 `OutputHandler` / `InputSource`
抽象接入,第二阶段计划 PySide6。

## 快速开始

```bash
uv sync --extra dev
uv run verba translate "Hello world" --to zh-Hans --provider echo
# [auto->zh-Hans] Hello world

uv run verba ocr-demo ./screenshot.png
```

`echo` / `echo-ocr` 是验证接口的 stub provider。接入真实服务见
[docs/providers.md](docs/providers.md)。

## 代码里用

```python
from verba.core.pipeline import Pipeline
from verba.core.registry import ServiceRegistry
from verba.outputs.base import OutputHub
from verba.outputs.notification import ConsoleOutputHandler
from verba.providers.base import BaseTranslator
from verba.providers.demo import EchoTranslator
from verba.utils.cache import TTLCache

translators: ServiceRegistry[BaseTranslator] = ServiceRegistry()
translators.register("echo", EchoTranslator())

outputs = OutputHub()
outputs.register(ConsoleOutputHandler())

pipeline = Pipeline(translators=translators, outputs=outputs, cache=TTLCache())
result = pipeline.translate_text("Hello", target_lang=Lang.ZH_HANS, provider="echo")
print(result.text)
```

## 架构一图流

```
事件触发(划词/剪贴板/截图/手动)
      │ EventBus 发布
      ▼
InputSource → (OCR?) → Translator → OutputHandler 呈现
      └──────── ServiceRegistry(插件注册表) ────────┘
```

详细见 [docs/architecture.md](docs/architecture.md)。

## 包结构

```
src/verba/
├── core/        EventBus, ServiceRegistry, Pipeline(编排)
├── models/      不可变数据模型(TranslationRequest/Result, OCR, Image)
├── providers/   BaseTranslator / BaseOCR 抽象 + demo stub
├── inputs/      输入源抽象(clipboard 可用, selection/screenshot 占位)
├── outputs/     OutputHandler 抽象(console/notification 参考实现)
├── config/      分层配置:默认 → TOML → 环境变量(密钥)
└── utils/       RetryPolicy, RateLimiter, TTLCache, HttpClient(SSE), 日志
```

## 测试与类型

```bash
uv run pytest          # 24 tests
uv run mypy            # strict, 0 errors
```

## 路线图

第二阶段(桌面化)见 [docs/roadmap.md](docs/roadmap.md):PySide6 UI、
全局快捷键、划词/截图输入源、真实翻译/OCR 服务接入。
