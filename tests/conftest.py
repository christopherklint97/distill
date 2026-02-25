"""Shared test fixtures."""

from pathlib import Path

import pytest

from distill.config import DistillConfig
from distill.db import Database


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Create a temporary database for testing."""
    db = Database(tmp_path / "test.db")
    yield db  # type: ignore[misc]
    db.close()


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    """Return a temporary config file path."""
    return tmp_path / "config.toml"


@pytest.fixture
def default_config() -> DistillConfig:
    """Return a default config instance."""
    return DistillConfig()
