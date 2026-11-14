"""Use unchanged official metrics only on labels invented in this test module."""

import importlib.util
from pathlib import Path

import pytest
from test_temporal import decode, labels, scene


def metrics():
    path = Path(__file__).resolve().parents[1] / "evaluation/possession_metrics.py"
    spec = importlib.util.spec_from_file_location("invented_metrics_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_temporal_predictions_score_against_invented_ground_truth_only():
    pm = metrics()
    authored = "H" * 60 + "A" * 4 + "H" * 60 + "D" * 40 + "A" * 60
    gt = pm.label_codes(list(authored))
    prediction = pm.label_codes(list(labels(decode(scene(authored)))))
    result = pm.evaluate(gt, prediction, bootstrap_n=0)
    assert result["macro_f1"] == 1.0
    assert result["spell_f1_mean"] == 1.0


def test_invented_twenty_frame_shift_exposes_iou_threshold_behavior():
    pm = metrics()
    # H [20,120) vs H [40,140): 80 intersection / 120 union = 2/3.
    gt = pm.label_codes(list("D" * 20 + "H" * 100 + "D" * 40))
    pred = pm.label_codes(list("D" * 40 + "H" * 100 + "D" * 20))
    report = pm.spell_scores(gt, pred, pm.valid_runs(gt))
    assert report["per_iou"][0.6]["f1"] == 1.0
    assert report["per_iou"][0.7]["f1"] == 0.0
    assert report["mean_f1"] == pytest.approx(0.8)


def test_official_x_fill_is_separate_from_model_and_cannot_cross_gt_holes():
    pm = metrics()
    gt = pm.label_codes(list("HHHHXXAAAA"))
    pred = pm.label_codes(list("HXXXXXXXXA"))
    filled = pm.fill_abstentions(pred, pm.valid_runs(gt))
    assert list(filled) == list(gt)
    assert list(pred) == list(pm.label_codes(list("HXXXXXXXXA")))
    assert pm.evaluate(gt, pred, bootstrap_n=0)["macro_f1"] < 1
