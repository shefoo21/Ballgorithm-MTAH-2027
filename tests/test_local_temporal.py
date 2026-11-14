"""Opt-in temporal integration with invented local assets only."""

import csv
import json
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_local_pipeline import fingerprint, make_bundle

from mtah.local.config import LocalError, load_local_config
from mtah.local.runner import run_local


def enable(path, settings=""):
    with path.open("a", encoding="utf-8") as stream:
        stream.write('\n[inference]\nmode="rules_temporal"\n[temporal]\n' + settings)


def test_old_config_and_explicit_rules_preserve_baseline_bytes(tmp_path):
    _, _, path = make_bundle(tmp_path)
    implicit = load_local_config(path)
    assert implicit.mode == "rules"
    first = run_local(implicit, "implicit")
    with path.open("a", encoding="utf-8") as stream:
        stream.write('\n[inference]\nmode="rules"\n')
    second = run_local(load_local_config(path), "explicit")
    assert (first / "submission.csv").read_bytes() == (second / "submission.csv").read_bytes()
    assert json.loads((second / "manifest.json").read_text())["inference"]["mode"] == "rules"


def test_temporal_local_mode_is_explicit_private_repeatable_and_read_only(tmp_path, monkeypatch):
    dataset, _, path = make_bundle(tmp_path, optional=True)
    enable(path)
    before = fingerprint(dataset)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("No network"))
    result = run_local(load_local_config(path), "temporal", verify_repeat=True)
    assert fingerprint(dataset) == before
    assert not (result / ".incomplete").exists()
    report = json.loads((result / "diagnostics.json").read_text())
    assert report["reproducibility"]["status"] == "identical"
    assert report["deterministic"]["coverage"]["rows"] == 48
    assert report["deterministic"]["missing_ball_frames"] == 2
    assert report["deterministic"]["missing_player_slot_observations"] == 0
    for forbidden in (str(dataset), "video_frame", "tracking.txt", "home-id"):
        assert forbidden not in json.dumps(report)
    manifest = json.loads((result / "manifest.json").read_text())["inference"]
    assert manifest["mode"] == "rules_temporal"
    assert manifest["temporal"]["uses_future_observations"] is True
    assert manifest["temporal"]["settings"]["max_segment_frames"] == 200000


@pytest.mark.parametrize(
    "extra",
    [
        '[inference]\nmode="unknown"',
        "[temporal]\nturnover_cost=0.2",
        '[inference]\nmode="rules_temporal"',
        '[inference]\nmode="rules"\n[temporal]',
        '[inference]\nmode="rules_temporal"\n[temporal]\nmade_up=1',
        '[inference]\nmode="rules_temporal"\n[temporal]\nduration_s=100',
    ],
)
def test_invalid_or_ignored_mode_settings_fail(tmp_path, extra):
    _, _, path = make_bundle(tmp_path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n" + extra + "\n")
    with pytest.raises(LocalError):
        load_local_config(path)


def test_temporal_resource_failure_retains_incomplete_without_csv(tmp_path):
    _, output, path = make_bundle(tmp_path)
    enable(path, "max_segment_frames=2\n")
    with pytest.raises(LocalError):
        run_local(load_local_config(path), "bounded")
    assert (output / "bounded" / ".incomplete").exists()
    assert not (output / "bounded" / "submission.csv").exists()


def test_full_length_temporal_file_pipeline_official_format_and_repeat(tmp_path):
    dataset, _, path = make_bundle(tmp_path, count=199319, phase1=True)
    enable(path)
    before = fingerprint(dataset)
    result = run_local(load_local_config(path), "full-temporal", verify_repeat=True)
    diagnostics = json.loads((result / "diagnostics.json").read_text())
    assert diagnostics["reproducibility"]["status"] == "identical"
    assert diagnostics["deterministic"]["coverage"] == {
        "rows": 199319,
        "expected_rows": 199319,
        "complete_ordered": True,
        "graded_rows": 158857,
        "ungraded_rows": 40462,
    }
    with (result / "submission.csv").open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream)
        count = 0
        for i, row in enumerate(rows):
            assert int(row["frame"]) == i
            expected = "H" if 11185 <= i < 90652 else "A" if 110808 <= i < 190198 else "X"
            assert row["label"] == expected
            count += 1
    assert count == 199319
    assert fingerprint(dataset) == before
    repo = Path(__file__).resolve().parents[1]
    checked = subprocess.run(
        [
            sys.executable,
            str(repo / "evaluation/validate_submission.py"),
            str(result / "submission.csv"),
            "--rows",
            "199319",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr


def test_invalid_direct_mode_configuration_cannot_silently_fall_back(tmp_path):
    _, _, path = make_bundle(tmp_path)
    with pytest.raises(LocalError):
        run_local(replace(load_local_config(path), mode="typo"), "bad-mode")
