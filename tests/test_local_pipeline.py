"""Local-runner tests read invented files only, never competition data/configs."""

import csv
import hashlib
import json
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from mtah.local.config import LocalError, load_local_config
from mtah.local.inputs import iter_inputs, load_slot_teams, load_tags
from mtah.local.runner import run_local


def make_bundle(tmp_path, *, count=48, phase1=False, optional=False):
    dataset = tmp_path / "invented-input"
    output = tmp_path / "private-output"
    dataset.mkdir()
    output.mkdir()
    slots, fps = (46, 25) if phase1 else (2, 10)
    periods = [(1, 11185, 90652), (2, 110808, 190198)] if phase1 else [(1, 3, 18), (2, 25, 45)]
    # Interleave teams and reverse identifiers: never sort slots by ID/name.
    players = "".join(
        f'<Player id="slot-{slots - i}" teamId="{("away-id" if i % 2 else "home-id")}"/>'
        for i in range(slots)
    )
    (dataset / "metadata.xml").write_text(
        '<EPTS xmlns="urn:invented"><Team id="away-id"/><Team id="home-id"/>' + players + "</EPTS>",
        encoding="utf-8",
    )
    player_text = ";".join("0.8,0.5,0" if i % 2 else "0.2,0.5,0" for i in range(slots))
    with (dataset / "tracking.txt").open("w", encoding="utf-8", newline="\n") as stream:
        for frame in range(count):
            x = "0.8" if frame >= periods[1][1] else "0.2"
            ball = "NaN,NaN,NaN" if not phase1 and frame in (10, 11) else f"{x},0.5,0"
            stream.write(f"{frame + 1}:{player_text}:{ball}\n")
    assets = 'metadata = "metadata.xml"\ntracking = "tracking.txt"\n'
    if optional:
        from mtah.validation.bundle import HOMOGRAPHY_HEADER

        with (dataset / "quality.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(HOMOGRAPHY_HEADER)
            for frame in range(count):
                writer.writerow(
                    [frame]
                    + (["NaN"] * 10 + [0] if frame == 7 else [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1])
                )
        (dataset / "tags.xml").write_text(
            "<file><ALL_INSTANCES><instance><start>0</start><end>1.2</end><code>DEFENDING</code>"
            "<label><group>Team</group><text>Visitors</text></label></instance>"
            "<instance><start>1</start><end>2</end><code>SET PIECES</code>"
            "<label><group>Team</group><text>N/A</text></label></instance>"
            "</ALL_INSTANCES></file>",
            encoding="utf-8",
        )
        assets += 'homography = "quality.csv"\nsmart_tagging = "tags.xml"\n'
    path = tmp_path / "invented.toml"
    period_text = "".join(
        f"[[features.periods]]\nperiod_id={p}\nstart={a}\nstop={b}\n" for p, a, b in periods
    )
    path.write_text(
        f'schema_version = 1\nprofile = "{"phase1" if phase1 else "synthetic"}"\n'
        f'dataset_root = "{dataset.as_posix()}"\noutput_root = "{output.as_posix()}"\n'
        f"frame_count = {count}\ntrack_slots = {slots}\n"
        "[assets]\n" + assets + '[teams]\nhome_id="home-id"\naway_id="away-id"\n'
        'tag_home="Hosts"\ntag_away="Visitors"\n'
        "[features]\npitch_length_m=100.0\npitch_width_m=50.0\n"
        f"fps={fps}\n" + period_text + "[rules]\n[diagnostics]\nshort_fragment_s=1.0\n"
        "max_short_fragment_fraction=0.5\nmax_abstention_fraction=0.5\n"
        '[provenance]\nparameter_basis="provisional"\nreference="invented-test-only"\n',
        encoding="utf-8",
    )
    return dataset, output, path


def fingerprint(root):
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()
    }


def test_metadata_order_and_optional_sources_preserve_public_contract(tmp_path):
    _, _, path = make_bundle(tmp_path, optional=True)
    config = load_local_config(path)
    assert load_slot_teams(config) == ("H", "A")
    samples = list(iter_inputs(config))
    assert [s.tracking.video_frame for s in samples] == list(range(48))
    assert not samples[7].homography.valid
    assert not samples[10].tracking.ball.observed
    tags = load_tags(config)
    assert [(t.start, t.stop, t.team) for t in tags] == [(0, 12, "A"), (10, 20, None)]


