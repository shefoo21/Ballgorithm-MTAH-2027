"""Failure diagnosis on invented files only; never inspect a private failed run."""

import csv
import errno
import socket
from pathlib import Path

import pytest
from test_local_pipeline import fingerprint, make_bundle

from mtah.features import FeatureError
from mtah.inference import InferenceError
from mtah.local.__main__ import main
from mtah.local.config import LocalError, load_local_config
from mtah.local.runner import run_local

SECRET = "PRIVATE_SENTINEL_team_coordinates_frame_9342"


def cli(path, capsys, *, run="diagnosis", extra=()):
    code = main(["--config", str(path), "--run-name", run, "--local-only", "--diagnose", *extra])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert SECRET not in captured.out and str(path.parent) not in captured.out
    assert "Traceback" not in captured.out
    return code, captured.out.strip()


@pytest.mark.parametrize(
    "case,expected",
    [
        ("toml", "configuration/invalid_toml"),
        ("missing_config", "configuration/not_found"),
        ("same_team", "configuration/ambiguous_team_mapping"),
        ("missing_asset", "asset_checks/not_found"),
        ("metadata_parse", "metadata/invalid_metadata"),
        ("team_mapping", "metadata/metadata_team_reference"),
        ("bad_atd", "atd_input/invalid_atd_record"),
        ("frame_gap", "atd_input/tracking_frame_sequence"),
        ("truncated", "atd_input/tracking_row_count"),
        ("encoding", "atd_input/invalid_encoding"),
        ("features", "feature_extraction/invalid_features"),
        ("inference_contract", "rule_inference/invalid_inference"),
    ],
)
def test_real_invented_failures_have_fixed_origin(tmp_path, capsys, case, expected):
    dataset, output, path = make_bundle(tmp_path)
    if case == "toml":
        path.write_text(SECRET + '="unterminated')
    elif case == "missing_config":
        path = tmp_path / (SECRET + ".toml")
    elif case == "same_team":
        path.write_text(path.read_text().replace('away_id="away-id"', 'away_id="home-id"'))
    elif case == "missing_asset":
        (dataset / "tracking.txt").unlink()
    elif case == "metadata_parse":
        (dataset / "metadata.xml").write_text("<" + SECRET)
    elif case == "team_mapping":
        p = dataset / "metadata.xml"
        p.write_text(p.read_text().replace('teamId="home-id"', 'teamId="' + SECRET + '"'))
    elif case in ("bad_atd", "frame_gap", "truncated", "encoding", "features"):
        p = dataset / "tracking.txt"
        lines = p.read_text().splitlines()
        if case == "bad_atd":
            lines[6] = lines[6].replace("0.2", SECRET)
        elif case == "frame_gap":
            lines[6] = lines[6].replace("7:", "8:")
        elif case == "truncated":
            lines.pop()
        elif case == "features":
            # Finite ATD coordinates pass parsing; distance arithmetic overflows in features.
            lines[6] = "7:1e308,0.5,0;0.8,0.5,0:-1e308,0.5,0"
        p.write_text("\n".join(lines) + "\n")
        if case == "encoding":
            with p.open("ab") as stream:
                stream.write(b"\xff")
    elif case == "inference_contract":
        path.write_text(path.read_text().replace("[rules]", "[rules]\nsupport_radius_m=2"))
    before = fingerprint(dataset)
    status, text = cli(path, capsys)
    assert status == 1 and text == "Local inference failed: " + expected
    assert fingerprint(dataset) == before
    assert not (output / "diagnosis/submission.csv").exists()
    if (output / "diagnosis").exists():
        assert (output / "diagnosis/.incomplete").exists()


@pytest.mark.parametrize(
    "stage,target,exception",
    [
        ("asset_checks/permission_denied", "_input_hashes", PermissionError(SECRET)),
        ("metadata/unexpected_error", "load_slot_teams", RuntimeError(SECRET)),
        ("automatic_tags/unexpected_error", "load_tags", RuntimeError(SECRET)),
        ("submission_writing/storage_full", "write_submission", OSError(errno.ENOSPC, SECRET)),
        ("finalization/permission_denied", "_write_json", PermissionError(SECRET)),
    ],
)
def test_os_and_internal_failures_are_sanitized(
    tmp_path, capsys, monkeypatch, stage, target, exception
):
    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)

    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(runner, target, fail)
    status, text = cli(path, capsys)
    assert status == 1 and text == "Local inference failed: " + stage
    assert (output / "diagnosis/.incomplete").exists()


