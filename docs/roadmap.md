# 路线图

核心框架(第一阶段)已完成:纯 Python、无 GUI 依赖、24 测试全绿、
mypy strict 通过。以下为后续阶段。

## 第二阶段:桌面化(PySide6)

- [ ] **UI 技术栈**:PySide6(主流 Qt 绑定,跨 Win/macOS/Linux)。
      替代选项:CustomTkinter(轻量)、Flet(新兴)
- [ ] **主窗口**:翻译结果弹窗(可置顶、可拖拽、透明背景)、设置页
- [ ] **OutputHandler 桌面实现**:`QPopupOutputHandler` 渲染结果到浮窗;
      `TrayOutputHandler` 系统托盘
- [ ] **InputSource 补齐**:
      - 划词捕获:Windows 用 `pywin32`(GlobalKeyboardHook +
        `GetCursorPos` + 复制),macOS 用 `pyobjc`(AX API + 模拟 Cmd+C)
      - 截图:Windows `mss`/`pyautogui`,macOS `screencapture`
- [ ] **全局快捷键**:`pynput` 注册(翻译/OCR/截图)热键
- [ ] **UI 事件桥**:EventBus 订阅 → Qt signal 转发(注意线程:
      pipeline 调用发生在热键线程,Qt 渲染必须回主线程)

## 第三阶段:真实服务接入

- [ ] 翻译:DeepL、百度翻译、LibreTranslate(自托管免费)
- [ ] OCR:Google Vision、腾讯云 OCR、本地 Tesseract/PaddleOCR
- [ ] 流式 AI 翻译/解释:`HttpClient.stream_sse` 已验证,可接 LLM 流式输出
- [ ] TTS / 查词(词典释义)能力扩展:`capabilities` 字段预留

## 第四阶段:产品化

- [ ] 打包:`PyInstaller`(Windows exe)/ `briefcase`(macOS .app)
- [ ] 自动更新、崩溃上报、遥测(可选)
- [ ] provider 市场:按 `ProviderMeta.capabilities` 发现/选择默认服务
- [ ] i18n:UI 中英双语

## 里程碑建议

1. **M1(2 周)**:PySide6 浮窗 + 剪贴板翻译 + DeepL/百度翻译
2. **M2(1 周)**:截图 OCR 全链路(截图 → OCR → 翻译 → 浮窗)
3. **M3(1 周)**:全局快捷键 + 设置页 + 打包内测
