"""Tests for configuration loading."""

from pathlib import Path

import pytest

from distill.config import DistillConfig, load_config, set_config_value


class TestDefaults:
    def test_default_config(self, default_config: DistillConfig) -> None:
        assert default_config.general.default_format == "markdown"
        assert default_config.general.default_style == "detailed"
        assert default_config.whisper.backend == "local"
        assert default_config.whisper.model == "base"
        assert default_config.claude.model == "claude-sonnet-4-6"
        assert default_config.claude.max_tokens == 8192
        assert default_config.subscriptions.check_interval_hours == 24

    def test_missing_config_file_uses_defaults(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.toml")
        assert config.general.default_format == "markdown"


class TestFileLoading:
    def test_load_from_toml(self, tmp_config_path: Path) -> None:
        tmp_config_path.write_text(
            '[general]\noutput_dir = "/tmp/test"\ndefault_style = "concise"\n\n'
            '[whisper]\nbackend = "api"\nmodel = "large"\n'
        )
        config = load_config(tmp_config_path)
        assert config.general.output_dir == "/tmp/test"
        assert config.general.default_style == "concise"
        assert config.whisper.backend == "api"
        assert config.whisper.model == "large"
        # Unset values keep defaults
        assert config.general.default_format == "markdown"

    def test_partial_config(self, tmp_config_path: Path) -> None:
        tmp_config_path.write_text('[claude]\nmax_tokens = 4096\n')
        config = load_config(tmp_config_path)
        assert config.claude.max_tokens == 4096
        assert config.claude.model == "claude-sonnet-4-6"


class TestEnvOverrides:
    def test_env_overrides_file(
        self, tmp_config_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tmp_config_path.write_text('[general]\ndefault_format = "html"\n')
        monkeypatch.setenv("DISTILL_DEFAULT_FORMAT", "epub")
        config = load_config(tmp_config_path)
        assert config.general.default_format == "epub"

    def test_env_overrides_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("DISTILL_WHISPER_BACKEND", "api")
        config = load_config(tmp_path / "missing.toml")
        assert config.whisper.backend == "api"


class TestSetConfig:
    def test_set_config_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config.toml"
        monkeypatch.setenv("DISTILL_CONFIG", str(config_path))
        set_config_value("whisper.backend", "api")
        config = load_config(config_path)
        assert config.whisper.backend == "api"

    def test_set_preserves_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_path = tmp_path / "config.toml"
        monkeypatch.setenv("DISTILL_CONFIG", str(config_path))
        set_config_value("whisper.backend", "api")
        set_config_value("whisper.model", "large")
        config = load_config(config_path)
        assert config.whisper.backend == "api"
        assert config.whisper.model == "large"
