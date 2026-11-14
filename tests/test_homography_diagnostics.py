"""Invented rows only: identify exact rejection branches without leaking input values."""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from mtah import _io, cli
from mtah.config import load_config
from mtah.validation import bundle

HEADER = "frame,h00,h01,h02,h10,h11,h12,h20,h21,h22,reprojection_error,valid"
IDENTITY = ["1", "0", "0", "0", "1", "0", "0", "0", "1"]


def row(matrix=None, error="NaN", flag="0", frame="0"):
    return ",".join([frame, *(["NaN"] * 9 if matrix is None else matrix), error, flag])


@pytest.fixture
def toy_csv(synthetic_bundle):
    root, config = synthetic_bundle
    config.write_text(config.read_text().replace("frame_count = 3", "frame_count = 1"))
    path = root / "homography.csv"

    def write(*rows):
        path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
        return path, config

    return write


def diagnose(config):
    assert hasattr(bundle, "diagnose_homography"), "Aggregate homography mode is not implemented"
    return bundle.diagnose_homography(load_config(config), "tactical").to_dict()


@pytest.mark.parametrize(
    "record,issue,reason",
    [
        (row() + ",extra", "invalid_record", "malformed_row_width"),
        (",".join(["0"] + ["NaN"] * 9 + ["0"]), "invalid_record", "malformed_row_width"),
        ("", "invalid_record", "malformed_row_width"),
        (row(frame="-1"), "invalid_record", "invalid_frame_index"),
        (row(frame="0.5"), "invalid_record", "invalid_frame_index"),
        (row(frame="0.0"), "invalid_record", "invalid_frame_index"),
        pytest.param(
            row(frame="9" * 5000), "invalid_record", "invalid_frame_index", id="oversized-frame"
        ),
        (row(frame="1"), "frame_sequence", "out_of_sequence_frame"),
        (row(flag="2"), "invalid_record", "invalid_valid_flag"),
        (row(flag="0.0"), "invalid_record", "invalid_valid_flag"),
        (row(flag="true"), "invalid_record", "invalid_valid_flag"),
        (row(flag=""), "invalid_record", "invalid_valid_flag"),
        (row(["private-cell"] * 9), "invalid_record", "malformed_matrix_numeric_cell"),
        (row(error="private-cell"), "invalid_record", "malformed_reprojection_error_numeric_cell"),
        (row(["0"] + ["NaN"] * 8), "invalid_record", "finite_values_on_unavailable_matrix"),
        (row(["inf"] + ["NaN"] * 8), "invalid_record", "infinite_values_on_unavailable_matrix"),
        (row(["-inf"] * 9), "invalid_record", "infinite_values_on_unavailable_matrix"),
        (row(error="inf"), "invalid_record", "infinite_unavailable_reprojection_error"),
        (row(error="-inf"), "invalid_record", "infinite_unavailable_reprojection_error"),
        (row(error="-1"), "invalid_record", "negative_reprojection_error"),
        (row(flag="1"), "invalid_record", "nonfinite_valid_matrix"),
        (row([""] * 9, "0", "1"), "invalid_record", "malformed_matrix_numeric_cell"),
        (row(["inf"] + IDENTITY[1:], "0", "1"), "invalid_record", "nonfinite_valid_matrix"),
        (row(IDENTITY, "", "1"), "invalid_record", "malformed_reprojection_error_numeric_cell"),
        (
            row(IDENTITY, "bad-error", "1"),
            "invalid_record",
            "malformed_reprojection_error_numeric_cell",
        ),
        (row(IDENTITY, "NaN", "1"), "invalid_record", "nonfinite_valid_reprojection_error"),
        (row(IDENTITY, "inf", "1"), "invalid_record", "nonfinite_valid_reprojection_error"),
        (row(IDENTITY, "-0.1", "1"), "invalid_record", "negative_reprojection_error"),
        (row(["0"] * 9, "0", "1"), "singular_matrix", "noninvertible_matrix"),
        (row(["1"] * 9, "0", "1"), "singular_matrix", "noninvertible_matrix"),
    ],
)
def test_each_rejection_preserves_failure_and_identifies_its_branch(toy_csv, record, issue, reason):
    path, config = toy_csv(record)
    before = path.read_bytes()
    document = diagnose(config)
    result = document["checks"][0]
    assert document["scope"] == "homography_only"
    assert not document["ok"]
    assert result["issues"] == {issue: 1}
    assert result["rejection_counts"] == {reason: 1}
    assert result["scan_complete"] is True
    assert result["unavailable_rows"] == 0
    assert path.read_bytes() == before
    ordinary = next(
        check.to_dict()
        for check in bundle.validate_bundle(load_config(config)).checks
        if check.asset == "tactical.homography"
    )
    assert {
        k: v for k, v in result.items() if k not in {"rejection_counts", "scan_complete"}
    } == ordinary


