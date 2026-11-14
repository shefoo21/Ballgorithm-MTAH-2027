"""Validate inference inputs, not files; never repair or recompute features."""

import math
from dataclasses import fields
from functools import cache
from types import UnionType
from typing import get_args, get_origin

from mtah.features import FrameFeatures, HomographyFeatures, TagFeatures, TeamFeatures
from mtah.inference.contracts import EvidenceScores, InferenceError, finite_number


@cache
def _layout(cls):
    return tuple((f.name, f.type) for f in fields(cls))


def _typed(value, kind):
    if kind is float:
        return type(value) in (int, float) and (
            finite_number(value) or (type(value) is float and math.isnan(value))
        )
    if kind in (int, bool, str, type(None)):
        return type(value) is kind
    if get_origin(kind) is UnionType:
        return any(_typed(value, part) for part in get_args(kind))
    if get_origin(kind) is tuple:
        return type(value) is tuple and all(_typed(v, get_args(kind)[0]) for v in value)
    return False


def _check_record(record, cls):
    if not isinstance(record, cls):
        raise InferenceError("Invalid inference input type")
    for name, kind in _layout(cls):
        value = getattr(record, name)
        if kind in (TeamFeatures, HomographyFeatures, TagFeatures):
            _check_record(value, kind)
        elif not _typed(value, kind):
            raise InferenceError("Invalid inference input field")


