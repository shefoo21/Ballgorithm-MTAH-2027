"""Timeline conversions; no hidden tracking counter or cross-camera offsets."""

import math


def atd_to_video_frame(frame_id: int) -> int:
    if type(frame_id) is not int or frame_id < 1:
        raise ValueError("ATD frame must be a positive integer")
    return frame_id - 1


def video_to_atd_frame(video_frame: int) -> int:
    if type(video_frame) is not int or video_frame < 0:
        raise ValueError("Video frame must be a nonnegative integer")
    return video_frame + 1


def seconds_to_video_frame(seconds: float, fps: float) -> int:
    """Nearest frame, with Python's ties-to-even rounding as in the public starter."""
    if (
        type(seconds) not in (int, float)
        or type(fps) not in (int, float)
        or not math.isfinite(seconds)
        or not math.isfinite(fps)
        or seconds < 0
        or fps <= 0
        or not math.isfinite(seconds * fps)
    ):
        raise ValueError("Invalid video time or frame rate")
    return round(seconds * fps)