@pytest.mark.parametrize(
    "origin,error,expected",
    [
        ("features", FeatureError(SECRET), "feature_extraction/invalid_features"),
        ("inference", InferenceError(SECRET), "rule_inference/invalid_inference"),
        ("inference", LocalError(SECRET), "rule_inference/unexpected_error"),
    ],
)
def test_lazy_producer_failure_is_not_misreported_as_writer(
    tmp_path, capsys, monkeypatch, origin, error, expected
):
    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)

    def fail(*args):
        raise error

    cls = runner.FeatureExtractor if origin == "features" else runner.PossessionEngine
    monkeypatch.setattr(cls, "transform" if origin == "features" else "step", fail)
    status, text = cli(path, capsys)
    assert status == 1 and text.endswith(expected)
    assert not (output / "diagnosis/submission.csv").exists()
    assert (output / "diagnosis/.incomplete").exists()


def test_success_bytes_remain_baseline_and_diagnosis_uses_no_network(tmp_path, capsys, monkeypatch):
    dataset, _, path = make_bundle(tmp_path)
    before = fingerprint(dataset)
    baseline = run_local(load_local_config(path), "baseline")
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Network prohibited"))
    status, text = cli(path, capsys, extra=("--verify-repeat",))
    assert status == 0 and text == "Local inference complete: complete/ok"
    diagnosed = baseline.parent / "diagnosis"
    assert (baseline / "submission.csv").read_bytes() == (diagnosed / "submission.csv").read_bytes()
    assert fingerprint(dataset) == before
    assert not (diagnosed / ".incomplete").exists()
    with (diagnosed / "submission.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == 48


def test_diagnostics_refuse_to_enable_or_override_temporal_mode(tmp_path, capsys):
    from test_local_temporal import enable

    _, output, path = make_bundle(tmp_path)
    enable(path)
    status, text = cli(path, capsys)
    assert status == 1 and text.endswith("configuration/diagnostics_require_rules_mode")
    assert not list(output.iterdir())


def test_existing_run_is_never_inspected_or_reused(tmp_path, capsys):
    _, output, path = make_bundle(tmp_path)
    folder = output / "diagnosis"
    folder.mkdir()
    (folder / "private.txt").write_text(SECRET)
    before = fingerprint(folder)
    status, text = cli(path, capsys)
    assert status == 1 and text.endswith("output_setup/already_exists")
    assert fingerprint(folder) == before


@pytest.mark.parametrize(
    "asset,body,expected",
    [
        ("tags.xml", "<broken", "automatic_tags/invalid_automatic_tags"),
        ("quality.csv", "frame,valid\n0,1\n", "homography_input/homography_header"),
    ],
)
def test_optional_input_failures_are_not_attributed_to_atd(tmp_path, capsys, asset, body, expected):
    dataset, _, path = make_bundle(tmp_path, optional=True)
    (dataset / asset).write_text(body + SECRET)
    assert cli(path, capsys) == (1, "Local inference failed: " + expected)


@pytest.mark.parametrize(
    "operation,expected",
    [
        ("config_read", "configuration/permission_denied"),
        ("tracking_read", "atd_input/permission_denied"),
        ("writer_create", "submission_writing/permission_denied"),
        ("marker_remove", "finalization/permission_denied"),
        ("guard_create", "output_setup/permission_denied"),
    ],
)
def test_permission_failures_at_real_io_boundaries(
    tmp_path, capsys, monkeypatch, operation, expected
):
    from mtah import _io
    from mtah.inference import submission

    dataset, output, path = make_bundle(tmp_path)

    def denied(*args, **kwargs):
        raise PermissionError(13, SECRET, str(path))

    if operation == "config_read":
        monkeypatch.setattr(_io, "open_binary", denied)
    elif operation == "tracking_read":
        monkeypatch.setattr(_io, "open_text", denied)
    elif operation == "writer_create":
        monkeypatch.setattr(submission.tempfile, "NamedTemporaryFile", denied)
    else:
        name = "unlink" if operation == "marker_remove" else "write_text"
        original = getattr(Path, name)

        def restricted(p, *args, **kwargs):
            if p.parent == output / "diagnosis" and p.name == (
                ".incomplete" if operation == "marker_remove" else ".gitignore"
            ):
                denied()
            return original(p, *args, **kwargs)

        monkeypatch.setattr(Path, name, restricted)
    before = fingerprint(dataset)
    assert cli(path, capsys) == (1, "Local inference failed: " + expected)
    assert fingerprint(dataset) == before
    if operation != "config_read":
        assert (output / "diagnosis/.incomplete").exists()


def test_replay_mismatch_has_repeat_category_and_keeps_marker(tmp_path, capsys, monkeypatch):
    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)
    original, count = runner._pass, 0

    def changed(*args):
        nonlocal count
        count += 1
        stats, manifest = original(*args)
        if count == 2:
            stats["missing_ball_frames"] += 1
        return stats, manifest

    monkeypatch.setattr(runner, "_pass", changed)
    assert cli(path, capsys, extra=("--verify-repeat",)) == (
        1,
        "Local inference failed: repeat_verification/non_deterministic_replay",
    )
    assert (output / "diagnosis/.incomplete").exists()


