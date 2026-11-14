"""Versioned feature results and a machine-readable schema; NaNs stay NaNs in memory."""

from dataclasses import asdict, dataclass, field, fields

from mtah.features.contracts import FeatureConfig, FeatureError, validate_slot_teams


def _feature(unit, missing="never", axis=None):
    return field(metadata={"unit": unit, "missing": missing, "axis": axis})


@dataclass(frozen=True, slots=True)
class TeamFeatures:
    slots: int = _feature("slots")
    observed_slots: int = _feature("slots")
    missing_fraction: float = _feature("fraction", "NaN")
    outside_pitch_slots: int = _feature("slots")
    distance_count: int = _feature("slots")
    nearest_distance_m: float = _feature("m", "NaN")
    second_distance_m: float = _feature("m", "NaN")
    mean_k_distance_m: float = _feature("m", "NaN")
    mean_distance_m: float = _feature("m", "NaN")
    median_distance_m: float = _feature("m", "NaN")
    within_radius_counts: tuple[float, ...] = _feature("slots", "NaN", "proximity_radii_m")
    within_radius_fractions: tuple[float, ...] = _feature("fraction", "NaN", "proximity_radii_m")
    speed_count: int = _feature("slots")
    speed_median_mps: float = _feature("m/s", "NaN")
    speed_mad_mps: float = _feature("m/s", "NaN")
    local_speed_median_mps: float = _feature("m/s", "NaN")
    coverage_changed: bool | None = _feature("flag", "null")
    nearest_distance_rate_mps: float = _feature("m/s", "NaN")


@dataclass(frozen=True, slots=True)
class HomographyFeatures:
    provided: bool = _feature("flag")
    valid: bool | None = _feature("flag", "null")
    reprojection_error: float = _feature("export-defined", "NaN")
    error_missing: bool = _feature("flag")


@dataclass(frozen=True, slots=True)
class TagFeatures:
    provided: bool = _feature("flag")
    active_count: int | None = _feature("events", "null")
    home_count: int | None = _feature("events", "null")
    away_count: int | None = _feature("events", "null")
    unknown_team_count: int | None = _feature("events", "null")
    set_piece_count: int | None = _feature("events", "null")
    team_conflict: bool | None = _feature("flag", "null")


@dataclass(frozen=True, slots=True, repr=False)
class FrameFeatures:
    video_frame: int = _feature("video frame")
    period_id: int | None = _feature("period ID", "null")
    segment_start: bool = _feature("flag")
    frame_gap_before: int = _feature("frames")
    ball_x: float = _feature("normalized", "NaN")
    ball_y: float = _feature("normalized", "NaN")
    ball_missing: bool = _feature("flag")
    ball_outside_pitch: bool | None = _feature("flag", "null")
    ball_reported_speed_mps: float = _feature("m/s", "NaN")
    ball_speed_missing: bool = _feature("flag")
    ball_speed_invalid: bool = _feature("flag")
    ball_missing_streak: int = _feature("frames")
    ball_observation_age_frames: int | None = _feature("frames", "null")
    player_missing: tuple[bool, ...] = _feature("flag", axis="slots")
    player_speed_missing: tuple[bool, ...] = _feature("flag", axis="slots")
    player_speed_invalid: tuple[bool, ...] = _feature("flag", axis="slots")
    slot_ball_distance_m: tuple[float, ...] = _feature("m", "NaN", "slots")
    unknown_team_observed_slots: int = _feature("slots")
    home: TeamFeatures
    away: TeamFeatures
    nearest_margin_m: float = _feature("m", "NaN")
    nearest_tie: bool | None = _feature("flag", "null")
    distance_evidence_missing: bool = _feature("flag")
    ball_vx_mps: float = _feature("m/s", "NaN")
    ball_vy_mps: float = _feature("m/s", "NaN")
    ball_speed_from_positions_mps: float = _feature("m/s", "NaN")
    ball_speed_disagreement_mps: float = _feature("m/s", "NaN")
    ball_motion_missing: bool = _feature("flag")
    homography: HomographyFeatures
    tags: TagFeatures


def feature_schema(config: FeatureConfig, slot_teams: tuple[str | None, ...]) -> dict:
    """JSON-compatible schema metadata, without observations or source file paths."""
    if not isinstance(config, FeatureConfig):
        raise FeatureError("Invalid feature configuration")
    validate_slot_teams(slot_teams)
    groups = {TeamFeatures, HomographyFeatures, TagFeatures}

    def describe(model, prefix=""):
        for item in fields(model):
            name = prefix + item.name
            if item.type in groups:
                yield from describe(item.type, name + ".")
            else:
                yield {"name": name, "dtype": str(item.type), **item.metadata}

    settings = asdict(config)
    settings["periods"] = list(settings["periods"])
    settings["proximity_radii_m"] = list(settings["proximity_radii_m"])
    return {
        "schema_version": 1,
        "timeline": "tactical_video_zero_based",
        "settings": settings,
        "slot_teams": list(slot_teams),
        "fields": list(describe(FrameFeatures)),
    }
