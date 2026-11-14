"""Label runs for diagnostics only. The official evaluator defines scored spells."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelRun:
    start: int
    stop: int
    label: str


def label_runs(labels: Iterable[str], *, breaks: Iterable[int] = ()) -> tuple[LabelRun, ...]:
    """Return half-open spans, preserving D, X and explicit sequence boundaries."""
    values = tuple(labels)
    boundaries = tuple(breaks)
    if any(type(value) is not str or value not in ("H", "A", "D", "X") for value in values):
        raise ValueError("Invalid possession label")
    if any(type(b) is not int or not 0 < b < len(values) for b in boundaries):
        raise ValueError("Invalid sequence boundary")
    if not values:
        return ()
    split_at = set(boundaries)
    runs = []
    start = 0
    for index in range(1, len(values)):
        if values[index] != values[start] or index in split_at:
            runs.append(LabelRun(start, index, values[start]))
            start = index
    runs.append(LabelRun(start, len(values), values[start]))
    return tuple(runs)
