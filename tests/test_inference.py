"""Invented football behavior; no match inputs or fitted thresholds."""

import json
import math
from dataclasses import replace

import pytest

from mtah.features import (
    FeatureConfig,
    FeatureExtractor,
    FeatureInput,
    HomographyQuality,
    Period,
    TagInterval,
)
from mtah.inference import (
    EvidenceModel,
    FeatureContract,
    InferenceError,
    PossessionEngine,
    RuleConfig,
    RuleDecoder,
    iter_predictions,
    rule_schema,
)
from mtah.tracking import Observation, TrackingFrame

NAN = math.nan
MISSING = Observation(NAN, NAN, NAN)
CONFIG = FeatureConfig(100.0, 50.0, 10.0, (Period(1, 0, 1000),))
TEAMS = ("H", "A")


def rows(xs, *, config=CONFIG, tags=None, players=None, speed=0.0, start=0, quality=None):
    extractor = FeatureExtractor(config, TEAMS, tags)
    for frame, x in enumerate(xs, start):
        ball = MISSING if x is None else Observation(x, 0.5, speed)
        people = players or (Observation(0.2, 0.5, 0.0), Observation(0.8, 0.5, 0.0))
        q = None if quality is None else HomographyQuality(frame, *quality)
        yield extractor.transform(FeatureInput(TrackingFrame(frame, people, ball), q))


def infer(xs, *, rules=None, config=CONFIG, **kwargs):
    return list(
        iter_predictions(
            rows(xs, config=config, **kwargs), contract=FeatureContract(config, TEAMS), rules=rules
        )
    )


def labels(predictions):
    return "".join(p.label for p in predictions)


def test_long_control_requires_confirmation_then_stays_stable():
    result = infer([0.2] * 100)
    assert labels(result) == "X" + "H" * 99
    assert result[-1].reason_codes[-1] == "control_supported"
    assert not result[-1].held


def test_short_opposing_touch_preserves_owner_but_persistent_control_turns_over():
    short = infer([0.2] * 10 + [0.8] * 3 + [0.2] * 10)
    assert set(labels(short)[1:]) == {"H"}
    assert any("turnover_pending" in p.reason_codes for p in short)
    sustained = infer([0.2] * 10 + [0.8] * 20)
    assert sustained[10].label == "H"  # Position jump is inconsistent motion.
    assert sustained[-1].label == "A"
    assert sum("turnover_confirmed" in p.reason_codes for p in sustained) == 1


def test_missing_ball_holds_briefly_then_expires_never_creates_dead_ball():
    result = infer([0.2] * 10 + [None] * 30)
    assert result[10].label == "H" and result[10].held
    assert result[15].confidence < result[10].confidence
    assert result[-1].label == "X"
    assert "D" not in labels(result)
    assert result[-1].evidence.ball_missing
    assert labels(infer([None] * 10)) == "X" * 10


def test_loose_ball_does_not_claim_opponent_and_cannot_refresh_held_owner():
    result = infer([0.2] * 10 + [0.5] * 60)
    assert result[10].label == "H"
    assert result[-1].label == "X"
    assert set(labels(result)) == {"H", "X"}


def test_visible_stoppage_then_missing_ball_can_retain_but_not_initiate_dead_state():
    result = infer([1.1] * 15 + [None] * 40)
    assert result[0].label == "X"
    assert result[14].label == "D"
    assert result[15].label == "D" and result[15].held
    assert result[-1].label == "X"
    assert labels(infer([None] * 20, tags=(TagInterval(0, 20, "Set pieces"),))) == "X" * 20


def test_set_piece_is_uncertain_and_active_teams_or_moving_ball_block_dead_entry():
    tag = (TagInterval(0, 30, "Set pieces", "A"),)
    assert infer([0.5] * 20, tags=tag)[-1].label == "D"
    moving = (Observation(0.2, 0.5, 3), Observation(0.8, 0.5, 3))
    assert "D" not in labels(infer([1.1] * 20, players=moving))
    assert "D" not in labels(infer([0.5] * 20, tags=tag, speed=4))


