"""Strict, versioned TOML; paths are explicit and resolved relative to the config."""

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from mtah import _io

BASE_ASSETS = frozenset(("video", "atd_meta", "atd_raw", "homography"))


class ConfigError(ValueError):
    """An invalid or unreadable configuration, without private path/value details."""


@dataclass(frozen=True)
class SourceConfig:
    name: str
    frame_count: int
    track_slots: int
    fps: float
    assets: Mapping[str, Path] = field(repr=False)
    event_count: int | None = None


@dataclass(frozen=True)
class ValidationConfig:
    sources: tuple[SourceConfig, ...]


def _integer(value, minimum=1):
    if type(value) is not int or value < minimum:
        raise ConfigError("Invalid configuration")
    return value


def _source(name: str, spec: dict, base: Path) -> SourceConfig:
    required = {"frame_count", "track_slots", "fps", "assets"}
    optional = {"event_count"} if name == "tactical" else set()
    if not isinstance(spec, dict) or not required <= spec.keys() <= required | optional:
        raise ConfigError("Invalid configuration")
    fps = spec["fps"]
    if type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0:
        raise ConfigError("Invalid configuration")
    assets = spec["assets"]
    expected = BASE_ASSETS | ({"smart_tagging"} if name == "tactical" else set())
    if not isinstance(assets, dict) or set(assets) != expected:
        raise ConfigError("Invalid configuration")
    if any(
        type(value) is not str or not value.strip() or "\x00" in value for value in assets.values()
    ):
        raise ConfigError("Invalid configuration")
    # absolute() is lexical: loading a config never stats or opens its target assets.
    paths = MappingProxyType(
        {key: (base / _io.local_path(value)).absolute() for key, value in assets.items()}
    )
    return SourceConfig(
        name=name,
        frame_count=_integer(spec["frame_count"]),
        track_slots=_integer(spec["track_slots"]),
        fps=float(fps),
        assets=paths,
        event_count=_integer(spec["event_count"], 0) if "event_count" in spec else None,
    )


def load_config(path: str | Path) -> ValidationConfig:
    try:
        path = _io.local_path(path).absolute()
        with _io.open_binary(path) as handle:
            document = tomllib.load(handle)
        if set(document) != {"schema_version", "sources"}:
            raise ConfigError("Invalid configuration")
        if _integer(document["schema_version"]) != 1:
            raise ConfigError("Invalid configuration")
        sources = document["sources"]
        if not isinstance(sources, dict) or not {"tactical"} <= sources.keys() <= {
            "tactical",
            "broadcast",
        }:
            raise ConfigError("Invalid configuration")
        return ValidationConfig(
            tuple(
                _source(name, sources[name], path.parent)
                for name in ("tactical", "broadcast")
                if name in sources
            )
        )
    except (OSError, ValueError, TypeError, OverflowError):
        raise ConfigError("Invalid configuration") from None
