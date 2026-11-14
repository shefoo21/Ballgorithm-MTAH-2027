"""Pure ATD parser. NaN is missing evidence, never an inferred possession label."""

import math
import re
from dataclasses import dataclass

from mtah.alignment import atd_to_video_frame


@dataclass(frozen=True)
class Observation:
    x: float
    y: float
    speed: float

    @property
    def observed(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y)


@dataclass(frozen=True)
class TrackingFrame:
    video_frame: int
    players: tuple[Observation, ...]
    ball: Observation


def _observation(text: str) -> Observation:
    parts = text.split(",")
    if len(parts) != 3:
        raise ValueError("Invalid observation")
    x, y, speed = (float(part) for part in parts)
    if any(math.isinf(value) for value in (x, y, speed)) or math.isnan(x) != math.isnan(y):
        raise ValueError("Invalid observation")
    return Observation(x, y, speed)


def parse_atd_line(line: str, *, expected_slots: int) -> TrackingFrame:
    """Parse one record without clipping coordinates or filling missing values.

    Slot order is retained; slots are not stable player identities. Error messages
    deliberately omit input values, even when a numeric conversion fails.
    """
    if type(expected_slots) is not int or expected_slots < 1:
        raise ValueError("Invalid slot count")
    try:
        frame, players_text, ball_text = line.strip().split(":")
        if re.fullmatch(r"[0-9]+", frame) is None:
            raise ValueError("Invalid frame")
        video_frame = atd_to_video_frame(int(frame))
        players = tuple(_observation(group) for group in players_text.split(";"))
        if len(players) != expected_slots:
            raise ValueError("Invalid slot count")
        return TrackingFrame(video_frame, players, _observation(ball_text))
    except (ValueError, AttributeError, OverflowError):
        raise ValueError("Invalid ATD record") from None