def test_restart_needs_motion_and_confirmed_control_even_if_tag_persists():
    tag = (TagInterval(0, 80, "Set pieces"),)
    stationary = infer([1.1] * 15 + [0.2] * 15)
    assert "H" not in labels(stationary)[15:]
    extractor = FeatureExtractor(CONFIG, TEAMS, tag)
    engine = PossessionEngine(FeatureContract(CONFIG, TEAMS))
    result = []
    for i in range(30):
        x, speed = (1.1, 0) if i < 15 else (0.2 + (i - 15) * 0.001, 1)
        feature = extractor.transform(
            FeatureInput(
                TrackingFrame(
                    i,
                    (Observation(0.2, 0.5, 0), Observation(0.8, 0.5, 0)),
                    Observation(x, 0.5, speed),
                )
            )
        )
        result.append(engine.step(feature))
    assert result[14].label == "D"
    assert result[-1].label == "H"
    assert any("restart_confirmed" in p.reason_codes for p in result)


def test_defensive_and_unknown_tags_do_not_assign_possession():
    tag = (TagInterval(0, 30, "Defensive phase", "A"), TagInterval(0, 30, "Unknown event", None))
    result = infer([0.2] * 20, tags=tag)
    assert result[-1].label == "H"
    assert result[-1].evidence.tags_unknown
    assert result[-1].evidence.tags_provided


def test_conflicting_tags_reduce_confidence_and_remain_visible():
    tag = (TagInterval(0, 30, "Phase", "A"), TagInterval(0, 30, "Phase", "H"))
    clean = infer([0.2] * 20)[-1]
    conflict = infer([0.2] * 20, tags=tag)[-1]
    assert conflict.evidence.source_confidence < clean.evidence.source_confidence
    assert conflict.evidence.tag_conflict


@pytest.mark.parametrize("players", [(MISSING, MISSING), (Observation(0.2, 0.5, 0), MISSING)])
def test_missing_opponent_is_not_evidence_of_dominance(players):
    assert labels(infer([0.2] * 30, players=players)) == "X" * 30


def test_invalid_calibration_and_inconsistent_motion_reduce_source_confidence():
    clean = infer([0.2] * 20, quality=(True, 0))[-1]
    bad = infer([0.2] * 20, quality=(False, NAN))[-1]
    wrong_speed = infer([0.2] * 20, speed=40)[-1]
    assert bad.label == wrong_speed.label == "X"
    assert bad.evidence.source_confidence < clean.evidence.source_confidence
    assert wrong_speed.evidence.source_confidence < clean.evidence.source_confidence


def test_period_and_frame_gaps_reset_ownership_and_candidate_counts():
    config = replace(CONFIG, periods=(Period(1, 0, 10), Period(2, 15, 40)))
    result = infer([0.2] * 10 + [None] * 10, config=config)
    assert labels(result[10:]) == "X" * 10
    assert result[15].period_id == 2
    features = list(rows([0.2] * 20))
    engine = PossessionEngine(FeatureContract(CONFIG, TEAMS))
    for row in features[:10]:
        engine.step(row)
    after_gap = engine.step(features[15])
    assert after_gap.label == "X"
    assert after_gap.video_frame == 15


def test_configurable_confirmation_delays_and_deterministic_streaming():
    rules = RuleConfig(acquire_confirm_s=0.5)
    features = list(rows([0.2] * 30))
    contract = FeatureContract(CONFIG, TEAMS)
    batch = list(iter_predictions(features, contract=contract, rules=rules))
    engine = PossessionEngine(contract, rules)
    chunked = [engine.step(f) for f in features[:13]] + [engine.step(f) for f in features[13:]]
    assert batch == chunked
    assert labels(batch[:6]) == "XXXXHH"
    assert all(0 <= p.confidence <= 1 for p in batch)
    assert json.loads(json.dumps(engine.manifest(), allow_nan=False))["schema_version"] == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(control_distance_m=0),
        dict(turnover_confirm_s=-1),
        dict(tag_conflict_factor=1.1),
        dict(dead_min_confidence=NAN),
        dict(acquire_confirm_s=True),
        dict(stop_ball_speed_mps=math.inf),
    ],
)
def test_invalid_configs_rejected(kwargs):
    with pytest.raises(InferenceError):
        RuleConfig(**kwargs)