@pytest.mark.parametrize(
    "record,unavailable",
    [
        (row(), 1),
        (row([""] * 9, ""), 1),
        (row(error=""), 1),
        (row(error="304"), 1),
        (row(IDENTITY, "1e100", "1"), 0),
    ],
)
def test_expected_missingness_and_large_finite_error_do_not_fail(toy_csv, record, unavailable):
    _, config = toy_csv(record)
    document = diagnose(config)
    result = document["checks"][0]
    assert document["ok"]
    assert result["issues"] == result["rejection_counts"] == {}
    assert result["scan_complete"] is True
    assert result["unavailable_rows"] == unavailable


def test_multiple_conditions_preserve_first_rejection_and_independent_sequence_issue(toy_csv):
    # Parsing the error precedes checking matrix finiteness in the existing validator.
    _, config = toy_csv(row(["inf"] * 9, "bad-error", "1", frame="5"))
    result = diagnose(config)["checks"][0]
    assert result["issues"] == {"frame_sequence": 1, "invalid_record": 1}
    assert result["rejection_counts"] == {
        "out_of_sequence_frame": 1,
        "malformed_reprojection_error_numeric_cell": 1,
    }


def test_abort_marks_partial_counts_and_omits_unavailable_total(toy_csv):
    _, config = toy_csv(row(error="bad-error"), '1,"unterminated-private-cell')
    result = diagnose(config)["checks"][0]
    assert result["issues"] == {"invalid_record": 1, "invalid_csv": 1}
    assert result["rejection_counts"] == {
        "malformed_reprojection_error_numeric_cell": 1,
        "malformed_csv": 1,
    }
    assert result["scan_complete"] is False
    assert result["rows"] is None
    assert "unavailable_rows" not in result
    assert "private-cell" not in json.dumps(result)


@pytest.mark.parametrize(
    "mutation,issue,reason,complete",
    [
        ("header", "header", "invalid_header", False),
        ("row_count", "row_count", "row_count_mismatch", True),
        ("encoding", "unreadable_file", "unreadable_file", False),
        ("missing", "missing_file", "missing_file", False),
        ("directory", "not_regular_file", "not_regular_file", False),
        ("empty", "empty_file", "empty_file", False),
    ],
)
def test_file_failures_are_classified_without_fabricating_complete_scan(
    toy_csv, mutation, issue, reason, complete
):
    path, config = toy_csv(row())
    if mutation == "header":
        path.write_text("private-header\n")
    elif mutation == "row_count":
        path.write_text(HEADER + "\n")
    elif mutation == "encoding":
        path.write_bytes(b"\xffprivate-cell")
    elif mutation in {"missing", "directory"}:
        path.unlink()
        if mutation == "directory":
            path.mkdir()
    else:
        path.write_bytes(b"")
    document = diagnose(config)
    result = document["checks"][0]
    assert not document["ok"]
    assert result["issues"] == {issue: 1}
    assert result["rejection_counts"] == {reason: 1}
    assert result["scan_complete"] is complete
    assert "private" not in json.dumps(document)