def test_final_report_serialization_failure_does_not_mark_run_complete(
    tmp_path, capsys, monkeypatch
):
    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)
    original = runner._write_json

    def invalid_report(target, document):
        original(target, {**document, "invented_bad_value": float("nan")})

    monkeypatch.setattr(runner, "_write_json", invalid_report)
    assert cli(path, capsys) == (1, "Local inference failed: finalization/invalid_report")
    assert (output / "diagnosis/submission.csv").exists()
    assert (output / "diagnosis/.incomplete").exists()


def test_invalid_generated_submission_remains_a_failure(tmp_path, capsys, monkeypatch):
    from dataclasses import replace

    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)
    original = runner.PossessionEngine.step
    monkeypatch.setattr(
        runner.PossessionEngine, "step", lambda self, f: replace(original(self, f), label=SECRET)
    )
    assert cli(path, capsys) == (1, "Local inference failed: submission_writing/invalid_submission")
    assert not (output / "diagnosis/submission.csv").exists()
    assert (output / "diagnosis/.incomplete").exists()


def test_finalization_assembly_errors_have_finalization_stage(tmp_path, capsys, monkeypatch):
    import mtah.local.runner as runner

    _, _, path = make_bundle(tmp_path)

    def fail(*args):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(runner, "asdict", fail)
    assert cli(path, capsys) == (1, "Local inference failed: finalization/unexpected_error")


@pytest.mark.parametrize("prior", ["os", "classified"])
def test_unrelated_active_exception_cannot_poison_diagnosis(prior):
    from mtah.local.errors import LocalFailure, classify, fixed_details

    try:
        raise PermissionError(SECRET) if prior == "os" else LocalFailure("metadata", "not_found")
    except (PermissionError, LocalFailure):
        try:
            raise FeatureError(SECRET)
        except FeatureError as error:
            assert fixed_details(classify("feature_extraction", error)) == (
                "feature_extraction",
                "invalid_features",
            )


def test_unknown_error_payload_is_never_formatted_or_compared(tmp_path, capsys, monkeypatch):
    import mtah.local.runner as runner

    class ForbiddenPayload:
        def __str__(self):
            raise AssertionError(SECRET)

        def __repr__(self):
            raise AssertionError(SECRET)

        def __eq__(self, other):
            raise AssertionError(SECRET)

    _, _, path = make_bundle(tmp_path)

    def fail(*args):
        raise LocalError(ForbiddenPayload())

    monkeypatch.setattr(runner.PossessionEngine, "step", fail)
    assert cli(path, capsys) == (1, "Local inference failed: rule_inference/unexpected_error")


def test_interrupt_is_fixed_and_does_not_complete_run(tmp_path, capsys, monkeypatch):
    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)

    def stop(*args):
        raise KeyboardInterrupt(SECRET)

    monkeypatch.setattr(runner, "load_slot_teams", stop)
    assert cli(path, capsys) == (130, "Local inference failed: metadata/interrupted")
    assert (output / "diagnosis/.incomplete").exists()


def test_remote_root_has_fixed_asset_path_category(tmp_path, capsys):
    dataset, _, path = make_bundle(tmp_path)
    path.write_text(path.read_text().replace(dataset.as_posix(), "//" + SECRET + "/share"))
    assert cli(path, capsys) == (1, "Local inference failed: asset_checks/invalid_local_path")


def test_normal_cli_also_sanitizes_untrusted_localerror(tmp_path, capsys, monkeypatch):
    import mtah.local.runner as runner

    _, _, path = make_bundle(tmp_path)

    def fail(*args):
        raise LocalError(SECRET)

    monkeypatch.setattr(runner.PossessionEngine, "step", fail)
    status = main(["--config", str(path), "--run-name", "normal", "--local-only"])
    captured = capsys.readouterr()
    assert status == 1
    assert captured.out.strip() == "Local inference failed: rule_inference/unexpected_error"
    assert captured.err == ""


def test_allowlist_rechecks_mutated_error_and_handles_context_cycles():
    from mtah.local.errors import LocalFailure, classify, fixed_details

    failure = LocalFailure("metadata", "not_found")
    failure.stage = SECRET
    assert fixed_details(classify("pipeline", failure)) == ("pipeline", "unexpected_error")
    wrapper = LocalError("invalid_tactical_input")
    wrapper.__context__ = wrapper
    assert fixed_details(classify("atd_input", wrapper)) == ("atd_input", "invalid_tactical_input")
