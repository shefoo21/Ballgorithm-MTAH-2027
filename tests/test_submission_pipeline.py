"""Invented observations through the unchanged official submission validator."""

import csv
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from mtah.inference import InferenceError
from mtah.inference.submission import write_submission
from mtah.synthetic import synthetic_predictions


def test_complete_official_length_pipeline(tmp_path):
    target = tmp_path / "invented-199319.csv"
    assert write_submission(target, synthetic_predictions(199319), expected_rows=199319) == 199319
    with target.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["frame", "label"]
        seen = set()
        count = 0
        for count, row in enumerate(reader, 1):
            assert row["frame"] == str(count - 1)
            seen.add(row["label"])
    assert count == 199319 and seen == {"H", "A", "D", "X"}
    validator = Path(__file__).resolve().parents[1] / "evaluation" / "validate_submission.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(target), "--rows", "199319"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, "Official validator rejected invented submission"
    assert "199319 rows, frame 0..199318" in result.stdout


def test_repeatable_bytes_and_refuses_overwrite(tmp_path):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    write_submission(first, synthetic_predictions(200), expected_rows=200)
    write_submission(second, synthetic_predictions(200), expected_rows=200)
    expected = first.read_bytes()
    assert expected == second.read_bytes()
    with pytest.raises(InferenceError):
        write_submission(first, synthetic_predictions(200), expected_rows=200)
    assert first.read_bytes() == expected
    assert set(tmp_path.iterdir()) == {first, second}


@pytest.mark.parametrize("kind", ["short", "long", "gap", "label", "type", "exception"])
def test_failure_never_publishes_partial_submission(tmp_path, kind):
    predictions = list(synthetic_predictions(20))
    if kind == "short":
        predictions.pop()
    elif kind == "long":
        predictions.append(replace(predictions[-1], video_frame=20))
    elif kind == "gap":
        predictions[10] = replace(predictions[10], video_frame=11)
    elif kind == "label":
        predictions[10] = replace(predictions[10], label="bad")
    elif kind == "type":
        predictions[10] = None
    else:

        def broken():
            yield predictions[0]
            raise InferenceError("Synthetic producer failed")

        predictions = broken()
    with pytest.raises(InferenceError):
        write_submission(tmp_path / "never.csv", predictions, expected_rows=20)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_invalid_output_counts_fail_before_creation(tmp_path, count):
    with pytest.raises(InferenceError):
        write_submission(tmp_path / "never.csv", (), expected_rows=count)
    assert not list(tmp_path.iterdir())


def test_synthetic_example_has_no_input_option_and_runs_as_installed_module(tmp_path):
    target = tmp_path / "demo.csv"
    result = subprocess.run(
        [sys.executable, "-m", "mtah.synthetic", "--out", str(target), "--frames", "200"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "invented" in result.stdout.lower()
    assert target.exists()


def test_destination_created_during_generation_is_not_overwritten(tmp_path):
    target = tmp_path / "racing.csv"

    def racing_stream():
        yield from synthetic_predictions(20)
        target.write_text("existing content", encoding="utf-8")

    with pytest.raises(InferenceError):
        write_submission(target, racing_stream(), expected_rows=20)
    assert target.read_text(encoding="utf-8") == "existing content"
    assert list(tmp_path.iterdir()) == [target]


def test_publication_failure_cleans_temporary_output(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("Invented unsupported filesystem")

    monkeypatch.setattr(os, "rename" if os.name == "nt" else "link", fail)
    with pytest.raises(InferenceError):
        write_submission(tmp_path / "never.csv", synthetic_predictions(20), expected_rows=20)
    assert not list(tmp_path.iterdir())
