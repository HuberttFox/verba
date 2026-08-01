from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pydantic import ValidationError
import pytest

from verba.config.schema import AppConfig, DesktopOptions
from verba.models.translation import Lang


def test_desktop_options_defaults() -> None:
    cfg = AppConfig()
    assert cfg.desktop.hotkey_selection == "Ctrl+Alt+D"
    assert cfg.desktop.hotkey_input == "Ctrl+Alt+L"
    assert cfg.desktop.default_target == Lang.ZH_HANS
    assert cfg.desktop.popup_auto_close_ms == 8000
    assert cfg.desktop.click_to_copy is True


def test_desktop_options_override_from_toml() -> None:
    cfg = AppConfig.model_validate(
        {"desktop": {"hotkey_selection": "Ctrl+Shift+X", "popup_auto_close_ms": 3000}}
    )
    assert cfg.desktop.hotkey_selection == "Ctrl+Shift+X"
    assert cfg.desktop.popup_auto_close_ms == 3000
    assert cfg.desktop.hotkey_input == "Ctrl+Alt+L"


def test_popup_auto_close_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"desktop": {"popup_auto_close_ms": 0}})
