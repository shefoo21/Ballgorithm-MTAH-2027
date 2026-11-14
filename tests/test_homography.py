"""Invented homographies only; never resolve competition paths or read local reports."""

import json

import numpy as np
import pytest

from mtah.cli import main
from mtah.config import load_config
from mtah.validation import validate_bundle


@pytest.fixture
def broadcast_homography(synthetic_bundle):
    root, config = synthetic_bundle
    homography = root / "broadcast.csv"
    homography.write_text((root / "homography.csv").read_text(), encoding="utf-8")
    with config.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n[sources.broadcast]\nframe_count = 3\ntrack_slots = 2\nfps = 25\n"
            '[sources.broadcast.assets]\nvideo = "invented/toy.mp4"\n'
            'atd_meta = "invented/tracking.xml"\natd_raw = "invented/tracking.txt"\n'
            'homography = "invented/broadcast.csv"\n'
        )
    return root, config, homography


def replace_middle_row(path, row):
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[2] = row
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def unavailable_row(matrix=None, error="", frame="1", valid="0"):
    return ",".join([frame, *(matrix if matrix is not None else [""] * 9), error, valid])


def homography_check(config, source="broadcast"):
    report = validate_bundle(load_config(config))
    check = next(item for item in report.checks if item.asset == f"{source}.homography")
    return report, check.to_dict()


def test_explicit_nan_unavailable_row_already_passes(broadcast_homography):
    _, config, _ = broadcast_homography
    report, check = homography_check(config)
    assert report.ok
    assert check["status"] == "passed"
    assert check["issues"] == {}


@pytest.mark.parametrize("source", ["broadcast", "tactical"])
@pytest.mark.parametrize(
    "matrix,error",
    [([""] * 9, ""), (["NaN"] * 9, ""), ([""] * 9, "NaN"), (["", "NaN", ""] * 3, "0.5")],
)
def test_unavailable_csv_missing_values_are_not_corruption(
    broadcast_homography, source, matrix, error
):
    root, config, broadcast = broadcast_homography
    path = broadcast if source == "broadcast" else root / "homography.csv"
    replace_middle_row(path, unavailable_row(matrix, error))
    before = path.read_bytes()
    report, check = homography_check(config, source)
    assert check["issues"] == {}
    assert check["status"] == "passed"
    assert report.ok
    assert path.read_bytes() == before


def test_official_loader_interprets_empty_csv_cells_as_nan(broadcast_homography, monkeypatch):
    # Only substitute path resolution; run the public CSV loader on the actual toy file.
    from starter import load_homography

    _, _, path = broadcast_homography
    replace_middle_row(path, unavailable_row())
    monkeypatch.setattr(load_homography, "require", lambda *args: [str(path)])
    matrices, errors, valid = load_homography.load(source="broadcast")
    assert valid.tolist() == [True, False, True]
    assert np.isnan(matrices[1]).all()
    assert np.isnan(errors[1])


@pytest.mark.parametrize("missing", ["", "NaN"])
def test_unavailable_rows_have_informational_count_not_issues(broadcast_homography, missing):
    _, config, path = broadcast_homography
    replace_middle_row(path, unavailable_row([missing] * 9, missing))
    report, check = homography_check(config)
    assert check["unavailable_rows"] == 1
    assert check["rows"] == 3
    assert check["issues"] == {}
    assert report.ok


def test_all_unavailable_rows_are_allowed_without_a_percentage_threshold(broadcast_homography):
    _, config, path = broadcast_homography
    header = path.read_text().splitlines()[0]
    path.write_text(
        header + "\n" + "\n".join(unavailable_row(frame=str(i)) for i in range(3)) + "\n",
        encoding="utf-8",
    )
    report, check = homography_check(config)
    assert report.ok
    assert check["unavailable_rows"] == 3


