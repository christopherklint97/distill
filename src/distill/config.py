"""Configuration loading for Distill."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("~/.config/distill/config.toml").expanduser()


@dataclass
class GeneralConfig:
    """General settings."""

    output_dir: str = "~/Documents/distill"
    default_format: str = "markdown"
    default_style: str = "detailed"


@dataclass
class WhisperConfig:
    """Whisper transcription settings."""

    backend: str = "local"
    model: str = "base"
    language: str = "en"


@dataclass
class ClaudeConfig:
    """Claude LLM settings."""

    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8192


@dataclass
class SubscriptionConfig:
    """Subscription management settings."""

    check_interval_hours: int = 24
    auto_process: bool = False


@dataclass
class DistillConfig:
    """Top-level configuration for Distill."""

    general: GeneralConfig = field(default_factory=GeneralConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)
    subscriptions: SubscriptionConfig = field(default_factory=SubscriptionConfig)


def _apply_section(target: object, data: dict[str, object]) -> None:
    """Apply a dict of values onto a dataclass instance."""
    for key, value in data.items():
        if hasattr(target, key):
            expected_type = type(getattr(target, key))
            if expected_type is bool and isinstance(value, str):
                setattr(target, key, value.lower() in ("true", "1", "yes"))
            elif expected_type is int and isinstance(value, str):
                setattr(target, key, int(value))
            else:
                setattr(target, key, value)


def _apply_env_overrides(config: DistillConfig) -> None:
    """Override config values from environment variables."""
    env_map: dict[str, tuple[object, str]] = {
        "DISTILL_OUTPUT_DIR": (config.general, "output_dir"),
        "DISTILL_DEFAULT_FORMAT": (config.general, "default_format"),
        "DISTILL_DEFAULT_STYLE": (config.general, "default_style"),
        "DISTILL_WHISPER_BACKEND": (config.whisper, "backend"),
        "DISTILL_WHISPER_MODEL": (config.whisper, "model"),
        "DISTILL_WHISPER_LANGUAGE": (config.whisper, "language"),
        "DISTILL_CLAUDE_MODEL": (config.claude, "model"),
        "DISTILL_CLAUDE_MAX_TOKENS": (config.claude, "max_tokens"),
    }
    for env_var, (section, attr) in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            _apply_section(section, {attr: value})


def load_config(path: Path | None = None) -> DistillConfig:
    """Load configuration from TOML file with env var overrides.

    Config file path resolution:
    1. Explicit ``path`` argument
    2. ``DISTILL_CONFIG`` environment variable
    3. ``~/.config/distill/config.toml``
    """
    import tomllib

    config = DistillConfig()

    config_path = path or Path(
        os.environ.get("DISTILL_CONFIG", str(_DEFAULT_CONFIG_PATH))
    )
    config_path = config_path.expanduser()

    if config_path.exists():
        logger.info("Loading config from %s", config_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        section_map: dict[str, object] = {
            "general": config.general,
            "whisper": config.whisper,
            "claude": config.claude,
            "subscriptions": config.subscriptions,
        }
        for section_name, section_obj in section_map.items():
            if section_name in data and isinstance(data[section_name], dict):
                _apply_section(section_obj, data[section_name])
    else:
        logger.debug("No config file found at %s, using defaults", config_path)

    _apply_env_overrides(config)
    return config


def set_config_value(key: str, value: str) -> None:
    """Set a single config value in the TOML file.

    Args:
        key: Dotted key like ``whisper.backend``.
        value: The value to set.
    """
    import tomllib

    config_path = Path(
        os.environ.get("DISTILL_CONFIG", str(_DEFAULT_CONFIG_PATH))
    ).expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, dict[str, object]] = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        for k, v in raw.items():
            if isinstance(v, dict):
                data[k] = dict(v)
            else:
                data.setdefault("general", {})[k] = v

    parts = key.split(".", 1)
    if len(parts) != 2:
        msg = f"Key must be in 'section.key' format, got: {key}"
        raise ValueError(msg)

    section, attr = parts
    data.setdefault(section, {})[attr] = value

    _write_toml(config_path, data)
    logger.info("Set %s = %s in %s", key, value, config_path)


def _write_toml(path: Path, data: dict[str, dict[str, object]]) -> None:
    """Write a simple nested dict as TOML."""
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            if isinstance(v, bool):
                lines.append(f"{k} = {str(v).lower()}")
            elif isinstance(v, int):
                lines.append(f"{k} = {v}")
            else:
                lines.append(f'{k} = "{v}"')
        lines.append("")
    path.write_text("\n".join(lines))
