# verba

UI 无关的 Python 插件框架,用于从 0 构建 **Bob / Pot 类**桌面工具:
划词翻译、截图 OCR、多翻译服务接入。

核心零 GUI 依赖,可独立运行(CLI);桌面 UI 通过 `OutputHandler` / `InputSource`
抽象接入,基于 PySide6 的桌面版(Windows)见下文。

## 快速开始

```bash
uv sync --extra dev
uv run verba translate "Hello world" --to zh-Hans --provider echo
# [auto->zh-Hans] Hello world

uv run verba ocr-demo ./screenshot.png
```

`echo` / `echo-ocr` 是验证接口的 stub provider。接入真实服务见
[docs/providers.md](docs/providers.md)。

## 桌面版(Windows)

Bob/Pot 风格桌面工具:系统托盘常驻,全局热键翻译。

**功能清单**
- 划词翻译:选中任意文字,按 `Ctrl+Alt+D` → 浮窗显示原文 + 译文
- 输入翻译:`Ctrl+Alt+L` → 输入窗在鼠标处弹出,Enter 翻译
- 系统托盘:划词翻译 / 输入翻译 / 设置 / 退出
- 设置窗:热键重绑、目标语言,保存即生效
- 结果浮窗:自动关闭、可固定、点击复制译文到剪贴板

**快速开始**

```bash
uv sync
uv run verba-desktop
```

**配置** `~/.config/verba/config.toml`:

```toml
[desktop]
hotkey_selection = "Ctrl+Alt+D"
hotkey_input = "Ctrl+Alt+L"
default_target = "zh-Hans"

[providers.deepl]
type = "remote"

[providers.baidu]
type = "remote"
options = { app_id = "your-app-id" }
```

API key 不写进 TOML,通过环境变量注入(需先在 TOML 声明对应 provider):

```bash
export BOBPOT_API_KEY_BAIDU="your-secret"
export BOBPOT_API_KEY_DEEPL="your-key"
```

提供者优先级:google(免密钥)→ deepl → baidu → echo;未配密钥的跳过。

**已知限制**
- 目标应用以管理员权限运行(UAC 提权)→ 模拟复制无效
- Google 免费接口不稳定,可用 deepl/baidu 密钥替代
- 完整真机验证清单见 [docs/windows-verification.md](docs/windows-verification.md)

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
uv run pytest          # 92 tests
uv run mypy            # strict, 0 errors
```

## 路线图

未实现能力(截图 OCR、流式 AI 翻译、打包 exe、自动更新等)见
[docs/roadmap.md](docs/roadmap.md)。
