# 路线图

核心框架已完成:纯 Python、无 GUI 依赖、92 测试全绿、mypy strict 通过。
桌面版(Windows,PySide6)已在 `desktop-phase` 分支完成,待合并主干。以下为后续阶段。

## 第二阶段:桌面化(PySide6)

已交付(desktop-phase):翻译浮窗/输入窗/设置窗、系统托盘、全局热键
(RegisterHotKey)、Windows 划词捕获(模拟 Ctrl+C + 剪贴板即时恢复)、
EventBus → Qt signal 桥。以下为第二期遗留项。

- [x] **UI 技术栈**:PySide6(主流 Qt 绑定,跨 Win/macOS/Linux)。
      替代选项:CustomTkinter(轻量)、Flet(新兴)
- [x] **主窗口**:翻译结果浮窗(自动关闭、固定、点击复制)、设置页
- [x] **OutputHandler 桌面实现**:`QPopupOutputHandler` 渲染结果到浮窗;
      `TrayOutputHandler` 系统托盘
- [ ] **InputSource 补齐**:
      - 划词捕获:已完成(Windows,模拟 Ctrl+C;macOS 未做)
      - 截图:Windows `mss`/`pyautogui`,macOS `screencapture`
- [x] **全局快捷键**:`RegisterHotKey`(ctypes)注册,热键冲突时托盘气泡提示
- [x] **UI 事件桥**:EventBus 订阅 → Qt signal 转发(pipeline 在 worker 线程,
      Qt 渲染回主线程)

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
