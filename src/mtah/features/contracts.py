"""Immutable tactical feature inputs. No I/O, identities, labels or inferred defaults."""

import math
from dataclasses import dataclass, field

from mtah.alignment import seconds_to_video_frame
from mtah.tracking import Observation, TrackingFrame


class FeatureError(ValueError):
    """Sanitized invalid-input/undefined-arithmetic failure, without input values."""


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return not math.isinf(value)
    except OverflowError:
        return False


def _positive(value):
    return _number(value) and math.isfinite(value) and value > 0


@dataclass(frozen=True, slots=True)
class Period:
    period_id: int
    start: int
    stop: int

    def __post_init__(self):
        if not (_integer(self.period_id, 1) and _integer(self.start) and _integer(self.stop)):
            raise FeatureError("Invalid period")
        if self.stop <= self.start:
            raise FeatureError("Invalid period")


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    pitch_length_m: float
    pitch_width_m: float
    fps: float
    periods: tuple[Period, ...]
    proximity_radii_m: tuple[float, ...] = (1.0, 3.0, 5.0)
    nearest_k: int = 3

    def __post_init__(self):
        if not all(_positive(v) for v in (self.pitch_length_m, self.pitch_width_m, self.fps)):
            raise FeatureError("Invalid feature dimensions or frame rate")
        radii = self.proximity_radii_m
        if type(radii) is not tuple or not radii or not all(_positive(v) for v in radii):
            raise FeatureError("Invalid proximity radii")
        if any(a >= b for a, b in zip(radii, radii[1:], strict=False)):
            raise FeatureError("Invalid proximity radii")
        if not _integer(self.nearest_k, 1):
            raise FeatureError("Invalid nearest count")
        if type(self.periods) is not tuple or not self.periods:
            raise FeatureError("Invalid period layout")
        if any(not isinstance(p, Period) for p in self.periods):
            raise FeatureError("Invalid period layout")
        if len({p.period_id for p in self.periods}) != len(self.periods) or any(
            a.stop > b.start for a, b in zip(self.periods, self.periods[1:], strict=False)
        ):
            raise FeatureError("Invalid period layout")


def validate_slot_teams(slot_teams):
    if (
        type(slot_teams) is not tuple
        or not slot_teams
        or any(
            team is not None and (type(team) is not str or team not in ("H", "A"))
            for team in slot_teams
        )
    ):
        raise FeatureError("Invalid slot-team mapping")


@dataclass(frozen=True, slots=True)
class HomographyQuality:
    video_frame: int
    valid: bool
    reprojection_error: float = field(repr=False)

    def __post_init__(self):
        error = self.reprojection_error
        if not _integer(self.video_frame) or type(self.valid) is not bool or not _number(error):
            raise FeatureError("Invalid homography quality")
        if (self.valid and math.isnan(error)) or error < 0:
            raise FeatureError("Invalid homography quality")


@dataclass(frozen=True, slots=True)
class TagInterval:
    start: int
    stop: int
    code: str = field(repr=False)
    team: str | None = None

    def __post_init__(self):
        if not _integer(self.start) or not _integer(self.stop) or self.stop <= self.start:
            raise FeatureError("Invalid tag interval")
        if type(self.code) is not str or not self.code.strip():
            raise FeatureError("Invalid tag code")
        if self.team is not None and (type(self.team) is not str or self.team not in ("H", "A")):
            raise FeatureError("Invalid tag team")

    @classmethod
    def from_seconds(cls, start, stop, code, team=None, *, fps):
        try:
            return cls(
                seconds_to_video_frame(start, fps), seconds_to_video_frame(stop, fps), code, team
            )
        except (ValueError, TypeError, OverflowError):
            raise FeatureError("Invalid tag timing or metadata") from None


@dataclass(frozen=True, slots=True)
class FeatureInput:
    tracking: TrackingFrame = field(repr=False)
    homography: HomographyQuality | None = None


def validate_input(sample, slot_count):
    if not isinstance(sample, FeatureInput) or not isinstance(sample.tracking, TrackingFrame):
        raise FeatureError("Invalid feature input")
    frame = sample.tracking
    if not _integer(frame.video_frame):
        raise FeatureError("Invalid feature frame")
    if type(frame.players) is not tuple or len(frame.players) != slot_count:
        raise FeatureError("Invalid feature slot count")
    for item in (*frame.players, frame.ball):
        if not isinstance(item, Observation) or not all(
            _number(v) for v in (item.x, item.y, item.speed)
        ):
            raise FeatureError("Invalid feature observation")
        if math.isnan(item.x) != math.isnan(item.y):
            raise FeatureError("Invalid feature observation")
    quality = sample.homography
    if quality is not None and (
        not isinstance(quality, HomographyQuality) or quality.video_frame != frame.video_frame
    ):
        raise FeatureError("Homography quality is not aligned to the input frame")
