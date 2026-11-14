"""Strict local runner settings, separate from the read-only validation configuration."""

import math
import os
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from mtah import _io
from mtah.features import FeatureConfig, Period
from mtah.inference import RuleConfig
from mtah.inference.temporal import OfflineTemporalDecoder, TemporalConfig
from mtah.local.errors import LocalError as LocalError
from mtah.local.errors import guarded

PHASE1_PERIODS = (Period(1, 11185, 90652), Period(2, 110808, 190198))
MAX_CONFIG_BYTES = 1024 * 1024
MAX_XML_BYTES = 16 * 1024 * 1024
MAX_LINE_CHARS = 65536


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    short_fragment_s: float = 1.0
    max_short_fragment_fraction: float = 0.5
    max_abstention_fraction: float = 0.5

    def __post_init__(self):
        for name in ("short_fragment_s", "max_short_fragment_fraction", "max_abstention_fraction"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise LocalError("invalid_diagnostic_settings")
            if name != "short_fragment_s" and value > 1:
                raise LocalError("invalid_diagnostic_settings")


@dataclass(frozen=True, slots=True)
class LocalConfig:
    profile: str
    dataset_root: Path = field(repr=False)
    output_root: Path = field(repr=False)
    assets: object = field(repr=False)
    frame_count: int
    track_slots: int
    home_id: str = field(repr=False)
    away_id: str = field(repr=False)
    tag_home: str = field(repr=False)
    tag_away: str = field(repr=False)
    features: FeatureConfig
    rules: RuleConfig
    diagnostics: DiagnosticConfig
    parameter_basis: str
    reference: str = field(repr=False)
    mode: str = "rules"
    temporal: TemporalConfig | None = None

    def __post_init__(self):
        if (
            self.mode not in ("rules", "rules_temporal")
            or (self.mode == "rules" and self.temporal is not None)
            or (self.mode == "rules_temporal" and not isinstance(self.temporal, TemporalConfig))
        ):
            raise LocalError("invalid_inference_mode")


def _keys(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() <= set(required) | set(
        optional
    ):
        raise LocalError("invalid_configuration_keys")


def _string(value):
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise LocalError("invalid_configuration_value")
    return value


def _integer(value):
    if type(value) is not int or value < 1:
        raise LocalError("invalid_configuration_value")
    return value


@guarded("asset_checks")
def _root(value):
    path = _io.local_path(_string(value))
    if not path.is_absolute():
        raise LocalError("roots_must_be_absolute")
    path = path.resolve(strict=True)
    if not stat.S_ISDIR(_io.stat_file(path).st_mode):
        raise LocalError("root_must_be_directory")
    return path


@guarded("asset_checks")
def check_paths(config):
    """Recheck resolved paths immediately before any run-directory creation."""
    dataset = config.dataset_root.resolve(strict=True)
    output = config.output_root.resolve(strict=True)
    if output.is_relative_to(dataset):
        raise LocalError("output_overlaps_dataset")
    for path in config.assets.values():
        if not path.resolve().is_relative_to(dataset):
            raise LocalError("input_escapes_dataset")
    return dataset, output


@guarded("configuration")
def load_local_config(path: Path | str) -> LocalConfig:
    try:
        with _io.open_binary(_io.local_path(path)) as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise LocalError("configuration_too_large")
        d = tomllib.loads(raw.decode("utf-8-sig"))
        _keys(
            d,
            (
                "schema_version",
                "profile",
                "dataset_root",
                "output_root",
                "frame_count",
                "track_slots",
                "assets",
                "teams",
                "features",
                "rules",
                "diagnostics",
                "provenance",
            ),
            ("inference", "temporal"),
        )
        if (
            type(d["schema_version"]) is not int
            or d["schema_version"] != 1
            or d["profile"] not in ("phase1", "synthetic")
        ):
            raise LocalError("invalid_profile_or_schema")
        dataset, output = _root(d["dataset_root"]), _root(d["output_root"])
        _keys(d["assets"], ("metadata", "tracking"), ("homography", "smart_tagging"))
        assets = {}
        for name, value in d["assets"].items():
            relative = _io.local_path(_string(value))
            if relative.is_absolute() or relative.drive:
                raise LocalError("assets_must_be_relative")
            candidate = Path(os.path.abspath(dataset / relative))
            if not candidate.is_relative_to(dataset) or not candidate.resolve().is_relative_to(
                dataset
            ):
                raise LocalError("input_escapes_dataset")
            assets[name] = candidate
        teams = d["teams"]
        _keys(teams, ("home_id", "away_id", "tag_home", "tag_away"))
        for value in teams.values():
            _string(value)
        if (
            teams["home_id"] == teams["away_id"]
            or teams["tag_home"].casefold().strip() == teams["tag_away"].casefold().strip()
        ):
            raise LocalError("ambiguous_team_mapping")
        if any(
            teams[k].casefold().strip() in ("n/a", "na", "unknown")
            for k in ("tag_home", "tag_away")
        ):
            raise LocalError("unknown_tag_team_cannot_be_assigned")
        features = dict(d["features"])
        _keys(
            features,
            ("pitch_length_m", "pitch_width_m", "fps", "periods"),
            ("proximity_radii_m", "nearest_k"),
        )
        periods = []
        for p in features["periods"]:
            _keys(p, ("period_id", "start", "stop"))
            periods.append(Period(**p))
        features["periods"] = tuple(periods)
        if "proximity_radii_m" in features:
            features["proximity_radii_m"] = tuple(features["proximity_radii_m"])
        feature_config = FeatureConfig(**features)
        count, slots = _integer(d["frame_count"]), _integer(d["track_slots"])
        if any(p.stop > count for p in periods):
            raise LocalError("period_outside_timeline")
        if d["profile"] == "phase1" and (
            count != 199319
            or slots != 46
            or feature_config.fps != 25
            or tuple(periods) != PHASE1_PERIODS
        ):
            raise LocalError("phase1_contract_mismatch")
        _keys(
            d["diagnostics"],
            (),
            ("short_fragment_s", "max_short_fragment_fraction", "max_abstention_fraction"),
        )
        provenance = d["provenance"]
        _keys(provenance, ("parameter_basis", "reference"))
        if provenance["parameter_basis"] not in ("provisional", "licensed_external"):
            raise LocalError("invalid_parameter_provenance")
        _string(provenance["reference"])
        inference = d.get("inference", {"mode": "rules"})
        _keys(inference, ("mode",))
        mode = inference["mode"]
        if mode not in ("rules", "rules_temporal") or (
            (mode == "rules_temporal") != ("temporal" in d)
        ):
            raise LocalError("invalid_inference_mode")
        temporal = TemporalConfig.from_dict(d["temporal"]) if "temporal" in d else None
        if temporal is not None:
            OfflineTemporalDecoder(fps=feature_config.fps, config=temporal)
        result = LocalConfig(
            d["profile"],
            dataset,
            output,
            MappingProxyType(assets),
            count,
            slots,
            **teams,
            features=feature_config,
            rules=RuleConfig.from_dict(d["rules"]),
            diagnostics=DiagnosticConfig(**d["diagnostics"]),
            mode=mode,
            temporal=temporal,
            **provenance,
        )
        check_paths(result)
        return result
    except LocalError:
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        raise LocalError("invalid_configuration") from None