def test_cli_is_deterministic_local_only_and_never_opens_other_assets(toy_csv, monkeypatch, capsys):
    path, config = toy_csv(row(error="-7.654321"))
    before = (path.read_bytes(), config.read_bytes())

    def guard(original):
        def checked(candidate, *args, **kwargs):
            assert candidate in {path, config}, "Unselected input accessed"
            return original(candidate, *args, **kwargs)

        return checked

    def no_network(*args, **kwargs):
        pytest.fail("Diagnostic attempted network access")

    for name in ("open_text", "open_binary", "stat_file"):
        monkeypatch.setattr(_io, name, guard(getattr(_io, name)))
    monkeypatch.setattr(socket, "socket", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    args = ["--local-only", "--config", str(config), "--diagnose-homography", "tactical"]
    assert cli.main(args) == 1
    first = capsys.readouterr()
    assert cli.main(args) == 1
    second = capsys.readouterr()
    assert first.out == second.out
    assert first.err == second.err == ""
    document = json.loads(first.out)
    assert len(document["checks"]) == 1
    assert document["checks"][0]["rejection_counts"] == {"negative_reprojection_error": 1}
    for value in (str(path), str(config), path.name, config.name, "7.654321", "Traceback"):
        assert value not in first.out
    assert (path.read_bytes(), config.read_bytes()) == before


def test_cli_requires_opt_in_before_any_input(toy_csv, monkeypatch):
    _, config = toy_csv(row())

    def never_load(*args):
        pytest.fail("Input opened without local-only opt-in")

    monkeypatch.setattr(cli, "load_config", never_load)
    with pytest.raises(SystemExit) as error:
        cli.main(["--config", str(config), "--diagnose-homography", "tactical"])
    assert error.value.code == 2


def test_unconfigured_source_fails_without_accessing_any_asset(toy_csv, monkeypatch, capsys):
    _, config = toy_csv(row())

    def never_access(*args):
        pytest.fail("An asset was accessed for an unconfigured source")

    monkeypatch.setattr(_io, "stat_file", never_access)
    assert (
        cli.main(["--local-only", "--config", str(config), "--diagnose-homography", "broadcast"])
        == 2
    )
    output = capsys.readouterr()
    assert json.loads(output.out)["error"] == "invalid_configuration"
    assert str(config) not in output.out + output.err


# Exact defaults documented by pandas 2.3 read_csv. No arbitrary spellings/whitespace added.
PUBLIC_NA_TOKENS = [
    "",
    "#N/A",
    "#N/A N/A",
    "#NA",
    "-1.#IND",
    "-1.#QNAN",
    "-NaN",
    "-nan",
    "1.#IND",
    "1.#QNAN",
    "<NA>",
    "N/A",
    "NA",
    "NULL",
    "NaN",
    "None",
    "n/a",
    "nan",
    "null",
]


@pytest.mark.parametrize("token", PUBLIC_NA_TOKENS)
@pytest.mark.parametrize("location", ["matrix", "error", "both"])
def test_documented_missing_tokens_match_actual_public_loader(
    toy_csv, monkeypatch, token, location
):
    import numpy as np
    from starter import load_homography

    matrix = [token if location != "error" else "NaN"] * 9
    error = token if location != "matrix" else "NaN"
    path, config = toy_csv(row(matrix, error))
    monkeypatch.setattr(load_homography, "require", lambda *args: [str(path)])
    matrices, errors, valid = load_homography.load()
    # Run the real official loader first: prove its behavior before requiring compatibility.
    assert not valid.any()
    assert np.isnan(matrices).all()
    assert np.isnan(errors).all()
    document = diagnose(config)
    assert document["ok"]
    check = document["checks"][0]
    assert check["issues"] == check["rejection_counts"] == {}
    assert check["unavailable_rows"] == 1


@pytest.mark.parametrize("token", ["missing", "undefined", "nil", "Null", "N/A ", " "])
@pytest.mark.parametrize("location", ["matrix", "error"])
def test_unknown_missing_tokens_are_still_corruption(toy_csv, token, location):
    matrix = [token if location == "matrix" else "NaN"] * 9
    error = token if location == "error" else "NaN"
    _, config = toy_csv(row(matrix, error))
    check = diagnose(config)["checks"][0]
    reason = (
        "malformed_matrix_numeric_cell"
        if location == "matrix"
        else "malformed_reprojection_error_numeric_cell"
    )
    assert check["issues"] == {"invalid_record": 1}
    assert check["rejection_counts"] == {reason: 1}
    assert check["unavailable_rows"] == 0


@pytest.mark.parametrize("token", ["", "NaN", "N/A", "NULL", "-1.#IND"])
@pytest.mark.parametrize("location", ["matrix", "error"])
def test_missing_tokens_cannot_make_valid_one_acceptable(toy_csv, token, location):
    matrix = [token] + IDENTITY[1:] if location == "matrix" else IDENTITY
    error = token if location == "error" else "0"
    _, config = toy_csv(row(matrix, error, "1"))
    document = diagnose(config)
    assert not document["ok"]
    assert document["checks"][0]["issues"] == {"invalid_record": 1}
    assert document["checks"][0]["unavailable_rows"] == 0


def test_counts_aggregate_repeated_failures_without_claiming_distinct_bad_rows(toy_csv):
    _, config = toy_csv(
        row(error="bad-error"),
        row(error="bad-error", frame="1"),
        row(flag="2", frame="9"),
        row(frame="3"),
    )
    config.write_text(config.read_text().replace("frame_count = 1", "frame_count = 4"))
    document = diagnose(config)
    result = document["checks"][0]
    assert not document["ok"]
    assert result["rows"] == 4
    assert result["unavailable_rows"] == 1
    assert result["issues"] == {"invalid_record": 3, "frame_sequence": 1}
    assert result["rejection_counts"] == {
        "malformed_reprojection_error_numeric_cell": 2,
        "invalid_valid_flag": 1,
        "out_of_sequence_frame": 1,
    }


def test_documented_command_selects_broadcast_only_in_independent_process(toy_csv, tmp_path):
    path, config = toy_csv(row(flag="2"))  # Tactical deliberately fails if accidentally selected.
    broadcast = path.with_name("invented-broadcast.csv")
    broadcast.write_text(HEADER + "\n" + row(["NULL"] * 9, "N/A") + "\n", encoding="utf-8")
    with config.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n[sources.broadcast]\nframe_count = 1\ntrack_slots = 2\nfps = 25\n"
            '[sources.broadcast.assets]\nvideo = "unselected-forbidden"\n'
            'atd_meta = "unselected-forbidden"\natd_raw = "unselected-forbidden"\n'
            'homography = "invented/invented-broadcast.csv"\n'
        )
    before = broadcast.read_bytes(), config.read_bytes(), path.read_bytes()
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_local.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--local-only",
            "--config",
            str(config),
            "--diagnose-homography",
            "broadcast",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    document = json.loads(result.stdout)
    assert document["scope"] == "homography_only"
    assert document["checks"] == [
        {
            "asset": "broadcast.homography",
            "status": "passed",
            "rows": 1,
            "issues": {},
            "unavailable_rows": 1,
            "rejection_counts": {},
            "scan_complete": True,
        }
    ]
    assert before == (broadcast.read_bytes(), config.read_bytes(), path.read_bytes())


@pytest.mark.parametrize("field", ["frame", "flag"])
def test_missing_tokens_are_never_allowed_for_required_indices_or_flags(toy_csv, field):
    _, config = toy_csv(row(**{field: "N/A"}))
    document = diagnose(config)
    result = document["checks"][0]
    assert not document["ok"]
    assert result["issues"] == {"invalid_record": 1}
    assert result["rejection_counts"] == {
        "invalid_frame_index" if field == "frame" else "invalid_valid_flag": 1
    }