def validate_features(f, contract):
    _check_record(f, FrameFeatures)
    expected_period = next(
        (p.period_id for p in contract.config.periods if p.start <= f.video_frame < p.stop), None
    )
    if f.video_frame < 0 or f.frame_gap_before < 0 or f.period_id != expected_period:
        raise InferenceError("Invalid feature timeline")
    if (
        f.ball_missing_streak < 0
        or (f.ball_observation_age_frames is not None and f.ball_observation_age_frames < 0)
        or (
            not f.ball_missing
            and (f.ball_missing_streak != 0 or f.ball_observation_age_frames != 0)
        )
        or (f.ball_missing and f.ball_missing_streak == 0)
    ):
        raise InferenceError("Invalid missingness age")
    if f.ball_speed_from_positions_mps < 0 or f.ball_speed_disagreement_mps < 0:
        raise InferenceError("Invalid derived ball motion")
    disagreement_missing = f.ball_motion_missing or f.ball_speed_missing or f.ball_speed_invalid
    if math.isnan(f.ball_speed_disagreement_mps) != disagreement_missing or (
        not disagreement_missing
        and f.ball_speed_disagreement_mps
        != abs(f.ball_speed_from_positions_mps - f.ball_reported_speed_mps)
    ):
        raise InferenceError("Inconsistent ball speed disagreement")
    teams = contract.slot_teams
    if any(
        len(mask) != len(teams)
        for mask in (
            f.player_missing,
            f.player_speed_missing,
            f.player_speed_invalid,
            f.slot_ball_distance_m,
        )
    ):
        raise InferenceError("Invalid feature slot shape")
    if (
        math.isnan(f.ball_x) != f.ball_missing
        or math.isnan(f.ball_y) != f.ball_missing
        or (f.ball_outside_pitch is None) != f.ball_missing
        or math.isnan(f.ball_reported_speed_mps) != f.ball_speed_missing
        or (f.ball_reported_speed_mps < 0) != f.ball_speed_invalid
        or math.isnan(f.ball_speed_from_positions_mps) != f.ball_motion_missing
    ):
        raise InferenceError("Inconsistent feature missingness")
    if not f.ball_missing and f.ball_outside_pitch != (
        f.ball_x < 0 or f.ball_x > 1 or f.ball_y < 0 or f.ball_y > 1
    ):
        raise InferenceError("Inconsistent pitch indicator")
    for i, distance in enumerate(f.slot_ball_distance_m):
        if math.isnan(distance) != (f.ball_missing or f.player_missing[i]) or distance < 0:
            raise InferenceError("Inconsistent slot distance missingness")
    for team, name in ((f.home, "H"), (f.away, "A")):
        observed = sum(not f.player_missing[i] for i, t in enumerate(teams) if t == name)
        if (
            team.slots != teams.count(name)
            or team.observed_slots != observed
            or not 0 <= team.speed_count <= observed
            or not 0 <= team.outside_pitch_slots <= observed
            or team.distance_count != (0 if f.ball_missing else observed)
        ):
            raise InferenceError("Inconsistent team coverage")
        if (team.slots and team.missing_fraction != 1 - observed / team.slots) or (
            not team.slots and not math.isnan(team.missing_fraction)
        ):
            raise InferenceError("Inconsistent missing fraction")
        if len(team.within_radius_counts) != len(contract.config.proximity_radii_m) or len(
            team.within_radius_fractions
        ) != len(contract.config.proximity_radii_m):
            raise InferenceError("Invalid feature radius shape")
        for value in (team.nearest_distance_m, team.mean_k_distance_m):
            if math.isnan(value) != (team.distance_count == 0) or value < 0:
                raise InferenceError("Inconsistent team distance missingness")
        for value in team.within_radius_counts:
            if math.isnan(value) != (team.distance_count == 0) or (
                not math.isnan(value)
                and (value < 0 or value > team.distance_count or value != int(value))
            ):
                raise InferenceError("Invalid proximity support")
        for count, fraction in zip(
            team.within_radius_counts, team.within_radius_fractions, strict=True
        ):
            if (team.distance_count and fraction != count / team.distance_count) or (
                not team.distance_count and not math.isnan(fraction)
            ):
                raise InferenceError("Invalid proximity fraction")
        if (
            math.isnan(team.speed_median_mps) != (team.speed_count == 0)
            or team.speed_median_mps < 0
        ):
            raise InferenceError("Invalid team motion")
    quality = f.homography
    if (
        quality.error_missing != math.isnan(quality.reprojection_error)
        or quality.reprojection_error < 0
        or (quality.valid is None) == quality.provided
        or (quality.valid is True and quality.error_missing)
        or (not quality.provided and not quality.error_missing)
    ):
        raise InferenceError("Inconsistent calibration evidence")
    tag = f.tags
    counts = (
        tag.home_count,
        tag.away_count,
        tag.unknown_team_count,
        tag.set_piece_count,
        tag.active_count,
    )
    if tag.provided:
        if (
            any(v is None or v < 0 for v in counts)
            or sum(counts[:3]) != tag.active_count
            or tag.set_piece_count > tag.active_count
            or tag.team_conflict != (tag.home_count > 0 and tag.away_count > 0)
        ):
            raise InferenceError("Inconsistent tag evidence")
    elif any(v is not None for v in (*counts, tag.team_conflict)):
        raise InferenceError("Inconsistent absent tag evidence")


def validate_evidence(e):
    _check_record(e, EvidenceScores)
    scores = (
        e.source_confidence,
        e.home_control,
        e.away_control,
        e.dead_confidence,
        e.home_visibility,
        e.away_visibility,
    )
    if any(not finite_number(v) or not 0 <= v <= 1 for v in scores):
        raise InferenceError("Invalid evidence confidence")
    if any(v > e.source_confidence for v in (e.home_control, e.away_control, e.dead_confidence)):
        raise InferenceError("Decision evidence exceeds source confidence")
    if e.video_frame < 0 or (e.period_id is not None and e.period_id < 1):
        raise InferenceError("Invalid evidence timeline")
    if e.control_candidate not in (None, "H", "A"):
        raise InferenceError("Invalid control candidate")
    if (e.dead_candidate and e.ball_missing) or (e.dead_candidate and e.control_candidate):
        raise InferenceError("Contradictory decision evidence")
    if e.control_candidate and e.ball_missing:
        raise InferenceError("Control requires an observed ball")