@pytest.mark.parametrize(
    "row,issue",
    [
        (unavailable_row(frame="0"), "frame_sequence"),
        (unavailable_row(frame="2"), "frame_sequence"),
        (unavailable_row(frame="-1"), "invalid_record"),
        (unavailable_row(frame="1.5"), "invalid_record"),
        (unavailable_row(valid="2"), "invalid_record"),
        (unavailable_row(valid="true"), "invalid_record"),
        (unavailable_row(valid="0.0"), "invalid_record"),
        (unavailable_row(valid=""), "invalid_record"),
        (unavailable_row(["1"] + [""] * 8), "invalid_record"),
        (unavailable_row(["inf"] + ["NaN"] * 8), "invalid_record"),
        (unavailable_row(["private-value"] + [""] * 8), "invalid_record"),
        (unavailable_row(error="private-value"), "invalid_record"),
        (unavailable_row(error="inf"), "invalid_record"),
        (unavailable_row(error="-1"), "invalid_record"),
        (unavailable_row() + ",extra", "invalid_record"),
        (",".join(["1"] + [""] * 9 + ["0"]), "invalid_record"),
    ],
)
def test_corrupt_unavailable_rows_still_fail_and_are_not_counted(broadcast_homography, row, issue):
    _, config, path = broadcast_homography
    replace_middle_row(path, row)
    report, check = homography_check(config)
    assert not report.ok
    assert check["status"] == "failed"
    assert issue in check["issues"]
    assert check["unavailable_rows"] == 0
    assert "private-value" not in json.dumps(report.to_dict())


@pytest.mark.parametrize(
    "matrix,error,issue",
    [
        ([""] * 9, "0", "invalid_record"),
        (["NaN"] * 9, "0", "invalid_record"),
        (["inf", "0", "0", "0", "1", "0", "0", "0", "1"], "0", "invalid_record"),
        (["1", "0", "0", "0", "1", "0", "0", "0", "0"], "0", "singular_matrix"),
        (["1", "0", "0", "0", "1", "0", "0", "0", "1"], "", "invalid_record"),
        (["1", "0", "0", "0", "1", "0", "0", "0", "1"], "NaN", "invalid_record"),
    ],
)
def test_valid_one_requires_finite_usable_matrix_and_error(
    broadcast_homography, matrix, error, issue
):
    _, config, path = broadcast_homography
    replace_middle_row(path, unavailable_row(matrix, error, valid="1"))
    report, check = homography_check(config)
    assert not report.ok
    assert check["issues"] == {issue: 1}
    assert check["unavailable_rows"] == 0


def test_unavailable_rows_do_not_hide_a_corrupt_valid_matrix(broadcast_homography):
    _, config, path = broadcast_homography
    replace_middle_row(path, unavailable_row())
    lines = path.read_text().splitlines()
    lines[-1] = "2,inf,0,0,0,1,0,0,0,1,0,1"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report, check = homography_check(config)
    assert not report.ok
    assert check["issues"] == {"invalid_record": 1}
    assert check["unavailable_rows"] == 1


@pytest.mark.parametrize(
    "mutation,issue", [("header", "header"), ("truncate", "row_count"), ("quote", "invalid_csv")]
)
def test_unavailable_rows_do_not_bypass_file_structure(broadcast_homography, mutation, issue):
    _, config, path = broadcast_homography
    replace_middle_row(path, unavailable_row())
    lines = path.read_text().splitlines()
    if mutation == "header":
        lines[0] = lines[0].replace("h00", "wrong")
    elif mutation == "truncate":
        lines.pop()
    else:
        lines[-1] = '2,"unterminated'
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report, check = homography_check(config)
    assert not report.ok
    assert issue in check["issues"]


@pytest.mark.parametrize("corrupt,exit_code", [(False, 0), (True, 1)])
def test_cli_reports_unavailability_separately_and_preserves_failure_exit(
    broadcast_homography, capsys, corrupt, exit_code
):
    _, config, path = broadcast_homography
    replace_middle_row(path, unavailable_row())
    if corrupt:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("private-value\n")
    assert main(["--local-only", "--config", str(config)]) == exit_code
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    check = next(item for item in report["checks"] if item["asset"] == "broadcast.homography")
    assert check["unavailable_rows"] == 1
    assert report["ok"] is (not corrupt)
    assert "private-value" not in captured.out + captured.err
