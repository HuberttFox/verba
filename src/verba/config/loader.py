"""Config loading: defaults -> user TOML -> environment overrides."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir
from pydantic import SecretStr

from verba.config.schema import AppConfig, ProviderConfig


def default_config() -> AppConfig:
    """Built-in defaults, safe to use out of the box."""
    return AppConfig()


def user_config_path() -> Path:
    """Per-user config file location, e.g. ~/.config/verba/config.toml."""
    return Path(user_config_dir("verba")) / "config.toml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into a copy of *base*."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env(config: AppConfig) -> AppConfig:
    """Fill api_key from BOBPOT_API_KEY_<PROVIDER> when not set in file."""
    providers = dict(config.providers)
    for name, provider in providers.items():
        env_name = f"BOBPOT_API_KEY_{name.upper().replace('-', '_')}"
        if provider.api_key is None and env_name in os.environ:
            providers[name] = provider.model_copy(
                update={"api_key": SecretStr(os.environ[env_name])}
            )
    return config.model_copy(update={"providers": providers})


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load config from the given path (or the default location if missing)."""
    base = default_config().model_dump()

    if path is None:
        path = user_config_path()
    path = Path(path)

    if path.is_file():
        with path.open("rb") as fh:
            base = _deep_merge(base, tomllib.load(fh))

    return _apply_env(AppConfig.model_validate(base))
