"""Configuration schema: pydantic models describing the whole app."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator

from verba.models.translation import Lang


class ProviderConfig(BaseModel):
    """Per-provider settings. Arbitrary extra options live in ``options``."""

    type: str = "remote"
    enabled: bool = True
    api_key: SecretStr | None = None
    base_url: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class CacheOptions(BaseModel):
    ttl_seconds: int = 3600
    max_entries: int = 1024


class HttpOptions(BaseModel):
    timeout: float = 30.0
    max_retries: int = 2
    base_delay: float = 0.5
    max_delay: float = 30.0
    user_agent: str = "verba/0.1.0"


class DesktopOptions(BaseModel):
    """GUI behavior. GUI reads these; core never touches them."""

    hotkey_selection: str = "Ctrl+Alt+D"
    hotkey_input: str = "Ctrl+Alt+L"
    default_target: Lang = Lang.ZH_HANS
    popup_auto_close_ms: int = 8000
    click_to_copy: bool = True

    @field_validator("popup_auto_close_ms")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("popup_auto_close_ms must be positive")
        return value


class AppConfig(BaseModel):
    """Top-level configuration merged from defaults + file + environment."""

    default_target_lang: Lang = Lang.ZH_HANS
    desktop: DesktopOptions = Field(default_factory=DesktopOptions)
    cache: CacheOptions = Field(default_factory=CacheOptions)
    http: HttpOptions = Field(default_factory=HttpOptions)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