def test_local_run_is_repeatable_private_and_read_only(tmp_path, monkeypatch):
    dataset, output, path = make_bundle(tmp_path, optional=True)
    before = fingerprint(dataset)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Network is prohibited"))
    result = run_local(load_local_config(path), "invented", verify_repeat=True)
    assert result == output / "invented"
    assert fingerprint(dataset) == before
    assert not (result / ".incomplete").exists()
    assert (result / ".gitignore").read_text() == "*\n"
    diagnostics = json.loads((result / "diagnostics.json").read_text())
    assert diagnostics["reproducibility"]["status"] == "identical"
    assert diagnostics["deterministic"]["coverage"]["rows"] == 48
    assert diagnostics["deterministic"]["missing_ball_frames"] == 2
    assert diagnostics["resources"]["elapsed_seconds"] > 0
    assert diagnostics["resources"]["peak_memory"]["bytes"] > 0
    assert "process_lifetime" in diagnostics["resources"]["peak_memory"]["scope"]
    raw_report = (result / "diagnostics.json").read_text()
    for forbidden in (str(dataset), "tracking.txt", "video_frame", "ball_x", "matrix", "home-id"):
        assert forbidden not in raw_report
    with (result / "submission.csv").open(encoding="utf-8") as stream:
        table = list(csv.DictReader(stream))
    assert [int(row["frame"]) for row in table] == list(range(48))
    assert all(
        row["label"] == "X" for i, row in enumerate(table) if not (3 <= i < 18 or 25 <= i < 45)
    )
    assert table[3]["label"] == table[25]["label"] == "X"
    assert table[17]["label"] == "H" and table[44]["label"] == "A"
    assert json.loads((result / "manifest.json").read_text())["schema_version"] == 1
    with pytest.raises(LocalError):
        run_local(load_local_config(path), "invented")
    assert fingerprint(dataset) == before


@pytest.mark.parametrize("change", ["duplicate", "gap", "short", "extra", "bad_number", "empty"])
def test_bad_tracking_fails_without_publishing_submission(tmp_path, change):
    dataset, output, path = make_bundle(tmp_path)
    source = dataset / "tracking.txt"
    lines = source.read_text().splitlines()
    if change == "duplicate":
        lines[6] = lines[5]
    elif change == "gap":
        lines[6] = lines[6].replace("7:", "8:")
    elif change == "short":
        lines.pop()
    elif change == "extra":
        lines.append("49:" + lines[-1].split(":", 1)[1])
    elif change == "bad_number":
        lines[6] = lines[6].replace("0.2", "PRIVATE_SENTINEL")
    else:
        lines[6] = ""
    source.write_text("\n".join(lines) + "\n")
    before = fingerprint(dataset)
    with pytest.raises(LocalError) as error:
        run_local(load_local_config(path), "failed")
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert not (output / "failed/submission.csv").exists()
    assert (output / "failed/.incomplete").exists()
    assert before == fingerprint(dataset)


@pytest.mark.parametrize(
    "change",
    ["inside_dataset", "escape_asset", "unknown_key", "wrong_phase1", "remote", "same_team"],
)
def test_configuration_boundaries(tmp_path, change):
    dataset, _, path = make_bundle(tmp_path)
    text = path.read_text()
    if change == "inside_dataset":
        text = text.replace("private-output", "invented-input")
    elif change == "escape_asset":
        text = text.replace("tracking.txt", "../secret.txt")
    elif change == "unknown_key":
        text += "unknown = 1\n"
    elif change == "wrong_phase1":
        text = text.replace('profile = "synthetic"', 'profile = "phase1"')
    elif change == "remote":
        text = text.replace(dataset.as_posix(), "//server/share")
    else:
        text = text.replace('away_id="away-id"', 'away_id="home-id"')
    path.write_text(text)
    with pytest.raises(LocalError):
        load_local_config(path)


def test_optional_sources_are_not_discovered(tmp_path):
    dataset, _, path = make_bundle(tmp_path)
    (dataset / "broadcast.csv").write_text("never read")
    config = load_local_config(path)
    assert load_tags(config) is None
    assert all(sample.homography is None for sample in iter_inputs(config))


@pytest.mark.parametrize(
    "target,change",
    [
        ("metadata.xml", 'teamId="home-id"'),
        ("tags.xml", "<start>0</start>"),
        ("quality.csv", "7,NaN"),
    ],
)
def test_invalid_optional_or_metadata_inputs_rejected(tmp_path, target, change):
    dataset, _, path = make_bundle(tmp_path, optional=True)
    asset = dataset / target
    replacement = {
        "metadata.xml": 'teamId="unmapped"',
        "tags.xml": "<start>-1</start>",
        "quality.csv": "8,NaN",
    }[target]
    asset.write_text(asset.read_text().replace(change, replacement))
    with pytest.raises(LocalError):
        run_local(load_local_config(path), "bad")


