"""Platform automation input sources (stubs).

划词捕获 (selection) 和 截图 (screenshot) 需要平台自动化能力:
- Windows/Linux: pynput + pyautogui/mss
- macOS: pyobjc + Quartz

这些属于第二阶段(桌面层)工作,见 docs/roadmap.md。接口已在此定型,
第二阶段只需实现 capture(),无需改动核心。
"""

from __future__ import annotations

from verba.inputs.base import InputPayload, InputSource


class SelectionSource(InputSource):
    """Copies the currently selected text on screen."""

    name = "selection"

    def capture(self) -> InputPayload:
        raise NotImplementedError(
            "SelectionSource 依赖平台自动化(pynput/pyautogui),"
            "见 docs/roadmap.md 第二阶段"
        )


class ScreenshotSource(InputSource):
    """Takes a screenshot of the selected screen region."""

    name = "screenshot"

    def capture(self) -> InputPayload:
        raise NotImplementedError(
            "ScreenshotSource 依赖平台自动化(mss/pyautogui),"
            "见 docs/roadmap.md 第二阶段"
        )
