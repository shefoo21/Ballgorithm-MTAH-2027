"""Causal tactical feature stream with explicit gaps, periods and uncertainty."""

import math
from bisect import bisect_right
from collections.abc import Iterable, Iterator
from dataclasses import replace

from mtah.features.context import TagCursor, quality_features
from mtah.features.contracts import (
    FeatureConfig,
    FeatureError,
    FeatureInput,
    TagInterval,
    validate_input,
    validate_slot_teams,
)
from mtah.features.schema import FrameFeatures
from mtah.features.spatial import distances, finite, outside_pitch, summarize_team


class FeatureExtractor:
    """Keep one prior output; reuse this instance across ordered chunks of one timeline.

    A new instance starts a new stream. This object is intentionally not thread-safe.
    Slot membership is positional metadata, never an assumption of player identity.
    """

    def __init__(
        self,
        config: FeatureConfig,
        slot_teams: tuple[str | None, ...],
        tags: Iterable[TagInterval] | None = None,
    ):
        if not isinstance(config, FeatureConfig):
            raise FeatureError("Invalid feature configuration")
        validate_slot_teams(slot_teams)
        self._config = config
        self._teams = slot_teams
        self._home = tuple(i for i, team in enumerate(slot_teams) if team == "H")
        self._away = tuple(i for i, team in enumerate(slot_teams) if team == "A")
        self._starts = tuple(period.start for period in config.periods)
        self._tags = TagCursor(tags)
        self._previous: FrameFeatures | None = None
        self._last_seen: int | None = None

    def _period_id(self, index):
        position = bisect_right(self._starts, index) - 1
        if position >= 0:
            period = self._config.periods[position]
            if index < period.stop:
                return period.period_id
        return None

    def _team_motion(self, current, previous, indices, missing, continuous):
        if not continuous:
            return current
        changed = any(missing[i] != self._previous.player_missing[i] for i in indices)
        rate = math.nan
        if not changed and all(
            math.isfinite(value)
            for value in (
                current.nearest_distance_m,
                previous.nearest_distance_m,
            )
        ):
            rate = finite(
                (current.nearest_distance_m - previous.nearest_distance_m) * self._config.fps
            )
        return replace(current, coverage_changed=changed, nearest_distance_rate_mps=rate)

    def transform(self, sample: FeatureInput) -> FrameFeatures:
        """Produce exactly one aligned row, or raise without updating stream state."""
        validate_input(sample, len(self._teams))
        try:
            return self._transform(sample)
        except (OverflowError, ZeroDivisionError):
            raise FeatureError("Feature arithmetic is not representable") from None

    def _transform(self, sample):
        frame = sample.tracking
        previous = self._previous
        index = frame.video_frame
        if previous is not None and index <= previous.video_frame:
            raise FeatureError("Feature frames must increase strictly")
        period_id = self._period_id(index)
        gap = index - previous.video_frame - 1 if previous is not None else 0
        start = previous is None or gap > 0 or period_id != previous.period_id
        continuous = not start and period_id is not None
        missing = tuple(not player.observed for player in frame.players)
        ball_missing = not frame.ball.observed
        ball_distances = distances(frame, self._config)
        home = summarize_team(frame, self._home, ball_distances, self._config)
        away = summarize_team(frame, self._away, ball_distances, self._config)
        if previous is not None:
            home = self._team_motion(home, previous.home, self._home, missing, continuous)
            away = self._team_motion(away, previous.away, self._away, missing, continuous)
        distance_missing = not all(
            math.isfinite(value)
            for value in (
                home.nearest_distance_m,
                away.nearest_distance_m,
            )
        )
        margin = math.nan if distance_missing else away.nearest_distance_m - home.nearest_distance_m
        vx = vy = position_speed = disagreement = math.nan
        if continuous and not previous.ball_missing and not ball_missing:
            vx = finite(
                (frame.ball.x - previous.ball_x) * self._config.pitch_length_m * self._config.fps
            )
            vy = finite(
                (frame.ball.y - previous.ball_y) * self._config.pitch_width_m * self._config.fps
            )
            position_speed = finite(math.hypot(vx, vy))
            if frame.ball.speed >= 0:
                disagreement = finite(abs(position_speed - frame.ball.speed))
        last_seen = None if start else self._last_seen
        if not ball_missing:
            last_seen = index
        missing_streak = (1 if start else previous.ball_missing_streak + 1) if ball_missing else 0
        # All checks/arithmetic precede tag advancement and state mutation.
        result = FrameFeatures(
            video_frame=index,
            period_id=period_id,
            segment_start=start,
            frame_gap_before=gap,
            ball_x=frame.ball.x,
            ball_y=frame.ball.y,
            ball_missing=ball_missing,
            ball_outside_pitch=None if ball_missing else outside_pitch(frame.ball),
            ball_reported_speed_mps=frame.ball.speed,
            ball_speed_missing=math.isnan(frame.ball.speed),
            ball_speed_invalid=frame.ball.speed < 0,
            ball_missing_streak=missing_streak,
            ball_observation_age_frames=None if last_seen is None else index - last_seen,
            player_missing=missing,
            player_speed_missing=tuple(math.isnan(player.speed) for player in frame.players),
            player_speed_invalid=tuple(player.speed < 0 for player in frame.players),
            slot_ball_distance_m=ball_distances,
            unknown_team_observed_slots=sum(
                not missing[i] for i, team in enumerate(self._teams) if team is None
            ),
            home=home,
            away=away,
            nearest_margin_m=margin,
            nearest_tie=None if distance_missing else margin == 0,
            distance_evidence_missing=distance_missing,
            ball_vx_mps=vx,
            ball_vy_mps=vy,
            ball_speed_from_positions_mps=position_speed,
            ball_speed_disagreement_mps=disagreement,
            ball_motion_missing=math.isnan(position_speed),
            homography=quality_features(sample.homography),
            tags=self._tags.at(index),
        )
        self._previous = result
        self._last_seen = last_seen
        return result


def iter_features(
    samples: Iterable[FeatureInput],
    *,
    config: FeatureConfig,
    slot_teams: tuple[str | None, ...],
    tags: Iterable[TagInterval] | None = None,
) -> Iterator[FrameFeatures]:
    """Lazily consume samples in their original order; never discover, fill or write data."""
    engine = FeatureExtractor(config, slot_teams, tags)
    for sample in samples:
        yield engine.transform(sample)
