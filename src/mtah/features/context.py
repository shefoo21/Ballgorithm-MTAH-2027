"""Optional automatic context: aggregate uncertain tags and aligned quality metadata."""

import heapq
import math
from collections import Counter

from mtah.features.contracts import FeatureError, TagInterval
from mtah.features.schema import HomographyFeatures, TagFeatures


def quality_features(quality):
    if quality is None:
        return HomographyFeatures(False, None, math.nan, True)
    return HomographyFeatures(
        True, quality.valid, quality.reprojection_error, math.isnan(quality.reprojection_error)
    )


class TagCursor:
    """Sweep half-open intervals once, with O(events) storage and no per-frame rescan."""

    def __init__(self, events):
        self._provided = events is not None
        try:
            items = () if events is None else tuple(events)
        except TypeError:
            raise FeatureError("Invalid tag collection") from None
        if any(not isinstance(item, TagInterval) for item in items):
            raise FeatureError("Invalid tag collection")
        self._events = tuple(
            sorted(
                items,
                key=lambda item: (
                    item.start,
                    item.stop,
                    item.code.strip().casefold(),
                    item.team or "",
                ),
            )
        )
        self._position = 0
        self._active = []
        self._teams = Counter()
        self._set_pieces = 0

    def at(self, frame):
        if not self._provided:
            return TagFeatures(False, None, None, None, None, None, None)
        while self._active and self._active[0][0] <= frame:
            _, _, team, set_piece = heapq.heappop(self._active)
            self._teams[team] -= 1
            self._set_pieces -= set_piece
        while self._position < len(self._events):
            event = self._events[self._position]
            if event.start > frame:
                break
            ordinal = self._position
            self._position += 1
            if event.stop <= frame:
                continue
            set_piece = event.code.strip().casefold() == "set pieces"
            heapq.heappush(self._active, (event.stop, ordinal, event.team, set_piece))
            self._teams[event.team] += 1
            self._set_pieces += set_piece
        return TagFeatures(
            True,
            len(self._active),
            self._teams["H"],
            self._teams["A"],
            self._teams[None],
            self._set_pieces,
            self._teams["H"] > 0 and self._teams["A"] > 0,
        )
