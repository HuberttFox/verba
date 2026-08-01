from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from pytestqt.qtbot import QtBot

from verba.config.schema import DesktopOptions
from verba.desktop.windows.popup import ResultPopup, popup_rect
from verba.models.translation import Lang, TranslationResult

SCREEN = QRect(0, 0, 1920, 1080)
SECONDARY = QRect(1920, 0, 1280, 1024)


def make_result() -> TranslationResult:
    return TranslationResult(
        text="你好,世界",
        source=Lang.AUTO,
        target=Lang.ZH_HANS,
        provider="echo",
    )


def test_rect_near_anchor() -> None:
    r = popup_rect(QPoint(500, 400), QSize(300, 200), [SCREEN])
    assert r.left() == 500
    assert r.top() == 400
    assert r.size() == QSize(300, 200)


def test_rect_clamps_right_bottom() -> None:
    r = popup_rect(QPoint(1800, 1000), QSize(300, 200), [SCREEN])
    assert r.right() <= SCREEN.right() - 8
    assert r.bottom() <= SCREEN.bottom() - 8
    assert r.width() == 300


def test_rect_clamps_left_top() -> None:
    r = popup_rect(QPoint(2, 2), QSize(300, 200), [SCREEN])
    assert r.left() >= SCREEN.left() + 8
    assert r.top() >= SCREEN.top() + 8


def test_rect_uses_anchor_screen() -> None:
    r = popup_rect(QPoint(2000, 500), QSize(300, 200), [SCREEN, SECONDARY])
    assert r.left() >= SECONDARY.left()
    assert r.right() <= SECONDARY.right()


def test_popup_renders_result_and_copies(qtbot: QtBot) -> None:
    popup = ResultPopup(DesktopOptions())
    qtbot.addWidget(popup)
    popup.show_result(make_result(), QPoint(100, 100))
    assert popup.isVisible()
    assert "你好,世界" in popup.toPlainText()

    popup.copy_translation()
    from PySide6.QtWidgets import QApplication

    clip = QApplication.clipboard().text()
    assert clip == "你好,世界"


def test_copy_label_reverts_after_delay(qtbot: QtBot) -> None:
    popup = ResultPopup(DesktopOptions())
    qtbot.addWidget(popup)
    popup.show_result(make_result(), QPoint(100, 100))
    popup.copy_translation()
    assert popup._copy_button.text() == "已复制"
    qtbot.wait(1300)
    assert popup._copy_button.text() == "复制"


def test_copy_timer_does_not_outlive_popup(qtbot: QtBot) -> None:
    popup = ResultPopup(DesktopOptions())
    qtbot.addWidget(popup)
    popup.show_result(make_result(), QPoint(100, 100))
    popup.copy_translation()
    popup.deleteLater()
    qtbot.wait(10)
    qtbot.wait(1300)


class _WideContentPopup(ResultPopup):
    """Simulates content forcing a wider-than-cap layout (offscreen-safe)."""

    def adjustSize(self) -> None:
        self.resize(600, 200)


def test_popup_width_capped_at_400(qtbot: QtBot) -> None:
    popup = _WideContentPopup(DesktopOptions())
    qtbot.addWidget(popup)
    popup.show_anchor(QPoint(100, 100))
    assert popup.width() <= 400
    assert popup.width() >= 320


def test_popup_pin_disables_auto_close(qtbot: QtBot) -> None:
    opts = DesktopOptions(popup_auto_close_ms=100)
    popup = ResultPopup(opts)
    qtbot.addWidget(popup)
    popup.show_result(make_result(), QPoint(100, 100))
    popup._pin_button.click()
    assert popup.is_pinned
    qtbot.wait(300)
    assert popup.isVisible()
