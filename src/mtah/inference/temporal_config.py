"""Versioned provisional temporal settings; no fitting or data-dependent defaults."""

from dataclasses import asdict, dataclass, field, fields

from mtah.inference.contracts import InferenceError, finite_number


def _parameter(default, unit, description, *, minimum=0, maximum=1e6, integer=False):
    return field(
        default=default,
        metadata={
            "unit": unit,
            "description": description,
            "minimum": minimum,
            "maximum": maximum,
            "type": "integer" if integer else "number",
        },
    )


@dataclass(frozen=True, slots=True)
class TemporalConfig:
    """Costs are support-seconds, not negative log probabilities. Schema version 1."""

    observation_weight: float = _parameter(
        1.0, "factor", "Linear observation cost weight", minimum=1e-6
    )
    turnover_cost: float = _parameter(0.12, "cost", "H/A change base cost")
    dead_entry_cost: float = _parameter(0.12, "cost", "H/A to corroborated D cost")
    restart_cost: float = _parameter(0.12, "cost", "D to motion-supported H/A cost")
    turnover_discount: float = _parameter(
        0.8, "fraction", "Evidence discount on every transition", maximum=1
    )
    duration_s: float = _parameter(
        0.4, "s", "Dwell age at which soft exit penalty vanishes", minimum=1e-6
    )
    short_exit_cost: float = _parameter(0.08, "cost", "Maximum soft early-exit penalty")
    min_source_confidence: float = _parameter(
        0.3, "score", "Minimum reliable source", minimum=1e-6, maximum=1
    )
    min_support: float = _parameter(
        0.55, "score", "Minimum score of a flagged direct candidate", minimum=1e-6, maximum=1
    )
    min_confidence: float = _parameter(
        0.2, "score", "Minimum emitted reliability", minimum=1e-6, maximum=1
    )
    max_unsupported_s: float = _parameter(
        1.0, "s", "Maximum time since any direct anchor before reset"
    )
    continuity_half_life_s: float = _parameter(
        1.5, "s", "Decay of last selected direct support", minimum=1e-6
    )
    max_segment_frames: int = _parameter(
        200000,
        "frames",
        "Maximum buffered evidence island",
        minimum=1,
        maximum=1000000,
        integer=True,
    )
    max_age_bins: int = _parameter(
        64,
        "bins",
        "Reject dwell discretization larger than this",
        minimum=1,
        maximum=256,
        integer=True,
    )
    max_backpointer_bytes: int = _parameter(
        64 * 1024 * 1024,
        "bytes",
        "Maximum traceback array allocation",
        minimum=1,
        maximum=512 * 1024 * 1024,
        integer=True,
    )

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if (
                not finite_number(value)
                or item.metadata["type"] == "integer"
                and type(value) is not int
                or not item.metadata["minimum"] <= value <= item.metadata["maximum"]
            ):
                raise InferenceError("Invalid temporal configuration")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, settings):
        if type(settings) is not dict or set(settings) - {f.name for f in fields(cls)}:
            raise InferenceError("Invalid temporal configuration keys")
        return cls(**settings)


def temporal_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MTAH offline temporal configuration v1",
        "type": "object",
        "additionalProperties": False,
        "description": "Provisional, uncalibrated. ceil(duration_s * fps) <= max_age_bins.",
        "properties": {
            f.name: {"default": f.default, **f.metadata} for f in fields(TemporalConfig)
        },
    }
