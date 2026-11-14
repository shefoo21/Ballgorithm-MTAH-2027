"""Versioned, immutable inference contracts. Confidence is never a probability."""

import math
from dataclasses import asdict, dataclass, field, fields

from mtah.features import FeatureConfig, feature_schema


class InferenceError(ValueError):
    """Invalid contract or sequence, deliberately without observation values."""


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _setting(default, unit, description, *, maximum=None):
    return field(
        default=default,
        metadata={
            "unit": unit,
            "description": description,
            "exclusiveMinimum": 0,
            **({"maximum": maximum} if maximum is not None else {}),
        },
    )


@dataclass(frozen=True, slots=True)
class RuleConfig:
    """Provisional synthetic-design settings, not learned or competition optimized."""

    control_distance_m: float = _setting(2.0, "m", "Maximum nearest distance for control")
    control_margin_m: float = _setting(1.0, "m", "Minimum opponent-minus-own nearest margin")
    support_radius_m: float = _setting(3.0, "m", "Required existing feature radius with support")
    nearest_weight: float = _setting(
        0.75, "fraction", "Nearest versus mean-k score weight", maximum=1
    )
    max_control_ball_speed_mps: float = _setting(12.0, "m/s", "Upper ball speed for new control")
    max_speed_disagreement_mps: float = _setting(8.0, "m/s", "Maximum reported/derived discrepancy")
    max_proximity_rate_mps: float = _setting(10.0, "m/s", "Maximum absolute team proximity rate")
    min_team_visibility: float = _setting(
        0.25, "fraction", "Required visible fraction of slots", maximum=1
    )
    control_min_confidence: float = _setting(0.55, "score", "Minimum control score", maximum=1)
    dead_min_confidence: float = _setting(0.6, "score", "Minimum dead-ball score", maximum=1)
    min_source_confidence: float = _setting(
        0.3, "score", "Minimum source reliability for entry", maximum=1
    )
    min_continuity_confidence: float = _setting(
        0.2, "score", "Minimum carried-state score", maximum=1
    )
    quality_absent_factor: float = _setting(
        0.9, "factor", "Reliability without calibration metadata", maximum=1
    )
    quality_invalid_factor: float = _setting(
        0.2, "factor", "Reliability when calibration unavailable", maximum=1
    )
    quality_error_scale: float = _setting(
        10.0, "export-defined", "Error scale in 1/(1+error/scale)"
    )
    missing_motion_factor: float = _setting(
        0.8, "factor", "Reliability without derived ball motion", maximum=1
    )
    unreliable_motion_factor: float = _setting(
        0.25, "factor", "Reliability with invalid/disagreeing speed", maximum=1
    )
    coverage_change_factor: float = _setting(
        0.75, "factor", "Reliability when visible slot mask changes", maximum=1
    )
    tag_conflict_factor: float = _setting(
        0.7, "factor", "Reliability with opposing simultaneous tags", maximum=1
    )
    unknown_near_factor: float = _setting(
        0.4, "factor", "Reliability with an unknown-team nearby slot", maximum=1
    )
    acquire_confirm_s: float = _setting(0.2, "s", "Consecutive control support for initial owner")
    turnover_confirm_s: float = _setting(0.4, "s", "Consecutive opposing support to switch owner")
    dead_confirm_s: float = _setting(0.6, "s", "Consecutive corroborated stoppage support")
    restart_confirm_s: float = _setting(0.2, "s", "Consecutive control support after dead ball")
    missing_hold_s: float = _setting(1.0, "s", "Maximum unsupported owner age when ball missing")
    loose_hold_s: float = _setting(2.0, "s", "Maximum unsupported owner age otherwise")
    dead_hold_s: float = _setting(3.0, "s", "Maximum unsupported dead-state age")
    continuity_half_life_s: float = _setting(
        1.5, "s", "Half life of last directly supported confidence"
    )
    stop_ball_speed_mps: float = _setting(0.5, "m/s", "Upper observed ball speed for stoppage")
    stop_team_speed_mps: float = _setting(
        1.0, "m/s", "Upper median speed of each team for stoppage"
    )
    restart_speed_mps: float = _setting(
        1.0, "m/s", "Minimum ball speed during restart confirmation"
    )
    set_piece_dead_factor: float = _setting(
        0.75, "factor", "Dead score factor for inside set-piece evidence", maximum=1
    )

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if (
                not finite_number(value)
                or value <= 0
                or value > item.metadata.get("maximum", math.inf)
            ):
                raise InferenceError("Invalid rule configuration")
        if not self.stop_ball_speed_mps < self.restart_speed_mps <= self.max_control_ball_speed_mps:
            raise InferenceError("Inconsistent motion thresholds")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, settings):
        if type(settings) is not dict or set(settings) - {item.name for item in fields(cls)}:
            raise InferenceError("Invalid rule configuration keys")
        return cls(**settings)


def rule_schema():
    """JSON Schema plus units; all values strictly positive, factors bounded by one."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MTAH provisional rule configuration v1",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            item.name: {"type": "number", "default": item.default, **item.metadata}
            for item in fields(RuleConfig)
        },
        "description": "Synthetic-design assumptions. stop < restart <= maximum control speed.",
    }


@dataclass(frozen=True, slots=True)
class FeatureContract:
    config: FeatureConfig
    slot_teams: tuple[str | None, ...]

    def __post_init__(self):
        try:
            feature_schema(self.config, self.slot_teams)
        except ValueError:
            raise InferenceError("Invalid feature contract") from None

    def bind(self, rules):
        if not isinstance(rules, RuleConfig):
            raise InferenceError("Invalid rule configuration")
        try:
            return self.config.proximity_radii_m.index(rules.support_radius_m)
        except ValueError:
            raise InferenceError("Required support radius absent from feature contract") from None

    def manifest(self, rules):
        self.bind(rules)
        return {
            "schema_version": 1,
            "implementation": "causal-rules-v1",
            "settings_provenance": "synthetic-design-unvalidated",
            "feature_schema": feature_schema(self.config, self.slot_teams),
            "rules": rules.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class EvidenceScores:
    """Control/dead scores include reliability and must not exceed source_confidence."""

    video_frame: int
    period_id: int | None
    segment_start: bool
    source_confidence: float
    home_control: float
    away_control: float
    control_candidate: str | None
    dead_confidence: float
    dead_candidate: bool
    restart_motion: bool
    ball_missing: bool
    home_visibility: float
    away_visibility: float
    homography_provided: bool
    homography_valid: bool | None
    tags_provided: bool
    tags_unknown: bool
    tag_conflict: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Prediction:
    video_frame: int
    period_id: int | None
    label: str
    confidence: float
    held: bool
    reason_codes: tuple[str, ...]
    evidence: EvidenceScores

    @property
    def abstained(self):
        return self.label == "X"
