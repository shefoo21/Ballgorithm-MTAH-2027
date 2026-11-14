"""All observations below are invented; the feature layer has no input-file access."""

import importlib
import math
from dataclasses import asdict

import pytest

from mtah.tracking import Observation, TrackingFrame, parse_atd_line

NAN = math.nan


def test_feature_package_exists():
    assert importlib.util.find_spec("mtah.features") is not None, "Feature API not implemented"


@pytest.fixture
def features():
    try:
        return importlib.import_module("mtah.features")
    except ModuleNotFoundError:
        pytest.fail("Deterministic feature package has not been implemented")


def configuration(f, **kwargs):
    settings = dict(
        pitch_length_m=100.0,
        pitch_width_m=50.0,
        fps=2.0,
        periods=(f.Period(1, 0, 10), f.Period(2, 12, 20)),
        proximity_radii_m=(1.0, 5.0, 10.0),
        nearest_k=2,
    )
    return f.FeatureConfig(**(settings | kwargs))


def sample(f, index=0, players=None, ball=None, quality=None):
    if players is None:
        players = (Observation(0.03, 0.08, 2), Observation(0.0, 0.2, 4))
    if ball is None:
        ball = Observation(0, 0, 1)
    return f.FeatureInput(TrackingFrame(index, tuple(players), ball), quality)


def extractor(f, teams=("H", "A"), **kwargs):
    return f.FeatureExtractor(configuration(f, **kwargs), teams)


def test_geometry_uses_metres_and_preserves_slot_order(features):
    f = features
    item = sample(
        f,
        players=(
            Observation(0.03, 0.08, 2),
            Observation(0, 0.2, 4),
            Observation(0.06, 0.16, 6),
            Observation(NAN, NAN, NAN),
        ),
    )
    result = extractor(f, ("H", "A", "H", "A")).transform(item)
    assert result.video_frame == 0
    assert result.slot_ball_distance_m[:3] == pytest.approx((5, 10, 10))
    assert math.isnan(result.slot_ball_distance_m[3])
    assert result.player_missing == (False, False, False, True)
    assert result.home.nearest_distance_m == 5
    assert result.home.second_distance_m == 10
    assert result.home.mean_k_distance_m == result.home.median_distance_m == 7.5
    assert result.home.within_radius_counts == (0, 1, 2)
    assert result.home.within_radius_fractions == (0, 0.5, 1)
    assert result.away.observed_slots == 1
    assert result.away.missing_fraction == 0.5
    assert math.isnan(result.away.second_distance_m)
    assert result.nearest_margin_m == 5
    assert result.nearest_tie is False
    assert not result.distance_evidence_missing
    assert not item.tracking.players[-1].observed


def test_missing_ball_does_not_turn_unknown_proximity_into_zero(features):
    result = extractor(features).transform(sample(features, ball=Observation(NAN, NAN, NAN)))
    assert result.ball_missing and result.ball_motion_missing
    assert result.ball_outside_pitch is None
    assert all(math.isnan(x) for x in result.slot_ball_distance_m)
    assert all(math.isnan(x) for x in result.home.within_radius_counts)
    assert math.isnan(result.nearest_margin_m)
    assert result.nearest_tie is None
    assert result.distance_evidence_missing
    assert result.home.observed_slots == 1
    assert result.home.speed_median_mps == 2  # Speed evidence does not require a ball.
    assert "label" not in asdict(result)


def test_no_observed_team_distance_is_distinct_from_measured_zero(features):
    f = features
    result = extractor(f).transform(
        sample(
            f,
            players=(
                Observation(NAN, NAN, 8),
                Observation(0.2, 0.2, 1),
            ),
        )
    )
    assert result.home.observed_slots == result.home.speed_count == 0
    assert result.home.missing_fraction == 1
    assert math.isnan(result.home.nearest_distance_m)
    assert all(math.isnan(x) for x in result.home.within_radius_counts)
    assert result.away.within_radius_counts == (0, 0, 0)
    assert result.distance_evidence_missing


def test_unknown_team_is_exposed_without_assignment_or_reordering(features):
    f = features
    result = extractor(f, (None, "A")).transform(sample(f))
    assert result.unknown_team_observed_slots == 1
    assert result.home.slots == 0
    assert math.isnan(result.home.missing_fraction)
    assert math.isnan(result.home.nearest_distance_m)
    assert result.slot_ball_distance_m == (5, 10)


