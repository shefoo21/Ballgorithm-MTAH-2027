"""Invented evidence only; these labels are software specifications, not match accuracy."""

from dataclasses import replace

import pytest

from mtah.inference import EvidenceScores, InferenceError, RuleDecoder
from mtah.inference.temporal import OfflineTemporalDecoder, TemporalConfig, temporal_schema


def evidence(frame, state="H", *, strength=0.95, **changes):
    item = EvidenceScores(
        video_frame=frame,
        period_id=1,
        segment_start=frame == 0,
        source_confidence=1.0,
        home_control=strength if state == "H" else 0.05,
        away_control=strength if state == "A" else 0.05,
        control_candidate=state if state in ("H", "A") else None,
        dead_confidence=strength if state == "D" else 0.0,
        dead_candidate=state == "D",
        restart_motion=state in ("H", "A"),
        ball_missing=state == "X",
        home_visibility=1.0,
        away_visibility=1.0,
        homography_provided=False,
        homography_valid=None,
        tags_provided=False,
        tags_unknown=False,
        tag_conflict=False,
        reason_codes=(),
    )
    if state == "X":
        item = replace(item, home_control=0.0, away_control=0.0)
    return replace(item, **changes)


def scene(labels, **kwargs):
    return [evidence(i, s, **kwargs) for i, s in enumerate(labels)]


def labels(rows):
    return "".join(p.label for p in rows)


def decode(rows, *, fps=25, **settings):
    return list(OfflineTemporalDecoder(fps=fps, config=TemporalConfig(**settings)).decode(rows))


def test_long_control_and_short_strong_possession_are_preserved():
    authored = "H" * 60 + "A" * 4 + "H" * 60
    result = decode(scene(authored))
    assert labels(result) == authored
    assert all(p.confidence <= p.evidence.source_confidence for p in result)
    causal = RuleDecoder(fps=25)
    assert "A" not in labels(causal.step(e) for e in scene(authored))


def test_deflection_without_control_cannot_create_turnover():
    rows = scene("H" * 40)
    rows[20] = evidence(20, "A", control_candidate=None)
    assert labels(decode(rows)) == "H" * 40


def test_turnover_and_closely_spaced_control_changes():
    authored = "H" * 20 + "A" * 5 + "H" * 5 + "A" * 30
    assert labels(decode(scene(authored))) == authored


def test_long_missing_interval_expires_and_cannot_backfill_from_new_owner():
    result = decode(scene("H" * 30 + "X" * 80 + "A" * 30))
    assert labels(result[:30]) == "H" * 30
    assert labels(result[55:110]) == "X" * 55
    assert "A" not in labels(result[:110])
    assert "D" not in labels(result)
    assert labels(result[110:]) == "A" * 30
    assert all(p.confidence == 0 for p in result if p.label == "X")


def test_dead_ball_and_restart_need_current_corroboration():
    authored = "H" * 40 + "D" * 40 + "A" * 40
    rows = scene(authored)
    assert labels(decode(rows)) == authored
    # Missing ball cannot initiate D; stationary control cannot by itself leave established D.
    stationary = scene("D" * 80 + "H" * 4, restart_motion=False)
    assert "H" not in labels(decode(stationary))


def test_all_ambiguous_and_low_confidence_candidates_abstain():
    assert labels(decode(scene("X" * 100))) == "X" * 100
    weak = scene("H" * 100, strength=0.1, source_confidence=0.1)
    assert labels(decode(weak)) == "X" * 100


def test_periods_gaps_and_explicit_segments_reset_everything():
    first = scene("H" * 30)
    for reset in ({"period_id": 2}, {"segment_start": True}, {"video_frame": 99}):
        tail = evidence(30, "X", **reset) if "video_frame" not in reset else evidence(99, "X")
        result = decode(first + [tail])
        assert result[-1].label == "X"
        assert result[-1].video_frame == tail.video_frame
    outside = evidence(30, "H", period_id=None)
    assert decode(first + [outside])[-1].label == "X"


@pytest.mark.parametrize(
    "changes",
    [
        {"source_confidence": float("nan")},
        {"home_control": 1.1},
        {"video_frame": -1},
        {"period_id": 0},
        {"control_candidate": "D"},
        {"ball_missing": True},
        {"dead_candidate": True},
    ],
)
def test_malformed_evidence_fails_without_exposing_values(changes):
    with pytest.raises(InferenceError):
        decode([evidence(0, **changes)])


def test_order_segment_and_resource_contracts_are_strict():
    decoder = OfflineTemporalDecoder(fps=25, config=TemporalConfig(max_segment_frames=3))
    with pytest.raises(InferenceError):
        list(decoder.decode(scene("HHHH")))
    for frames in ([0, 0], [2, 1]):
        with pytest.raises(InferenceError):
            decode([evidence(i) for i in frames])
    with pytest.raises(InferenceError):
        list(OfflineTemporalDecoder(fps=25).decode_segment([evidence(0), evidence(2)]))
    with pytest.raises(InferenceError):
        decode(scene("HH"), max_backpointer_bytes=1)


@pytest.mark.parametrize(
    "settings",
    [
        {"turnover_cost": -1},
        {"duration_s": 0},
        {"min_support": True},
        {"min_confidence": 1.1},
        {"continuity_half_life_s": float("inf")},
        {"max_segment_frames": 1.2},
        {"max_age_bins": 65536},
        {"turnover_discount": 2},
        {"min_support": float("nan")},
    ],
)
def test_bad_settings_rejected(settings):
    with pytest.raises(InferenceError):
        TemporalConfig(**settings)