def test_cli_sanitizes_success_errors_and_requires_local_acknowledgment(tmp_path, capsys):
    from mtah.local.__main__ import main

    _, _, path = make_bundle(tmp_path)
    assert main(["--config", str(path), "--run-name", "cli", "--local-only"]) == 0
    output = capsys.readouterr()
    assert "complete" in output.out.lower()
    assert str(tmp_path) not in output.out and "label" not in output.out
    assert main(["--config", str(path), "--run-name", "../escape", "--local-only"]) != 0
    assert str(tmp_path) not in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--config", str(path), "--run-name", "no-ack"])


def test_full_length_file_pipeline_and_repeat_with_official_validator(tmp_path):
    dataset, _, path = make_bundle(tmp_path, count=199319, phase1=True)
    before = fingerprint(dataset)
    result = run_local(load_local_config(path), "full", verify_repeat=True)
    assert fingerprint(dataset) == before
    report = json.loads((result / "diagnostics.json").read_text())
    assert report["reproducibility"]["status"] == "identical"
    assert report["deterministic"]["coverage"]["rows"] == 199319
    assert report["deterministic"]["coverage"]["graded_rows"] == 158857
    boundaries = {}
    with (result / "submission.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            frame = int(row["frame"])
            if not (11185 <= frame < 90652 or 110808 <= frame < 190198):
                assert row["label"] == "X"
            if frame in (11185, 90651, 110808, 190197):
                boundaries[frame] = row["label"]
    assert boundaries == {11185: "X", 90651: "H", 110808: "X", 190197: "A"}
    official = Path(__file__).resolve().parents[1] / "evaluation/validate_submission.py"
    check = subprocess.run(
        [sys.executable, str(official), str(result / "submission.csv")],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert check.returncode == 0, "Unchanged official validator rejected invented CSV"
    assert "199319 rows, frame 0..199318" in check.stdout


def test_aggregate_runs_split_at_adjacent_periods_without_frame_details(tmp_path):
    from mtah.features import FeatureExtractor, Period
    from mtah.inference import FeatureContract, PossessionEngine
    from mtah.local.diagnostics import OperationalStats

    _, _, path = make_bundle(tmp_path)
    cfg = load_local_config(path)
    features = replace(cfg.features, periods=(Period(1, 0, 3), Period(2, 3, 6)))
    config = replace(cfg, features=features, frame_count=6)
    stats = OperationalStats(config)
    extractor = FeatureExtractor(features, ("H", "A"))
    engine = PossessionEngine(FeatureContract(features, ("H", "A")))
    for sample in list(iter_inputs(cfg))[:6]:
        p = engine.step(extractor.transform(sample))
        stats.add(sample, replace(p, label="H"))
    result = stats.finish()
    assert result["predicted_possessions"]["H"] == {
        "count": 2,
        "short_count": 2,
        "min_seconds": 0.3,
        "mean_seconds": 0.3,
        "max_seconds": 0.3,
    }
    assert result["operational_alerts"] == ["many_short_prediction_runs"]
    assert result["period_label_counts"] == {
        "1": {"H": 3, "A": 0, "D": 0, "X": 0},
        "2": {"H": 3, "A": 0, "D": 0, "X": 0},
    }


def test_input_change_keeps_run_incomplete(tmp_path, monkeypatch):
    import mtah.local.runner as runner

    dataset, output, path = make_bundle(tmp_path)
    original = runner._pass

    def mutate(*args):
        result = original(*args)
        with (dataset / "tracking.txt").open("a") as stream:
            stream.write("invented concurrent modification\n")
        return result

    monkeypatch.setattr(runner, "_pass", mutate)
    with pytest.raises(LocalError, match="inputs_changed"):
        run_local(load_local_config(path), "changed")
    assert (output / "changed/.incomplete").exists()
    assert not (output / "changed/manifest.json").exists()


def test_replay_mismatch_is_a_failure_not_parameter_selection(tmp_path, monkeypatch):
    import mtah.local.runner as runner

    _, output, path = make_bundle(tmp_path)
    original = runner._pass
    calls = 0

    def changed_stats(*args):
        nonlocal calls
        calls += 1
        stats, manifest = original(*args)
        if calls == 2:
            stats["missing_ball_frames"] += 1
        return stats, manifest

    monkeypatch.setattr(runner, "_pass", changed_stats)
    with pytest.raises(LocalError, match="non_deterministic"):
        run_local(load_local_config(path), "mismatch", verify_repeat=True)
    assert (output / "mismatch/.incomplete").exists()
    assert not (output / "mismatch/manifest.json").exists()


def test_resolved_output_alias_into_dataset_is_rejected_before_creation(tmp_path, monkeypatch):
    dataset, output, path = make_bundle(tmp_path)
    config = load_local_config(path)
    original = Path.resolve

    def resolve(p, *args, **kwargs):
        return dataset if p == output else original(p, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(LocalError, match="output_overlaps"):
        run_local(config, "alias")
    assert not (dataset / "alias").exists()
    assert not list(output.iterdir())


@pytest.mark.parametrize(
    "asset,body",
    [
        ("metadata.xml", '<!DOCTYPE EPTS [<!ENTITY bad "forbidden">]><EPTS>&bad;</EPTS>'),
        ("metadata.xml", '<EPTS><Team id="home-id"/><Team id="home-id"/></EPTS>'),
        ("tags.xml", "<file><ALL_INSTANCES/><instance/></file>"),
        ("quality.csv", "frame,valid\n0,1\n"),
    ],
)
def test_malformed_xml_and_csv_fail_closed(tmp_path, asset, body):
    dataset, _, path = make_bundle(tmp_path, optional=True)
    (dataset / asset).write_text(body, encoding="utf-8")
    with pytest.raises(LocalError):
        run_local(load_local_config(path), "invalid")


def test_line_resource_limit_and_unknown_team_tags(tmp_path):
    from mtah.local.config import MAX_LINE_CHARS

    dataset, _, path = make_bundle(tmp_path, optional=True)
    tags = dataset / "tags.xml"
    tags.write_text(tags.read_text().replace("Visitors", "Unmapped club"))
    config = load_local_config(path)
    assert all(t.team is None for t in load_tags(config))
    (dataset / "tracking.txt").write_text("x" * (MAX_LINE_CHARS + 1))
    with pytest.raises(LocalError, match="input_line_too_long"):
        list(iter_inputs(config))


def test_graded_abstention_alert_never_changes_predictions(tmp_path):
    dataset, _, path = make_bundle(tmp_path)
    tracking = dataset / "tracking.txt"
    lines = tracking.read_text().splitlines()
    tracking.write_text("".join(line.rsplit(":", 1)[0] + ":NaN,NaN,NaN\n" for line in lines))
    result = run_local(load_local_config(path), "missing")
    d = json.loads((result / "diagnostics.json").read_text())["deterministic"]
    assert d["graded_abstention_fraction"] == 1
    assert d["operational_alerts"] == ["high_graded_abstention"]
    assert d["label_counts"] == {"H": 0, "A": 0, "D": 0, "X": 48}


def test_manifest_records_effective_adapter_mapping_and_timeline(tmp_path):
    _, _, path = make_bundle(tmp_path, optional=True)
    config = load_local_config(path)
    result = run_local(config, "provenance")
    manifest = json.loads((result / "manifest.json").read_text())
    adapter = manifest["adapter"]
    assert adapter["home_metadata_team_id"] == "home-id"
    assert adapter["away_metadata_team_id"] == "away-id"
    assert adapter["home_tag_name"] == "Hosts"
    assert adapter["away_tag_name"] == "Visitors"
    assert adapter["tag_normalization"] == "strip_casefold_unknown_unmapped"
    assert adapter["frame_count"] == 48 and adapter["track_slots"] == 2
    assert adapter["atd_to_video_offset"] == -1
    assert set(adapter["enabled_assets"]) == {"metadata", "tracking", "homography", "smart_tagging"}


@pytest.mark.parametrize("extra", [["PRIVATE_SENTINEL"], ["--PRIVATE_SENTINEL"]])
def test_argument_errors_never_echo_private_arguments(extra, capsys):
    from mtah.local.__main__ import main

    with pytest.raises(SystemExit) as error:
        main(["--config", "private.toml", "--run-name", "sample", "--local-only", *extra])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert "PRIVATE_SENTINEL" not in output.out + output.err
    assert "private.toml" not in output.out + output.err


def test_malformed_options_have_fixed_errors(capsys):
    from mtah.local.__main__ import main

    with pytest.raises(SystemExit) as error:
        main(["--config", "--run-name", "PRIVATE_SENTINEL", "--local-only"])
    assert error.value.code == 2
    output = capsys.readouterr()
    assert "PRIVATE_SENTINEL" not in output.out + output.err
