"""Pure feature-to-evidence rules. No labels, histories, file access or identities."""

import math

from mtah.inference.contracts import EvidenceScores, FeatureContract, InferenceError, RuleConfig
from mtah.inference.validation import validate_features


class EvidenceModel:
    def __init__(self, contract: FeatureContract, rules: RuleConfig | None = None):
        if not isinstance(contract, FeatureContract):
            raise InferenceError("Invalid feature contract")
        self.contract = contract
        self.rules = RuleConfig() if rules is None else rules
        self._radius = contract.bind(self.rules)

    def score(self, features):
        """Return bounded heuristic support; validate before any numeric operations."""
        validate_features(features, self.contract)
        try:
            return self._score(features)
        except (OverflowError, ZeroDivisionError):
            raise InferenceError("Evidence arithmetic is not representable") from None

    def _score(self, f):
        c = self.rules
        reasons = []
        visibility = tuple(t.observed_slots / t.slots if t.slots else 0.0 for t in (f.home, f.away))
        coverage = min(1.0, min(visibility) / c.min_team_visibility)
        source = coverage
        if coverage < 1:
            reasons.append("low_team_coverage")
        quality = f.homography
        if not quality.provided:
            source *= c.quality_absent_factor
            reasons.append("calibration_not_provided")
        elif not quality.valid:
            source *= c.quality_invalid_factor
            reasons.append("calibration_unavailable")
        else:
            source *= 1 / (1 + quality.reprojection_error / c.quality_error_scale)
        if f.ball_missing:
            reasons.append("ball_missing")
        if f.ball_motion_missing:
            source *= c.missing_motion_factor
            reasons.append("ball_motion_missing")
        unreliable = (
            f.ball_speed_invalid
            or any(f.player_speed_invalid)
            or f.ball_speed_disagreement_mps > c.max_speed_disagreement_mps
        )
        if unreliable:
            source *= c.unreliable_motion_factor
            reasons.append("unreliable_motion")
        if f.home.coverage_changed or f.away.coverage_changed:
            source *= c.coverage_change_factor
            reasons.append("coverage_changed")
        conflict = f.tags.team_conflict is True
        if conflict:
            source *= c.tag_conflict_factor
            reasons.append("tag_conflict")
        unknown_near = any(
            team is None and d <= c.support_radius_m
            for team, d in zip(self.contract.slot_teams, f.slot_ball_distance_m, strict=True)
        )
        if unknown_near:
            source *= c.unknown_near_factor
            reasons.append("unknown_team_near_ball")
        speeds = tuple(
            v
            for v in (f.ball_reported_speed_mps, f.ball_speed_from_positions_mps)
            if math.isfinite(v) and v >= 0
        )
        speed = max(speeds, default=math.nan)
        if speed > c.max_control_ball_speed_mps:
            reasons.append("fast_ball")
        scores = tuple(self._geometry(team) * source for team in (f.home, f.away))
        stationary = (
            not f.ball_missing
            and not f.ball_motion_missing
            and speed <= c.stop_ball_speed_mps
            and all(t.speed_median_mps <= c.stop_team_speed_mps for t in (f.home, f.away))
        )
        set_piece = bool(f.tags.set_piece_count)
        dead_score = 0.0
        if stationary and coverage == 1 and not unreliable and not conflict:
            if f.ball_outside_pitch:
                dead_score = source
            elif set_piece:
                dead_score = source * c.set_piece_dead_factor
        dead_candidate = dead_score >= c.dead_min_confidence and source >= c.min_source_confidence
        candidate = None
        if (
            not f.ball_missing
            and f.ball_outside_pitch is False
            and not unreliable
            and not unknown_near
            and coverage == 1
            and speed <= c.max_control_ball_speed_mps
            and source >= c.min_source_confidence
            and not dead_candidate
        ):
            for own, other, label, score in (
                (f.home, f.away, "H", scores[0]),
                (f.away, f.home, "A", scores[1]),
            ):
                rate = own.nearest_distance_rate_mps
                if (
                    own.nearest_distance_m <= c.control_distance_m
                    and other.nearest_distance_m - own.nearest_distance_m >= c.control_margin_m
                    and own.within_radius_counts[self._radius] >= 1
                    and (math.isnan(rate) or abs(rate) <= c.max_proximity_rate_mps)
                    and score >= c.control_min_confidence
                ):
                    candidate = label
        if dead_candidate:
            reasons.append("corroborated_stoppage")
        elif candidate:
            reasons.append("control_candidate")
        else:
            reasons.append("insufficient_control")
        return EvidenceScores(
            f.video_frame,
            f.period_id,
            f.segment_start,
            source,
            *scores,
            candidate,
            dead_score,
            dead_candidate,
            bool(candidate and speed >= c.restart_speed_mps),
            f.ball_missing,
            *visibility,
            quality.provided,
            quality.valid,
            f.tags.provided,
            bool(f.tags.unknown_team_count),
            conflict,
            tuple(reasons),
        )

    def _geometry(self, team):
        if not math.isfinite(team.nearest_distance_m) or not math.isfinite(team.mean_k_distance_m):
            return 0.0
        c = self.rules
        return c.nearest_weight / (1 + team.nearest_distance_m / c.control_distance_m) + (
            1 - c.nearest_weight
        ) / (1 + team.mean_k_distance_m / c.support_radius_m)
