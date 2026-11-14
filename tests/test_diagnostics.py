"""Diagnostic development uses invented JSON reports only."""

import copy
import importlib
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def diagnostics():
    try:
        return importlib.import_module("mtah.diagnostics")
    except ModuleNotFoundError:
        pytest.fail("Report diagnostic helper has not been implemented")


def check(asset, status="passed", issues=None, rows=3, **extra):
    return {"asset": asset, "status": status, "issues": issues or {}, "rows": rows, **extra}


def report(*checks):
    return {
        "schema_version": 1,
        "scope": "structural_only_videos_unverified",
        "ok": not any(item["status"] == "failed" for item in checks),
        "checks": list(checks),
    }


@pytest.fixture
def toy_report(tmp_path):
    path = tmp_path / "invented-report.json"

    def write(document):
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    return write


def run(document, toy_report, capsys):
    path = toy_report(document)
    code = diagnostics().main(["--local-only", "--report", str(path)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_missing_file_is_identified_without_blame_on_homography(toy_report, capsys):
    code, out, err = run(
        report(
            check("tactical.video", "failed", {"missing_file": 1}, rows=None),
            check("broadcast.homography", unavailable_rows=2),
        ),
        toy_report,
        capsys,
    )
    assert code == 1
    assert "tactical.video" in out and "missing_file" in out
    assert "filename" in out.lower() and "configuration" in out.lower()
    assert "2 expected unavailable" in out
    assert "invalid_record" not in out
    assert err == ""


ISSUE_CASES = [
    ("missing_file", "tactical.video", "File availability", "filename"),
    ("not_regular_file", "tactical.atd_raw", "File availability", "directory"),
    ("empty_file", "tactical.atd_raw", "File availability", "empty"),
    ("unreadable_file", "tactical.atd_raw", "File access", "encoding"),
    ("header", "broadcast.homography", "Malformed data", "header"),
    ("invalid_csv", "broadcast.homography", "Malformed data", "quoting"),
    ("invalid_xml", "tactical.atd_meta", "Malformed data", "XML"),
    ("unsafe_xml", "tactical.atd_meta", "Unsafe XML", "entities"),
    ("xml_structure", "tactical.smart_tagging", "Malformed data", "ALL_INSTANCES"),
    ("invalid_record", "tactical.atd_raw", "Malformed data", "triplets"),
    ("invalid_record", "broadcast.homography", "Malformed data", "valid=1"),
    ("frame_sequence", "tactical.atd_raw", "Frame alignment", "1-based"),
    ("frame_sequence", "broadcast.homography", "Frame alignment", "0-based"),
    ("row_count", "broadcast.homography", "Count mismatch", "frame_count"),
    ("singular_matrix", "broadcast.homography", "Malformed data", "singular"),
    ("team_count", "tactical.atd_meta", "Metadata mismatch", "two"),
    ("slot_count", "tactical.atd_meta", "Metadata mismatch", "track_slots"),
    ("team_reference", "tactical.atd_meta", "Metadata mismatch", "teamId"),
    ("invalid_interval", "tactical.smart_tagging", "Malformed data", "seconds"),
    ("missing_code", "tactical.smart_tagging", "Malformed data", "code"),
    ("event_count", "tactical.smart_tagging", "Count mismatch", "event_count"),
]


@pytest.mark.parametrize("issue,asset,category,detail", ISSUE_CASES)
def test_issue_codes_have_meaning_possible_causes_and_local_actions(
    toy_report, capsys, issue, asset, category, detail
):
    code, out, _ = run(report(check(asset, "failed", {issue: 2})), toy_report, capsys)
    assert code == 1
    assert issue in out and asset in out and category in out
    assert detail in out
    assert "Meaning:" in out and "Possible causes:" in out and "Local action:" in out
    assert "2 occurrence(s)" in out
    assert "not necessarily distinct rows" in out


def test_multiple_failures_are_all_explained(toy_report, capsys):
    code, out, _ = run(
        report(
            check(
                "broadcast.homography",
                "failed",
                {"invalid_record": 2, "row_count": 1},
                unavailable_rows=1,
            ),
            check("tactical.atd_meta", "failed", {"team_reference": 1}),
        ),
        toy_report,
        capsys,
    )
    assert code == 1
    for text in ("invalid_record", "row_count", "team_reference", "1 expected unavailable"):
        assert text in out


def test_only_unavailability_and_unverified_video_do_not_create_failure(toy_report, capsys):
    code, out, _ = run(
        report(
            check("broadcast.homography", unavailable_rows=3),
            check("tactical.video", "present_unverified", rows=None),
        ),
        toy_report,
        capsys,
    )
    assert code == 0
    assert "Reported checks passed" in out
    assert "3 expected unavailable" in out
    assert "not a structural error" in out
    assert "Video content remains unverified" in out
    assert "does not rerun validation" in out


def test_older_report_does_not_invent_zero_unavailable_rows(toy_report, capsys):
    code, out, _ = run(report(check("broadcast.homography")), toy_report, capsys)
    assert code == 0
    assert "unavailable count was not recorded" in out
    assert "0 expected unavailable" not in out


@pytest.mark.parametrize(
    "error,detail",
    [
        ("invalid_configuration", "configuration"),
        ("internal_validation_error", "synthetic"),
        ("private-unknown-error", "Unrecognized validator error"),
    ],
)
def test_compact_validator_errors_stay_unresolved(toy_report, capsys, error, detail):
    code, out, _ = run({"schema_version": 1, "ok": False, "error": error}, toy_report, capsys)
    assert code == 2
    assert detail in out
    assert "private-unknown-error" not in out


def test_unknown_issue_is_not_silently_accepted_or_echoed(toy_report, capsys):
    code, out, _ = run(
        report(check("broadcast.homography", "failed", {"private-value\u001b[31m": 1})),
        toy_report,
        capsys,
    )
    assert code == 1
    assert "Unrecognized issue code" in out
    assert "private-value" not in out and "\u001b" not in out


def test_report_is_the_only_input_and_is_never_changed(toy_report, monkeypatch, capsys):
    from mtah import _io, config, validation

    document = report(check("tactical.video", "failed", {"missing_file": 1}, rows=None))
    document["private_config"] = "DO_NOT_ACCESS/config.toml"
    document["checks"][0]["path"] = "DO_NOT_ACCESS/match.mp4"
    path = toy_report(document)
    before = path.read_bytes()
    original_open, original_stat = _io.open_binary, _io.stat_file

    def guarded(original):
        def call(candidate):
            assert Path(candidate) == path
            return original(candidate)

        return call

    def forbidden(*args, **kwargs):
        pytest.fail("Diagnostics attempted validation, configuration loading, or networking")

    monkeypatch.setattr(_io, "open_binary", guarded(original_open))
    monkeypatch.setattr(_io, "stat_file", guarded(original_stat))
    monkeypatch.setattr(config, "load_config", forbidden)
    monkeypatch.setattr(validation, "validate_bundle", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert diagnostics().main(["--report", str(path), "--local-only"]) == 1
    out = capsys.readouterr().out
    assert "DO_NOT_ACCESS" not in out
    assert path.read_bytes() == before


def test_opt_in_is_required_before_report_access(monkeypatch):
    from mtah import _io

    def forbidden(*args):
        pytest.fail("Report accessed before local opt-in")

    monkeypatch.setattr(_io, "open_binary", forbidden)
    monkeypatch.setattr(_io, "stat_file", forbidden)
    with pytest.raises(SystemExit) as error:
        diagnostics().main(["--report", "not-opened.json"])
    assert error.value.code == 2


@pytest.mark.parametrize(
    "candidate",
    [
        "https://server.invalid/report.json",
        r"\\server.invalid\share\report.json",
        r"\\?\UNC\server.invalid\share\report.json",
    ],
)
def test_remote_paths_are_rejected_before_file_access(candidate, monkeypatch, capsys):
    from mtah import _io

    def forbidden(*args):
        pytest.fail("Remote path reached the filesystem")

    monkeypatch.setattr(_io, "open_binary", forbidden)
    monkeypatch.setattr(_io, "stat_file", forbidden)
    assert diagnostics().main(["--local-only", "--report", candidate]) == 2
    out = capsys.readouterr().out
    assert "server.invalid" not in out


@pytest.mark.parametrize(
    "mutation",
    [
        "ok",
        "status",
        "count_bool",
        "count_negative",
        "count_string",
        "unavailable_too_large",
        "duplicate_asset",
        "empty_checks",
        "version",
        "unknown_asset",
        "passed_with_issue",
        "failed_without_issue",
        "video_status",
        "scope",
    ],
)
def test_inconsistent_or_unsupported_reports_are_not_interpreted_as_success(
    toy_report, capsys, mutation
):
    document = report(check("broadcast.homography", "failed", {"invalid_record": 1}))
    item = document["checks"][0]
    if mutation == "ok":
        document["ok"] = True
    elif mutation == "status":
        item["status"] = "private-status"
    elif mutation.startswith("count_"):
        item["issues"]["invalid_record"] = {
            "count_bool": True,
            "count_negative": -1,
            "count_string": "1",
        }[mutation]
    elif mutation == "unavailable_too_large":
        item["unavailable_rows"] = 4
    elif mutation == "duplicate_asset":
        document["checks"].append(copy.deepcopy(item))
    elif mutation == "empty_checks":
        document["checks"] = []
        document["ok"] = True
    elif mutation == "version":
        document["schema_version"] = 2
    elif mutation == "unknown_asset":
        item["asset"] = "private-asset"
    elif mutation == "passed_with_issue":
        item["status"] = "passed"
        document["ok"] = True
    elif mutation == "failed_without_issue":
        item["issues"] = {}
    elif mutation == "video_status":
        item["status"] = "present_unverified"
        item["issues"] = {}
        document["ok"] = True
    else:
        document["scope"] = "private-scope"
    code, out, err = run(document, toy_report, capsys)
    assert code == 2
    assert "Cannot interpret report" in out
    assert "private-" not in out + err


@pytest.mark.parametrize(
    "content",
    [
        b'{"private-value":',
        b"[]",
        b"null",
        b"\xffprivate-value",
        b'{"schema_version":1,"schema_version":2}',
        b'{"private-value":NaN}',
    ],
)
def test_malformed_json_errors_do_not_echo_contents_or_paths(tmp_path, capsys, content):
    path = tmp_path / "private-name.json"
    path.write_bytes(content)
    assert diagnostics().main(["--local-only", "--report", str(path)]) == 2
    captured = capsys.readouterr()
    assert "private-" not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def test_utf8_bom_report_is_supported(toy_report, capsys):
    path = toy_report(report(check("tactical.atd_raw")))
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert diagnostics().main(["--local-only", "--report", str(path)]) == 0
    assert "Reported checks passed" in capsys.readouterr().out


def test_oversized_report_is_rejected_with_local_guidance(tmp_path, capsys):
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * (1024 * 1024 + 1))
    assert diagnostics().main(["--local-only", "--report", str(path)]) == 2
    assert "size limit" in capsys.readouterr().out


def test_missing_report_has_no_private_path_in_error(tmp_path, capsys):
    assert (
        diagnostics().main(["--local-only", "--report", str(tmp_path / "private-missing.json")])
        == 2
    )
    captured = capsys.readouterr()
    assert "Cannot read report" in captured.out
    assert "private-missing" not in captured.out + captured.err


def test_script_runs_independently_on_synthetic_json(toy_report):
    path = toy_report(report(check("tactical.video", "failed", {"missing_file": 1}, rows=None)))
    script = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_validation.py"
    result = subprocess.run(
        [sys.executable, str(script), "--local-only", "--report", str(path)],
        cwd=path.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing_file" in result.stdout
    assert "Possible causes:" in result.stdout and result.stderr == ""
