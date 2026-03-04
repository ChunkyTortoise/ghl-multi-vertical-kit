"""Load and validate vertical YAML configs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import yaml

from app.models import VerticalConfig

logger = logging.getLogger(__name__)

_VERTICALS_DIR = Path(__file__).resolve().parent.parent.parent / "verticals"

# In-memory cache: vertical name -> VerticalConfig
_cache: Dict[str, VerticalConfig] = {}


def _verticals_dir() -> Path:
    """Return the verticals directory path (testable)."""
    return _VERTICALS_DIR


def load_vertical(name: str, *, verticals_dir: Optional[Path] = None) -> VerticalConfig:
    """Load a single vertical config by name.

    Args:
        name: Vertical name (matches ``<name>.yaml`` in verticals/).
        verticals_dir: Override directory (used in tests).

    Returns:
        Parsed ``VerticalConfig``.

    Raises:
        FileNotFoundError: If the YAML file doesn't exist.
        ValueError: If the YAML is invalid or fails validation.
    """
    if name in _cache and verticals_dir is None:
        return _cache[name]

    base = verticals_dir or _verticals_dir()
    path = base / f"{name}.yaml"

    if not path.exists():
        available = list_verticals(verticals_dir=base)
        raise FileNotFoundError(
            f"Vertical '{name}' not found at {path}. "
            f"Available: {available}"
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Expected a mapping in {path}, got {type(raw).__name__}")

    config = VerticalConfig(**raw)

    if verticals_dir is None:
        _cache[name] = config

    return config


def list_verticals(*, verticals_dir: Optional[Path] = None) -> list[str]:
    """Return names of all available verticals."""
    base = verticals_dir or _verticals_dir()
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.yaml"))


def clear_cache() -> None:
    """Clear the in-memory vertical cache."""
    _cache.clear()