def test_outside_pitch_is_not_clipped_or_a_dead_ball_prediction(features):
    f = features
    result = extractor(f).transform(sample(f, ball=Observation(1.1, -0.1, 2)))
    assert result.ball_x == 1.1 and result.ball_y == -0.1
    assert result.ball_outside_pitch is True
    assert result.slot_ball_distance_m[0] == pytest.approx(math.hypot(107, 9))
    assert "label" not in asdict(result)


def test_speed_summaries_are_robust_and_do_not_fill_negative_or_missing_speeds(features):
    f = features
    result = extractor(f, ("H", "H", "H", "A", "A")).transform(
        sample(
            f,
            players=(
                Observation(0, 0, 2),
                Observation(0, 0, 4),
                Observation(0, 0, 100),
                Observation(0, 0, -3),
                Observation(0, 0, NAN),
            ),
            ball=Observation(0, 0, -2),
        )
    )
    assert result.home.speed_count == 3
    assert result.home.speed_median_mps == 4
    assert result.home.speed_mad_mps == 2
    assert result.home.local_speed_median_mps == 4
    assert result.away.speed_count == 0
    assert math.isnan(result.away.speed_median_mps)
    assert result.player_speed_invalid == (False, False, False, True, False)
    assert result.player_speed_missing == (False, False, False, False, True)
    assert result.ball_reported_speed_mps == -2
    assert result.ball_speed_invalid and not result.ball_speed_missing
    assert result.nearest_tie is True


@pytest.mark.parametrize(
    "setting,value",
    [
        ("pitch_length_m", 0),
        ("pitch_width_m", NAN),
        ("fps", math.inf),
        ("fps", True),
        ("proximity_radii_m", (1, 1)),
        ("proximity_radii_m", (2, 1)),
        ("proximity_radii_m", ()),
        ("proximity_radii_m", (-1,)),
        ("nearest_k", 0),
        ("nearest_k", True),
    ],
)
def test_invalid_feature_settings_fail_before_extraction(features, setting, value):
    with pytest.raises(features.FeatureError):
        configuration(features, **{setting: value})


@pytest.mark.parametrize("teams", [("H", "private-team"), (), (True, "A"), "HA"])
def test_invalid_slot_team_contracts_are_sanitized(features, teams):
    with pytest.raises(features.FeatureError) as error:
        extractor(features, teams)
    assert "private-team" not in str(error.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "slot_count",
        "frame_negative",
        "frame_bool",
        "frame_fraction",
        "one_nan",
        "infinite_position",
        "infinite_speed",
        "text_coordinate",
        "overflow_distance",
    ],
)
def test_malformed_programmatic_input_does_not_bypass_parser_invariants(features, mutation):
    f = features
    frame = sample(f).tracking
    index, players, ball = frame.video_frame, frame.players, frame.ball
    if mutation == "slot_count":
        players = players[:1]
    elif mutation.startswith("frame_"):
        index = {"frame_negative": -1, "frame_bool": True, "frame_fraction": 0.5}[mutation]
    else:
        ball = {
            "one_nan": Observation(NAN, 0, 0),
            "infinite_position": Observation(math.inf, 0, 0),
            "infinite_speed": Observation(0, 0, math.inf),
            "text_coordinate": Observation("private-cell", 0, 0),
            "overflow_distance": Observation(1e308, 0, 0),
        }[mutation]
    with pytest.raises(f.FeatureError) as error:
        extractor(f).transform(f.FeatureInput(TrackingFrame(index, players, ball)))
    assert "private-cell" not in str(error.value)


def test_schema_describes_every_leaf_and_fixed_vector_axis(features):
    f = features
    config = configuration(f)
    schema = f.feature_schema(config, ("H", "A"))
    assert schema["schema_version"] == 1
    assert schema["settings"]["pitch_length_m"] == 100
    assert schema["slot_teams"] == ["H", "A"]
    assert schema["settings"]["proximity_radii_m"] == [1, 5, 10]
    fields = {item["name"]: item for item in schema["fields"]}
    assert fields["slot_ball_distance_m"]["unit"] == "m"
    assert fields["slot_ball_distance_m"]["axis"] == "slots"
    assert fields["home.within_radius_counts"]["axis"] == "proximity_radii_m"
    assert fields["ball_vx_mps"]["missing"] == "NaN"
    assert fields["tags.active_count"]["missing"] == "null"

    def leaves(document, prefix=""):
        for key, value in document.items():
            if isinstance(value, dict):
                yield from leaves(value, prefix + key + ".")
            else:
                yield prefix + key

    result = extractor(f).transform(sample(f))
    assert set(fields) == set(leaves(asdict(result)))