def test_config_schema_roundtrip_unknown_keys_and_timing_bounds():
    config = TemporalConfig()
    assert TemporalConfig.from_dict(config.to_dict()) == config
    assert set(temporal_schema()["properties"]) == set(config.to_dict())
    with pytest.raises(InferenceError):
        TemporalConfig.from_dict({"unknown": 3})
    for fps in (0, True, float("nan"), 1e308):
        with pytest.raises(InferenceError):
            OfflineTemporalDecoder(fps=fps)


def test_original_evidence_is_preserved_and_repeated_decoding_identical():
    rows = scene("H" * 20 + "A" * 3 + "H" * 20)
    result = decode(rows)
    assert result == decode(rows)
    assert all(p.evidence is e for p, e in zip(result, rows, strict=True))


def test_future_context_can_reject_a_brief_weak_control_candidate():
    prefix = scene("H" * 20) + [evidence(i, "A", strength=0.6) for i in range(20, 23)]
    extended = prefix + [evidence(i, "H") for i in range(23, 43)]
    assert labels(decode(prefix)).endswith("AAA")
    assert labels(decode(extended)) == "H" * 43


@pytest.mark.parametrize("duration_s", [0.04, 0.4])
def test_exact_cost_ties_have_documented_state_order(duration_s):
    rows = [evidence(0)] + [evidence(i, "A", home_control=0.95) for i in range(1, 10)]
    assert (
        labels(decode(rows, turnover_cost=0, short_exit_cost=0, duration_s=duration_s)) == "H" * 10
    )


def test_exhaustive_short_paths_match_soft_duration_objective():
    # Enumerate whole paths (no DP/helpers from production). A wrong age, transition gate,
    # observation scale or traceback changes the independently calculated optimum.
    from itertools import product

    rows = [
        evidence(i, s, strength=q)
        for i, (s, q) in enumerate(
            zip("HAAHDHA", (0.95, 0.6, 0.95, 0.9, 0.95, 0.95, 0.6), strict=True)
        )
    ]

    def objective(path):
        if path[0] != "H":
            return float("inf")
        cost, run_start = 0.0, 0
        for i, state in enumerate(path):
            e = rows[i]
            supports = {"H": e.home_control, "A": e.away_control, "D": 0.0}
            if e.dead_candidate:
                supports = {"H": 0.0, "A": 0.0, "D": e.dead_confidence}
            cost += (1 - supports[state]) / 10
            if i and state != path[i - 1]:
                if state != ("D" if e.dead_candidate else e.control_candidate):
                    return float("inf")
                age = min(i - run_start, 4)
                cost += 0.12 * (1 - 0.8 * supports[state])
                cost += 0.08 * (1 - age / 4) * (1 - supports[state])
                run_start = i
        return cost

    optimum = min(objective(p) for p in product("HAD", repeat=len(rows)))
    result = labels(decode(rows, fps=10))
    assert "X" not in result
    assert objective(result) == pytest.approx(optimum, abs=1e-12)


def test_conflicting_tags_do_not_become_team_labels_or_dead_ball():
    from test_inference import CONFIG, TEAMS, rows

    from mtah.features import TagInterval
    from mtah.inference import EvidenceModel, FeatureContract

    model = EvidenceModel(FeatureContract(CONFIG, TEAMS))
    features = list(
        rows(
            [0.2] * 50,
            tags=(TagInterval(0, 50, "set pieces", "H"), TagInterval(0, 50, "defence", "A")),
        )
    )
    evidence_rows = [model.score(f) for f in features]
    predictions = decode(evidence_rows, fps=10)
    assert "A" not in labels(predictions) and "D" not in labels(predictions)
    assert labels(predictions).endswith("H" * 40)
    assert all(e.tag_conflict for e in evidence_rows)
    assert all(
        p.confidence <= e.source_confidence for p, e in zip(predictions, evidence_rows, strict=True)
    )


def test_expired_gap_future_changes_do_not_modify_prior_island():
    prefix = scene("H" * 20 + "X" * 60)
    home = prefix + [evidence(i, "H") for i in range(80, 100)]
    away = prefix + [evidence(i, "A") for i in range(80, 100)]
    assert decode(home)[:80] == decode(away)[:80]


def test_empty_single_frame_and_observed_ambiguity_have_explicit_behavior():
    assert decode([]) == []
    assert labels(decode(scene("H"))) == "H"
    assert labels(decode(scene("D"))) == "D"
    ambiguous = [evidence(i, "H", control_candidate=None) for i in range(100)]
    assert labels(decode(ambiguous)) == "X" * 100


def test_traceback_allocation_respects_exact_payload_cap(monkeypatch):
    from array import array

    from mtah.inference import temporal

    allocated = []

    class ObservedArray(array):
        def __new__(cls, *args):
            value = super().__new__(cls, *args)
            allocated.append(value)
            return value

        def __mul__(self, count):
            value = super().__mul__(count)
            allocated.append(value)
            return value

    overhead = ObservedArray("H").__sizeof__()
    base_overhead = array("H").__sizeof__()
    monkeypatch.setattr(temporal, "array", ObservedArray)
    result = decode(scene("H" * 1000), max_backpointer_bytes=60000)
    assert labels(result) == "H" * 1000
    payload = max(
        a.__sizeof__() - (overhead if isinstance(a, ObservedArray) else base_overhead)
        for a in allocated
    )
    assert payload <= 60000
