"""Compatibility smoke test: unchanged official scorer, entirely invented CSVs."""

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_official_evaluator_scores_only_explicit_synthetic_inputs(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    results = tmp_path / "toy_results"
    results.mkdir()
    # Long enough spans exercise possession/transition metrics and all three scored classes.
    labels = ["X"] * 5 + ["H"] * 40 + ["D"] * 30 + ["A"] * 40 + ["H"] * 40 + ["X"] * 5
    csv_text = "frame,label\n" + "".join(f"{i},{label}\n" for i, label in enumerate(labels))
    gt = tmp_path / "invented_gt.csv"
    gt.write_text(csv_text, encoding="utf-8")
    (results / "perfect_toy.csv").write_text(csv_text, encoding="utf-8")
    out = tmp_path / "toy_reports"
    result = subprocess.run(
        [
            sys.executable,
            str(repo / "evaluation" / "run_evaluation.py"),
            "--gt",
            str(gt),
            "--results",
            str(results),
            "--out",
            str(out),
            "--bootstrap",
            "0",
            "--no-detail",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with (out / "scoreboard.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert float(rows[0]["spell_f1_mean"]) == 1.0
    assert float(rows[0]["macro_f1"]) == 1.0
    report = json.loads((out / "reports" / "perfect_toy.json").read_text())
    assert report["ground_truth"] == "invented_gt.csv"