def test_existing_atd_parser_connects_without_changing_its_frame_mapping(features):
    f = features
    frame = parse_atd_line("1:0.03,0.08,2;0,0.2,4:0,0,1", expected_slots=2)
    rows = list(
        f.iter_features([f.FeatureInput(frame)], config=configuration(f), slot_teams=("H", "A"))
    )
    assert len(rows) == 1 and rows[0].video_frame == 0
    assert rows[0].slot_ball_distance_m == (5, 10)


def test_causal_ball_motion_and_collective_distance_rate(features):
    f = features
    engine = extractor(f)
    first = engine.transform(sample(f))
    second = engine.transform(sample(f, 1, ball=Observation(0.03, 0.08, 6)))
    assert first.segment_start and first.ball_motion_missing
    assert math.isnan(first.home.nearest_distance_rate_mps)
    assert not second.segment_start and second.frame_gap_before == 0
    assert second.ball_vx_mps == 6
    assert second.ball_vy_mps == 8
    assert second.ball_speed_from_positions_mps == 10
    assert second.ball_speed_disagreement_mps == 4
    assert second.home.nearest_distance_rate_mps == -10
    assert second.home.coverage_changed is False


def test_missing_ball_streak_and_age_do_not_interpolate_motion(features):
    f = features
    engine = extractor(f)
    first = engine.transform(sample(f, ball=Observation(NAN, NAN, NAN)))
    assert first.ball_missing_streak == 1 and first.ball_observation_age_frames is None
    engine.transform(sample(f, 1))
    missing = engine.transform(sample(f, 2, ball=Observation(NAN, NAN, NAN)))
    assert missing.ball_missing_streak == 1 and missing.ball_observation_age_frames == 1
    missing = engine.transform(sample(f, 3, ball=Observation(NAN, NAN, NAN)))
    assert missing.ball_missing_streak == 2 and missing.ball_observation_age_frames == 2
    recovered = engine.transform(sample(f, 4))
    assert recovered.ball_missing_streak == recovered.ball_observation_age_frames == 0
    assert recovered.ball_motion_missing
    assert math.isnan(recovered.home.nearest_distance_rate_mps)


def test_record_gap_retains_indices_and_resets_temporal_history(features):
    f = features
    records = [sample(f), sample(f, 4, ball=Observation(NAN, NAN, NAN)), sample(f, 5)]
    rows = list(f.iter_features(records, config=configuration(f), slot_teams=("H", "A")))
    assert [item.video_frame for item in rows] == [0, 4, 5]
    assert rows[1].frame_gap_before == 3 and rows[1].segment_start
    assert rows[1].ball_missing_streak == 1
    assert rows[1].ball_observation_age_frames is None
    assert rows[1].home.coverage_changed is None
    assert rows[2].ball_motion_missing


def test_period_boundaries_and_ungraded_frames_never_bridge_motion(features):
    f = features
    engine = extractor(f, periods=(f.Period(1, 1, 3), f.Period(2, 3, 5)))
    rows = [engine.transform(sample(f, i)) for i in range(7)]
    assert [r.period_id for r in rows] == [None, 1, 1, 2, 2, None, None]
    assert [r.segment_start for r in rows] == [True, True, False, True, False, True, False]
    assert [r.ball_motion_missing for r in rows] == [True, True, False, True, False, True, True]
    assert all(math.isnan(rows[i].home.nearest_distance_rate_mps) for i in (0, 1, 3, 5, 6))


def test_visibility_changes_mask_proximity_motion_without_assuming_player_identity(features):
    f = features
    engine = extractor(f, ("H", "H", "A"))
    engine.transform(
        sample(
            f,
            players=(
                Observation(0.01, 0, 2),
                Observation(NAN, NAN, NAN),
                Observation(0.1, 0, 3),
            ),
        )
    )
    result = engine.transform(
        sample(
            f,
            1,
            players=(
                Observation(NAN, NAN, NAN),
                Observation(0.09, 0, 4),
                Observation(0.1, 0, 3),
            ),
        )
    )
    assert result.home.observed_slots == 1
    assert result.home.coverage_changed is True  # Equal counts do not imply identical masks.
    assert math.isnan(result.home.nearest_distance_rate_mps)
    assert result.away.nearest_distance_rate_mps == 0


