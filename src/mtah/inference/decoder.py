"""Causal bounded persistence, deliberately independent of feature extraction."""

import math
from dataclasses import dataclass, replace

from mtah.inference.contracts import InferenceError, Prediction, RuleConfig, finite_number
from mtah.inference.validation import validate_evidence


@dataclass(frozen=True, slots=True)
class _State:
    last_frame: int = -1
    period_id: int | None = None
    owner: str | None = None
    supported_at: int = -1
    supported_confidence: float = 0.0
    candidate: str | None = None
    candidate_count: int = 0
    dead_count: int = 0
    restart_armed: bool = False


class RuleDecoder:
    """Reuse across chunks of one ordered stream; start a new instance for a new stream.

    Scores are uncalibrated. No backdating, future fill, evaluator or GT dependence.
    Failed steps do not mutate state. Instances are not thread-safe.
    """

    def __init__(self, *, fps: float, rules: RuleConfig | None = None):
        self.rules = RuleConfig() if rules is None else rules
        if not isinstance(self.rules, RuleConfig) or not finite_number(fps) or fps <= 0:
            raise InferenceError("Invalid decoder configuration")
        self.fps = fps
        durations = (
            "acquire_confirm_s",
            "turnover_confirm_s",
            "dead_confirm_s",
            "restart_confirm_s",
        )
        try:
            self._counts = {
                name: max(1, math.ceil(getattr(self.rules, name) * fps)) for name in durations
            }
            if not math.isfinite(self.rules.continuity_half_life_s * fps):
                raise OverflowError
        except (OverflowError, ValueError):
            raise InferenceError("Decoder timing is not representable") from None
        self._state = _State()

    def step(self, evidence):
        validate_evidence(evidence)
        if evidence.video_frame <= self._state.last_frame:
            raise InferenceError("Inference frames must increase strictly")
        prediction, state = self._advance(evidence)
        self._state = state
        return prediction

    def _advance(self, e):
        s = self._state
        reset = e.segment_start or e.period_id != s.period_id or e.video_frame != s.last_frame + 1
        if reset:
            s = _State()
        s = replace(s, last_frame=e.video_frame, period_id=e.period_id)
        if e.period_id is None:
            return self._prediction(e, "X", 0.0, False, "outside_period"), _State(
                last_frame=e.video_frame
            )
        c = self.rules
        reliable = e.source_confidence >= c.min_source_confidence
        if e.dead_candidate and reliable and e.dead_confidence >= c.dead_min_confidence:
            s = replace(
                s,
                dead_count=s.dead_count + 1,
                candidate=None,
                candidate_count=0,
                restart_armed=False,
            )
            if s.owner == "D" or s.dead_count >= self._counts["dead_confirm_s"]:
                return self._confirm(
                    e,
                    s,
                    "D",
                    e.dead_confidence,
                    "dead_supported" if s.owner == "D" else "dead_confirmed",
                )
            return self._hold(e, s, "dead_pending")
        s = replace(s, dead_count=0)
        candidate = e.control_candidate if reliable else None
        score = e.home_control if candidate == "H" else e.away_control
        if score < c.control_min_confidence:
            candidate = None
        if candidate is None:
            s = replace(s, candidate=None, candidate_count=0, restart_armed=False)
            return self._hold(e, s, "missing_continuity" if e.ball_missing else "loose_continuity")
        if candidate == s.owner:
            return self._confirm(e, s, candidate, score, "control_supported")
        count = s.candidate_count + 1 if s.candidate == candidate else 1
        armed = e.restart_motion or (s.candidate == candidate and s.restart_armed)
        s = replace(s, candidate=candidate, candidate_count=count, restart_armed=armed)
        if s.owner == "D":
            duration, reason = "restart_confirm_s", "restart"
            ready = armed
        elif s.owner in ("H", "A"):
            duration, reason, ready = "turnover_confirm_s", "turnover", True
        else:
            duration, reason, ready = "acquire_confirm_s", "acquisition", True
        if count >= self._counts[duration] and ready:
            return self._confirm(e, s, candidate, score, reason + "_confirmed")
        return self._hold(e, s, reason + "_pending")

    def _confirm(self, e, s, owner, confidence, reason):
        s = replace(
            s,
            owner=owner,
            supported_at=e.video_frame,
            supported_confidence=confidence,
            candidate=None,
            candidate_count=0,
            dead_count=0,
            restart_armed=False,
        )
        return self._prediction(e, owner, confidence, False, reason), s

    def _hold(self, e, s, reason):
        if s.owner is None:
            return self._prediction(e, "X", 0.0, False, reason), s
        age_s = (e.video_frame - s.supported_at) / self.fps
        c = self.rules
        limit = (
            c.dead_hold_s
            if s.owner == "D"
            else (c.missing_hold_s if e.ball_missing else c.loose_hold_s)
        )
        confidence = min(
            e.source_confidence, s.supported_confidence * 2 ** (-age_s / c.continuity_half_life_s)
        )
        if age_s > limit or confidence < c.min_continuity_confidence:
            # Discard stale ownership; pending fresh evidence may continue, but never
            # resurrect a cached owner solely from another ambiguous observation.
            return self._prediction(e, "X", 0.0, False, "continuity_expired"), replace(
                s, owner=None
            )
        return self._prediction(e, s.owner, confidence, True, reason), s

    @staticmethod
    def _prediction(e, label, confidence, held, reason):
        return Prediction(
            e.video_frame, e.period_id, label, confidence, held, e.reason_codes + (reason,), e
        )