def test_schema_describes_every_threshold_and_config_roundtrips():
    schema = rule_schema()
    config = RuleConfig()
    assert set(schema["properties"]) == set(config.to_dict())
    assert all(p["description"] and p["unit"] for p in schema["properties"].values())
    assert RuleConfig.from_dict(config.to_dict()) == config
    with pytest.raises(InferenceError):
        RuleConfig.from_dict({"typo": 1})
    with pytest.raises(InferenceError):
        FeatureContract(replace(CONFIG, proximity_radii_m=(1.0,)), TEAMS).bind(config)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda f: replace(f, ball_missing=False, ball_x=NAN),
        lambda f: replace(f, player_missing=(False,)),
        lambda f: replace(f, home=replace(f.home, within_radius_counts=(1.0,))),
        lambda f: replace(f, ball_reported_speed_mps=math.inf),
        lambda f: replace(f, period_id=17),
        lambda f: replace(f, home=replace(f.home, observed_slots=7)),
        lambda f: replace(f, segment_start=1),
    ],
)
def test_bad_features_fail_without_advancing_decoder(corrupt):
    features = list(rows([0.2] * 3))
    engine = PossessionEngine(FeatureContract(CONFIG, TEAMS))
    engine.step(features[0])
    with pytest.raises(InferenceError):
        engine.step(corrupt(features[1]))
    assert engine.step(features[1]).label == "H"
    with pytest.raises(InferenceError):
        engine.step(features[1])
    assert engine.step(features[2]).label == "H"


def test_evidence_and_decoder_independently_usable_and_validate_confidence():
    contract = FeatureContract(CONFIG, TEAMS)
    evidence = EvidenceModel(contract).score(next(rows([0.2])))
    decoder = RuleDecoder(fps=CONFIG.fps)
    with pytest.raises(InferenceError):
        decoder.step(replace(evidence, source_confidence=NAN))
    assert decoder.step(evidence).label == "X"


def test_nearest_player_without_margin_is_not_control():
    people = (Observation(0.2, 0.5, 0), Observation(0.208, 0.5, 0))
    assert labels(infer([0.2] * 30, players=people)) == "X" * 30
    assert labels(infer([0.204] * 30, players=people)) == "X" * 30


def test_unknown_nearby_slot_prevents_claiming_known_team_control():
    teams = ("H", None, "A")
    extractor = FeatureExtractor(CONFIG, teams)
    model = EvidenceModel(FeatureContract(CONFIG, teams))
    features = extractor.transform(
        FeatureInput(
            TrackingFrame(
                0,
                (Observation(0.2, 0.5, 0), Observation(0.2, 0.5, 0), Observation(0.8, 0.5, 0)),
                Observation(0.2, 0.5, 0),
            )
        )
    )
    evidence = model.score(features)
    assert evidence.control_candidate is None
    assert "unknown_team_near_ball" in evidence.reason_codes


def test_track_slot_swap_does_not_create_identity_motion():
    teams = ("H", "H", "A")
    extractor = FeatureExtractor(CONFIG, teams)
    engine = PossessionEngine(FeatureContract(CONFIG, teams))
    a, b, opponent = Observation(0.2, 0.5, 0), Observation(0.21, 0.5, 0), Observation(0.8, 0.5, 0)
    results = []
    for i in range(20):
        players = (a, b, opponent) if i % 2 else (b, a, opponent)
        results.append(
            engine.step(
                extractor.transform(
                    FeatureInput(TrackingFrame(i, players, Observation(0.2, 0.5, 0)))
                )
            )
        )
    assert labels(results) == "X" + "H" * 19


def test_inference_does_not_mutate_features_or_read_future_frames():
    features = list(rows([0.2] * 10 + [0.8] * 20))
    original = [(f.video_frame, f.player_missing, f.slot_ball_distance_m, f.home) for f in features]
    contract = FeatureContract(CONFIG, TEAMS)
    prefix = list(iter_predictions(features[:10], contract=contract))
    all_frames = list(iter_predictions(features, contract=contract))
    assert prefix == all_frames[:10]
    assert original == [
        (f.video_frame, f.player_missing, f.slot_ball_distance_m, f.home) for f in features
    ]


