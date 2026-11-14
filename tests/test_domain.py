import importlib
import math

import pytest


def module(name):
    # A missing implementation is a failed behavior contract, not a collection error.
    try:
        return importlib.import_module("mtah." + name)
    except ModuleNotFoundError:
        pytest.fail(f"Foundation module {name} has not been implemented")


@pytest.mark.parametrize("atd,video", [(1, 0), (2, 1), (199319, 199318)])
def test_frame_alignment_does_not_apply_hidden_counter_offsets(atd, video):
    m = module("alignment")
    assert m.atd_to_video_frame(atd) == video
    assert m.video_to_atd_frame(video) == atd


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "1"])
def test_atd_frame_rejects_nonpositive_and_noninteger_indices(bad):
    with pytest.raises(ValueError):
        module("alignment").atd_to_video_frame(bad)


def test_tag_time_uses_video_origin_and_nearest_frame():
    m = module("alignment")
    assert m.seconds_to_video_frame(0.04, 25) == 1
    assert m.seconds_to_video_frame(1.0, 25) == 25
    assert m.seconds_to_video_frame(0.1, 25) == 2  # same ties-to-even as public loader
    for seconds, fps in [(-1, 25), (math.nan, 25), (1, 0), (1, math.inf)]:
        with pytest.raises(ValueError):
            m.seconds_to_video_frame(seconds, fps)


def test_missing_ball_is_preserved_without_inventing_a_dead_ball_label():
    frame = module("tracking").parse_atd_line(
        "2:NaN,NaN,NaN;0.6,0.7,1:NaN,NaN,NaN", expected_slots=2
    )
    assert frame.video_frame == 1
    assert not frame.ball.observed
    assert math.isnan(frame.ball.x)
    assert not frame.players[0].observed
    assert frame.players[1].observed


def test_outside_pitch_position_is_not_clipped_or_rejected():
    frame = module("tracking").parse_atd_line("1:0,0,0:1.1,-0.1,2", expected_slots=1)
    assert (frame.ball.x, frame.ball.y) == (1.1, -0.1)


@pytest.mark.parametrize(
    "line",
    [
        "0:0,0,0:0,0,0",
        "1:0,0,0",
        "1:0,0,0:inf,0,1",
        "1:0,0,0:NaN,0,1",
        "1:0,0,0;0,0,0:0,0,0",
        "1:secret,0,0:0,0,0",
    ],
)
def test_malformed_tracking_has_sanitized_errors(line):
    with pytest.raises(ValueError) as error:
        module("tracking").parse_atd_line(line, expected_slots=1)
    assert "secret" not in str(error.value)
    assert line not in str(error.value)


def test_runs_preserve_dead_ball_and_abstention_boundaries():
    m = module("labels")
    spans = m.label_runs(["H", "H", "D", "D", "H", "A", "X", "A"])
    assert [(s.start, s.stop, s.label) for s in spans] == [
        (0, 2, "H"),
        (2, 4, "D"),
        (4, 5, "H"),
        (5, 6, "A"),
        (6, 7, "X"),
        (7, 8, "A"),
    ]
    assert m.label_runs([]) == ()


def test_runs_do_not_cross_explicit_half_boundaries():
    spans = module("labels").label_runs(["H", "H", "H", "H"], breaks=(2,))
    assert [(s.start, s.stop) for s in spans] == [(0, 2), (2, 4)]


def test_invalid_labels_are_rejected_without_echoing_contents():
    with pytest.raises(ValueError) as error:
        module("labels").label_runs(["H", "private-value"])
    assert "private-value" not in str(error.value)