def test_slot_swaps_do_not_create_person_velocity_or_change_team_statistics(features):
    f = features
    engine = extractor(f, ("H", "H", "A"))
    players = (Observation(0.01, 0, 2), Observation(0.7, 0, 6), Observation(0.3, 0, 4))
    first = engine.transform(sample(f, players=players))
    second = engine.transform(sample(f, 1, players=(players[1], players[0], players[2])))
    assert second.home.nearest_distance_rate_mps == 0
    assert second.home.speed_median_mps == first.home.speed_median_mps == 4
    assert second.slot_ball_distance_m == (70, 1, 30)
    assert "player_velocity" not in asdict(second)


def test_synthetic_turnover_changes_evidence_without_emitting_labels(features):
    f = features
    engine = extractor(f)
    players = (Observation(0.2, 0.5, 2), Observation(0.8, 0.5, 2))
    rows = [
        engine.transform(sample(f, i, players, Observation(x, 0.5, 1)))
        for i, x in enumerate((0.2, 0.5, 0.8))
    ]
    assert rows[0].nearest_margin_m > 0
    assert abs(rows[1].nearest_margin_m) < 1e-12
    assert rows[2].nearest_margin_m < 0
    assert all(not r.distance_evidence_missing for r in rows)
    assert all("label" not in asdict(r) for r in rows)


@pytest.mark.parametrize("indices", [(0, 0), (2, 1)])
def test_duplicate_and_reversed_frames_are_rejected_without_advancing_state(features, indices):
    f = features
    engine = extractor(f)
    engine.transform(sample(f, indices[0]))
    with pytest.raises(f.FeatureError):
        engine.transform(sample(f, indices[1]))
    result = engine.transform(sample(f, indices[0] + 1))
    assert result.frame_gap_before == 0 and not result.segment_start


def test_failed_quality_alignment_does_not_advance_tracking_or_tag_state(features):
    f = features
    tags = (f.TagInterval(1, 2, "SET PIECES", "H"),)
    engine = f.FeatureExtractor(configuration(f), ("H", "A"), tags)
    engine.transform(sample(f))
    with pytest.raises(f.FeatureError):
        engine.transform(sample(f, 5, quality=f.HomographyQuality(6, True, 0.2)))
    result = engine.transform(sample(f, 1))
    assert result.tags.active_count == 1
    assert not result.segment_start


@pytest.mark.parametrize("periods", ["overlap", "unordered", "duplicate", "empty"])
def test_invalid_period_layout_is_rejected(features, periods):
    f = features
    layout = {
        "overlap": (f.Period(1, 0, 4), f.Period(2, 3, 6)),
        "unordered": (f.Period(1, 5, 7), f.Period(2, 0, 2)),
        "duplicate": (f.Period(1, 0, 2), f.Period(1, 3, 4)),
        "empty": (),
    }[periods]
    with pytest.raises(f.FeatureError):
        configuration(f, periods=layout)


@pytest.mark.parametrize("args", [(0, 0, 3), (1, -1, 3), (1, 3, 3), (1, 3, 2), (True, 0, 2)])
def test_malformed_periods_fail_explicitly(features, args):
    with pytest.raises(features.FeatureError):
        features.Period(*args)


def test_quality_absent_unavailable_and_large_valid_error_remain_distinct(features):
    f = features
    engine = extractor(f)
    absent = engine.transform(sample(f)).homography
    unavailable = engine.transform(
        sample(f, 1, quality=f.HomographyQuality(1, False, NAN))
    ).homography
    valid = engine.transform(sample(f, 2, quality=f.HomographyQuality(2, True, 999))).homography
    assert not absent.provided and absent.valid is None and absent.error_missing
    assert unavailable.provided and unavailable.valid is False and unavailable.error_missing
    assert valid.provided and valid.valid is True and valid.reprojection_error == 999


@pytest.mark.parametrize(
    "flag,error", [(True, NAN), (True, -1), (False, -1), (False, math.inf), (2, 0)]
)
def test_invalid_optional_quality_is_not_silently_converted(features, flag, error):
    with pytest.raises(features.FeatureError):
        features.HomographyQuality(0, flag, error)