def test_alternating_opposing_candidates_do_not_accumulate_across_interruptions():
    features = list(rows([0.2] * 50))
    model = EvidenceModel(FeatureContract(CONFIG, TEAMS))
    decoder = RuleDecoder(fps=10)
    result = []
    for i, f in enumerate(features):
        e = model.score(f)
        if i >= 10 and i % 3 != 0:
            e = replace(e, control_candidate="A", away_control=0.9)
        result.append(decoder.step(e))
    assert "A" not in labels(result)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda f: replace(f, ball_speed_from_positions_mps=-1, ball_motion_missing=False),
        lambda f: replace(f, ball_speed_disagreement_mps=-1),
        lambda f: replace(f, ball_missing_streak=-1),
        lambda f: replace(f, ball_observation_age_frames=-1),
        lambda f: replace(f, home=replace(f.home, missing_fraction=0.5)),
        lambda f: replace(f, home=replace(f.home, within_radius_fractions=(1.5, 1.0, 1.0))),
        lambda f: replace(f, homography=replace(f.homography, provided=True, valid=True)),
        lambda f: replace(f, tags=replace(f.tags, provided=True)),
    ],
)
def test_semantically_corrupted_features_rejected(corrupt):
    f = next(rows([0.2]))
    with pytest.raises(InferenceError):
        EvidenceModel(FeatureContract(CONFIG, TEAMS)).score(corrupt(f))


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda e: replace(e, dead_candidate=True, ball_missing=True, control_candidate=None),
        lambda e: replace(e, control_candidate="A", ball_missing=True),
        lambda e: replace(e, video_frame=True),
        lambda e: replace(e, away_control=1.01),
        lambda e: replace(e, control_candidate="D"),
        lambda e: replace(e, source_confidence=math.inf),
    ],
)
def test_decoder_rejects_invalid_evidence_without_state_advance(corrupt):
    e = EvidenceModel(FeatureContract(CONFIG, TEAMS)).score(next(rows([0.2])))
    decoder = RuleDecoder(fps=10)
    with pytest.raises(InferenceError):
        decoder.step(corrupt(e))
    assert decoder.step(e).video_frame == 0


@pytest.mark.parametrize("fps", [True, 0, -2, math.nan, math.inf, "25"])
def test_decoder_rejects_invalid_frame_rate(fps):
    with pytest.raises(InferenceError):
        RuleDecoder(fps=fps)


@pytest.mark.parametrize("disagreement", [math.nan, 0.0])
def test_corrupt_speed_disagreement_cannot_bypass_reliability_or_advance_state(disagreement):
    features = list(rows([0.2] * 3, speed=9.0))
    contract = FeatureContract(CONFIG, TEAMS)
    normal = EvidenceModel(contract).score(features[1])
    assert normal.control_candidate is None
    assert "unreliable_motion" in normal.reason_codes
    engine = PossessionEngine(contract)
    engine.step(features[0])
    with pytest.raises(InferenceError):
        engine.step(replace(features[1], ball_speed_disagreement_mps=disagreement))
    result = engine.step(features[1])
    assert result.label == "X" and result.evidence == normal


@pytest.mark.parametrize("score_name", ["home_control", "away_control", "dead_confidence"])
def test_decision_scores_cannot_exceed_source_reliability(score_name):
    features = list(rows([0.2] * 2))
    model = EvidenceModel(FeatureContract(CONFIG, TEAMS))
    first = model.score(features[0])
    inconsistent = replace(
        first, source_confidence=0.3, home_control=0.2, away_control=0.1, dead_confidence=0.0
    )
    inconsistent = replace(inconsistent, **{score_name: 1.0})
    decoder = RuleDecoder(fps=10)
    with pytest.raises(InferenceError):
        decoder.step(inconsistent)
    assert decoder.step(first).label == "X"
    confirmed = decoder.step(model.score(features[1]))
    assert confirmed.label == "H"
    assert confirmed.confidence <= confirmed.evidence.source_confidence
