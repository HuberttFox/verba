from __future__ import annotations

import os

from verba.config.loader import default_config, load_config
from verba.models.translation import Lang


def test_defaults() -> None:
    config = default_config()
    assert config.default_target_lang == Lang.ZH_HANS
    assert config.cache.ttl_seconds == 3600
    assert config.http.timeout == 30.0


def test_load_toml(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "config.toml").write_text(
        '[providers.deepl]\nenabled = false\nbase_url = "https://x"\n'
        "[http]\ntimeout = 5.5\n"
    )
    config = load_config(tmp_path / "config.toml")
    assert config.providers["deepl"].enabled is False
    assert config.providers["deepl"].base_url == "https://x"
    assert config.http.timeout == 5.5


def test_env_api_key_override(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "config.toml").write_text('[providers.deepl]\nenabled = true\n')
    monkeypatch.setenv("BOBPOT_API_KEY_DEEPL", "secret-key")
    config = load_config(tmp_path / "config.toml")
    api_key = config.providers["deepl"].api_key
    assert api_key is not None
    assert api_key.get_secret_value() == "secret-key"


def test_file_key_wins_over_env(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "config.toml").write_text(
        '[providers.deepl]\napi_key = "from-file"\n'
    )
    monkeypatch.setenv("BOBPOT_API_KEY_DEEPL", "from-env")
    config = load_config(tmp_path / "config.toml")
    api_key = config.providers["deepl"].api_key
    assert api_key is not None
    assert api_key.get_secret_value() == "from-file"
