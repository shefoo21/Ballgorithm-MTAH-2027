"""Single-frame geometry and team summaries; never match a slot between frames."""

import math

from mtah.features.contracts import FeatureConfig, FeatureError
from mtah.features.schema import TeamFeatures
from mtah.tracking import Observation, TrackingFrame


def finite(value):
    if not math.isfinite(value):
        raise FeatureError("Feature arithmetic is not finite")
    return value


def outside_pitch(observation: Observation):
    return observation.observed and not (0 <= observation.x <= 1 and 0 <= observation.y <= 1)


def median(values):
    if not values:
        return math.nan
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    # Our medians contain nonnegative distances/speeds; avoid overflowing a+b.
    return finite(ordered[middle - 1] / 2 + ordered[middle] / 2)


def _mean(values):
    return finite(math.fsum(v / len(values) for v in values)) if values else math.nan


def distances(frame: TrackingFrame, config: FeatureConfig):
    if not frame.ball.observed:
        return (math.nan,) * len(frame.players)
    return tuple(
        finite(
            math.hypot(
                (player.x - frame.ball.x) * config.pitch_length_m,
                (player.y - frame.ball.y) * config.pitch_width_m,
            )
        )
        if player.observed
        else math.nan
        for player in frame.players
    )


def summarize_team(frame, slot_indices, ball_distances, config):
    visible = [i for i in slot_indices if frame.players[i].observed]
    ordered = sorted(ball_distances[i] for i in visible if math.isfinite(ball_distances[i]))
    speeds = [frame.players[i].speed for i in visible if frame.players[i].speed >= 0]
    speed_median = median(speeds)
    local_speeds = [
        frame.players[i].speed
        for i in visible
        if frame.players[i].speed >= 0 and ball_distances[i] <= config.proximity_radii_m[-1]
    ]
    counts = tuple(
        float(sum(distance <= radius for distance in ordered)) if ordered else math.nan
        for radius in config.proximity_radii_m
    )
    return TeamFeatures(
        slots=len(slot_indices),
        observed_slots=len(visible),
        missing_fraction=1 - len(visible) / len(slot_indices) if slot_indices else math.nan,
        outside_pitch_slots=sum(outside_pitch(frame.players[i]) for i in visible),
        distance_count=len(ordered),
        nearest_distance_m=ordered[0] if ordered else math.nan,
        second_distance_m=ordered[1] if len(ordered) > 1 else math.nan,
        mean_k_distance_m=_mean(ordered[: config.nearest_k]),
        mean_distance_m=_mean(ordered),
        median_distance_m=median(ordered),
        within_radius_counts=counts,
        within_radius_fractions=tuple(count / len(ordered) for count in counts)
        if ordered
        else counts,
        speed_count=len(speeds),
        speed_median_mps=speed_median,
        speed_mad_mps=median([abs(speed - speed_median) for speed in speeds]),
        local_speed_median_mps=median(local_speeds),
        coverage_changed=None,
        nearest_distance_rate_mps=math.nan,
    )
