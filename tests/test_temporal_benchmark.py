"""The benchmark has no input option and generates every evidence record itself."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode", ["rules", "rules_temporal"])
@pytest.mark.parametrize("scenario", ["mixed", "continuous"])
def test_benchmark_runs_in_fresh_process_on_invented_evidence(tmp_path, mode, scenario):
    script = Path(__file__).resolve().parents[1] / "scripts/benchmark_temporal.py"
    target = tmp_path / "invented.csv"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--mode",
            mode,
            "--frames",
            "300",
            "--out",
            str(target),
            "--scenario",
            scenario,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["kind"] == "invented_evidence_benchmark_not_accuracy"
    assert report["scenario"] == scenario
    assert report["rows"] == 300 and sum(report["label_counts"].values()) == 300
    # A short process may consume less than one OS CPU-accounting tick; zero is valid.
    assert report["wall_seconds"] > 0 and report["cpu_seconds"] >= 0
    assert report["peak_memory"]["bytes"] > 0
    assert len(target.read_text().splitlines()) == 301
