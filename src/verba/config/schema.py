"""Configuration schema: pydantic models describing the whole app."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, SecretStr

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


class AppConfig(BaseModel):
    """Top-level configuration merged from defaults + file + environment."""

    default_target_lang: Lang = Lang.ZH_HANS
    cache: CacheOptions = Field(default_factory=CacheOptions)
    http: HttpOptions = Field(default_factory=HttpOptions)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