def test_tags_are_uncertain_counts_with_overlap_unknown_teams_and_half_open_intervals(features):
    f = features
    tags = (
        f.TagInterval(1, 3, " set PIECES ", "H"),
        f.TagInterval(2, 4, "DEFENDING IN MIDDLE THIRD", "A"),
        f.TagInterval(2, 3, "UNKNOWN CODE", None),
    )
    engine = f.FeatureExtractor(configuration(f), ("H", "A"), tags)
    rows = [engine.transform(sample(f, i)) for i in range(5)]
    assert [r.tags.active_count for r in rows] == [0, 1, 3, 1, 0]
    assert rows[2].tags.home_count == rows[2].tags.away_count == 1
    assert rows[2].tags.unknown_team_count == rows[2].tags.set_piece_count == 1
    assert rows[2].tags.team_conflict
    assert rows[3].tags.away_count == 1  # Defensive annotation does not say who possesses.
    assert rows[3].tags.set_piece_count == 0
    assert "label" not in asdict(rows[3].tags)


def test_tags_absent_and_supplied_empty_are_not_equated(features):
    f = features
    absent = extractor(f).transform(sample(f)).tags
    empty = f.FeatureExtractor(configuration(f), ("H", "A"), ()).transform(sample(f)).tags
    assert absent.provided is False and absent.active_count is None and absent.team_conflict is None
    assert empty.provided is True and empty.active_count == 0 and empty.team_conflict is False


def test_tags_round_seconds_using_existing_video_convention(features):
    f = features
    event = f.TagInterval.from_seconds(0.1, 0.2, "SET PIECES", None, fps=25)
    assert (event.start, event.stop) == (2, 5)
    with pytest.raises(f.FeatureError):
        f.TagInterval.from_seconds(0, 0.001, "SET PIECES", None, fps=25)


@pytest.mark.parametrize(
    "args",
    [(-1, 2, "CODE", None), (1, 1, "CODE", None), (0, 2, "", None), (0, 2, "CODE", "private-team")],
)
def test_bad_tag_intervals_or_unmapped_teams_fail_without_echoes(features, args):
    with pytest.raises(features.FeatureError) as error:
        features.TagInterval(*args)
    assert "private-team" not in str(error.value)


def test_tag_sweep_handles_frame_gaps_and_events_spanning_period_boundaries(features):
    f = features
    engine = f.FeatureExtractor(
        configuration(f),
        ("H", "A"),
        (
            f.TagInterval(1, 2, "SET PIECES", "H"),
            f.TagInterval(8, 14, "BUILD UP", "A"),
        ),
    )
    first = engine.transform(sample(f))
    later = engine.transform(sample(f, 12))
    assert first.tags.active_count == 0
    assert later.tags.active_count == 1 and later.tags.away_count == 1
    assert later.segment_start and later.ball_motion_missing


def test_feature_extraction_is_lazy_causal_deterministic_and_chunk_equivalent(features):
    f = features
    consumed = []

    def inputs():
        for i in range(6):
            consumed.append(i)
            yield sample(f, i)

    config = configuration(f)
    stream = f.iter_features(inputs(), config=config, slot_teams=("H", "A"))
    first = next(stream)
    assert consumed == [0]
    all_rows = [first, *stream]
    chunks = []
    engine = f.FeatureExtractor(config, ("H", "A"))
    for indices in ((0, 1), (2,), (3, 4, 5)):
        chunks.extend(engine.transform(sample(f, i)) for i in indices)

    def comparable(value):
        if isinstance(value, dict):
            return {key: comparable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return tuple(comparable(item) for item in value)
        return "NaN" if isinstance(value, float) and math.isnan(value) else value

    assert comparable([asdict(r) for r in all_rows]) == comparable([asdict(r) for r in chunks])


def test_features_need_no_file_boundary_network_or_evaluator(features, monkeypatch):
    import socket

    from mtah import _io

    def forbidden(*args, **kwargs):
        pytest.fail("Pure feature extraction attempted external access")

    for name in ("open_text", "open_binary", "stat_file"):
        monkeypatch.setattr(_io, name, forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = extractor(features).transform(sample(features))
    assert result.home.nearest_distance_m == 5
