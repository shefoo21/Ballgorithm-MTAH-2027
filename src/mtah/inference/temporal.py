"""Offline capped-age Viterbi over H/A/D; X is an explicit evidence-expiry policy.

No tracking I/O, evaluator, identities, GT, networking, fitting or match-specific boundaries.
Future observations may revise earlier decisions inside one bounded evidence island.
"""

import math
from array import array
from collections.abc import Iterable, Iterator

from mtah.inference.contracts import EvidenceScores, InferenceError, Prediction, finite_number
from mtah.inference.temporal_config import TemporalConfig, temporal_schema
from mtah.inference.validation import validate_evidence

__all__ = ["OfflineTemporalDecoder", "TemporalConfig", "temporal_schema"]
STATES = ("H", "A", "D")
_NONE = 65535


class OfflineTemporalDecoder:
    """Stateless across decode calls. Buffer only one evidence island; fail on resource limits.

    Exact ties choose the first predecessor and terminal index in H/A/D, youngest-age order.
    No causal/prefix-equivalence promise. Input failures are sanitized; iterators may already
    have yielded earlier complete islands, so publish via the existing atomic CSV writer.
    """

    def __init__(self, *, fps: float, config: TemporalConfig | None = None):
        self.config = TemporalConfig() if config is None else config
        if not isinstance(self.config, TemporalConfig) or not finite_number(fps) or fps <= 0:
            raise InferenceError("Invalid temporal decoder configuration")
        self.fps = fps
        try:
            self.age_bins = max(1, math.ceil(self.config.duration_s * fps))
            if (
                self.age_bins > self.config.max_age_bins
                or not math.isfinite(self.config.max_unsupported_s * fps)
                or not math.isfinite(self.config.continuity_half_life_s * fps)
                or not math.isfinite(self.config.observation_weight / fps)
            ):
                raise ValueError
        except (OverflowError, ValueError):
            raise InferenceError("Temporal timing exceeds resource bounds") from None
        self.width = 3 * self.age_bins

    def manifest(self):
        return {
            "schema_version": 1,
            "implementation": "offline-capped-age-viterbi-v1",
            "uses_future_observations": True,
            "fps": self.fps,
            "settings": self.config.to_dict(),
            "effective_age_bins": self.age_bins,
            "tie_order": "H_A_D_then_youngest_age_first_predecessor",
            "confidence_semantics": "bounded_uncalibrated_evidence_reliability",
            "settings_provenance": "provisional-engineering-unvalidated",
        }

    def _support(self, e):
        if e.ball_missing or e.source_confidence < self.config.min_source_confidence:
            return (0.0, 0.0, 0.0), None
        scores = (
            (0.0, 0.0, e.dead_confidence)
            if e.dead_candidate
            else (e.home_control, e.away_control, 0.0)
        )
        candidate = (
            2
            if e.dead_candidate
            else (STATES.index(e.control_candidate) if e.control_candidate else None)
        )
        if candidate is not None and scores[candidate] < self.config.min_support:
            candidate = None
        return scores, candidate

    def decode_segment(self, evidence: Iterable[EvidenceScores]) -> Iterator[Prediction]:
        """Strict contiguous, single non-null period entry point; uncertainty may split it."""

        def checked():
            last = None
            for e in evidence:
                validate_evidence(e)
                if (
                    e.period_id is None
                    or last is not None
                    and (
                        e.period_id != last.period_id
                        or e.video_frame != last.video_frame + 1
                        or e.segment_start
                    )
                ):
                    raise InferenceError("Invalid temporal segment")
                last = e
                yield e

        yield from self.decode(checked())

    def decode(self, evidence: Iterable[EvidenceScores]) -> Iterator[Prediction]:
        """Split at gaps, periods, explicit resets and expired direct evidence; never fill IDs."""
        buffer = []
        last = None
        last_anchor = None
        for e in evidence:
            validate_evidence(e)
            if last is not None and e.video_frame <= last.video_frame:
                raise InferenceError("Inference frames must increase strictly")
            reset = (
                last is None
                or e.segment_start
                or e.period_id != last.period_id
                or (e.video_frame != last.video_frame + 1)
            )
            if reset:
                yield from self._island(buffer)
                buffer.clear()
                last_anchor = None
            last = e
            _, anchor = self._support(e)
            # Check elapsed support BEFORE accepting a new anchor: future evidence cannot
            # reconnect two islands through an interval whose support has already expired.
            if last_anchor is not None and (
                e.video_frame - last_anchor > self.config.max_unsupported_s * self.fps
            ):
                yield from self._island(buffer)
                buffer.clear()
                last_anchor = None
            if e.period_id is None or (last_anchor is None and anchor is None):
                yield self._prediction(
                    e,
                    "X",
                    0.0,
                    False,
                    "outside_period" if e.period_id is None else "temporal_no_anchor",
                )
                continue
            if anchor is not None:
                last_anchor = e.video_frame
            size = len(buffer) + 1
            if (
                size > self.config.max_segment_frames
                or size * self.width * array("H").itemsize > self.config.max_backpointer_bytes
            ):
                raise InferenceError("Temporal segment exceeds resource bounds")
            buffer.append(e)
        yield from self._island(buffer)

    def _transition(self, source, destination, age, support):
        c = self.config
        base = (
            c.restart_cost
            if source == 2
            else (c.dead_entry_cost if destination == 2 else c.turnover_cost)
        )
        return base * (1 - c.turnover_discount * support) + c.short_exit_cost * (
            1 - age / self.age_bins
        ) * (1 - support)

    def _island(self, rows):
        if not rows:
            return
        m, width = self.age_bins, self.width
        # Exact payload allocation: repeated append/extend overallocates beyond the byte cap.
        pointers = array("H", [_NONE]) * (len(rows) * width)
        costs = [math.inf] * width
        _, initial = self._support(rows[0])
        costs[initial * m] = 0.0
        for t, e in enumerate(rows):
            scores, anchor = self._support(e)
            emissions = tuple(
                self.config.observation_weight * (e.source_confidence - s) / self.fps
                for s in scores
            )
            offset = t * width
            if t == 0:
                current = costs
                current[initial * m] = emissions[initial]
            else:
                current = [math.inf] * width
                for index, cost in enumerate(costs):
                    if not math.isfinite(cost):
                        continue
                    state, age0 = divmod(index, m)
                    stay = state * m + min(age0 + 1, m - 1)
                    value = cost + emissions[state]
                    if value < current[stay]:
                        current[stay], pointers[offset + stay] = value, index
                    if anchor is not None and anchor != state and (state != 2 or e.restart_motion):
                        target = anchor * m
                        value = (
                            cost
                            + emissions[anchor]
                            + self._transition(state, anchor, age0 + 1, scores[anchor])
                        )
                        if value < current[target]:
                            current[target], pointers[offset + target] = value, index
            minimum = min(current)
            if not math.isfinite(minimum):
                raise InferenceError("Temporal arithmetic is not representable")
            costs = [cost - minimum for cost in current]
        winner = min(range(width), key=costs.__getitem__)
        path = bytearray(len(rows))
        for t in range(len(rows) - 1, -1, -1):
            path[t] = winner // m
            if t:
                winner = pointers[t * width + winner]
        del pointers, costs
        last_state = supported_at = None
        confidence = 0.0
        for t, (e, state) in enumerate(zip(rows, path, strict=True)):
            scores, anchor = self._support(e)
            changed = state != last_state
            if changed:
                supported_at = None
            direct = anchor == state
            if direct:
                supported_at, confidence = t, scores[state]
            age_s = (t - supported_at) / self.fps if supported_at is not None else math.inf
            reliability = min(
                e.source_confidence, confidence * 2 ** (-age_s / self.config.continuity_half_life_s)
            )
            supported = (
                age_s <= self.config.max_unsupported_s and reliability >= self.config.min_confidence
            )
            reason = "temporal_direct" if direct else "temporal_continuity"
            if changed and direct:
                reason = "temporal_entry"
            yield self._prediction(
                e,
                STATES[state] if supported else "X",
                reliability if supported else 0.0,
                supported and not direct,
                reason if supported else "temporal_support_expired",
            )
            last_state = state

    @staticmethod
    def _prediction(e, label, confidence, held, reason):
        return Prediction(
            e.video_frame, e.period_id, label, confidence, held, e.reason_codes + (reason,), e
        )
