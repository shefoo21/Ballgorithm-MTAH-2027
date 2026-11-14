"""Local orchestration with immutable inputs and private, newly created outputs."""

import hashlib
import importlib.metadata
import json
import re
import stat
import sys
import time
from dataclasses import asdict
from pathlib import Path

from mtah import _io
from mtah.features import FeatureExtractor
from mtah.inference import FeatureContract, PossessionEngine
from mtah.inference.submission import write_submission
from mtah.local.config import LocalConfig, LocalError, check_paths
from mtah.local.diagnostics import OperationalStats, peak_memory
from mtah.local.errors import call, guarded, iterate
from mtah.local.inputs import iter_inputs, load_slot_teams, load_tags


def _hash(path):
    if not stat.S_ISREG(_io.stat_file(path).st_mode):
        raise LocalError("input_must_be_regular_file")
    digest = hashlib.sha256()
    with _io.open_binary(path) as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _input_hashes(config):
    return {name: _hash(path) for name, path in sorted(config.assets.items())}


def _code_digest():
    # Only installed package Python source, never a repository-wide discovery scan.
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path, document):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def _pass(config, target, slot_teams, tags):
    if config.mode == "rules_temporal":
        from mtah.local.temporal import temporal_pass

        return temporal_pass(config, target, slot_teams, tags)
    stats = call("finalization", OperationalStats, config)
    extractor = call("feature_extraction", FeatureExtractor, config.features, slot_teams, tags)
    contract = call("rule_inference", FeatureContract, config.features, slot_teams)
    engine = call("rule_inference", PossessionEngine, contract, config.rules)

    def predictions():
        for sample in iterate("atd_input", iter_inputs, config):
            features = call("feature_extraction", extractor.transform, sample)
            prediction = call("rule_inference", engine.step, features)
            call("finalization", stats.add, sample, prediction)
            yield prediction

    call(
        "submission_writing",
        write_submission,
        target,
        predictions(),
        expected_rows=config.frame_count,
    )
    manifest = call("finalization", engine.manifest)
    manifest["mode"] = "rules"
    return call("finalization", stats.finish), manifest


def _reserve(directory):
    directory.mkdir()  # Exclusive; never inspect or reuse an old run.
    marker = directory / ".incomplete"
    marker.write_text("Incomplete run: do not submit artifacts.\n", encoding="utf-8")
    (directory / ".gitignore").write_text("*\n", encoding="utf-8", newline="\n")
    return marker


def _unchanged(config, before):
    if _input_hashes(config) != before:
        raise LocalError("inputs_changed_during_run")


def _verify_replay(second, output_hash, replay_stats, stats):
    if _hash(second) != output_hash or replay_stats != stats:
        raise LocalError("non_deterministic_replay")
    second.unlink()  # Only this run's new verification copy.


def _finalize(
    config,
    before,
    stats,
    inference_manifest,
    repeat,
    output_hash,
    started,
    directory,
    marker,
    verify_repeat,
):
    diagnostics = {
        "schema_version": 1,
        "kind": "local_operational_not_accuracy",
        "deterministic": stats,
        "reproducibility": repeat,
        "resources": {
            "elapsed_seconds": time.perf_counter() - started,
            "passes": 2 if verify_repeat else 1,
            "peak_memory": call("finalization", peak_memory),
        },
        "official_submission_validation": "run_separately_with_unchanged_validator",
    }
    inference_manifest["settings_provenance"] = config.parameter_basis
    manifest = {
        "schema_version": 1,
        "profile": config.profile,
        "adapter": {
            "frame_count": config.frame_count,
            "track_slots": config.track_slots,
            "atd_to_video_offset": -1,
            "enabled_assets": sorted(config.assets),
            "home_metadata_team_id": config.home_id,
            "away_metadata_team_id": config.away_id,
            "home_tag_name": config.tag_home,
            "away_tag_name": config.tag_away,
            "tag_normalization": "strip_casefold_unknown_unmapped",
        },
        "input_sha256": before,
        "submission_sha256": output_hash,
        "code_sha256": call("finalization", _code_digest),
        "python": sys.version,
        "dependencies": {
            "defusedxml": call("finalization", importlib.metadata.version, "defusedxml")
        },
        "inference": inference_manifest,
        "diagnostics_settings": asdict(config.diagnostics),
        "parameter_provenance": {
            "basis": config.parameter_basis,
            "reference": config.reference,
        },
        "rules_authority": "organizer_updated_email_recorded_2026-11-03",
    }
    call("finalization", _write_json, directory / "diagnostics.json", diagnostics)
    call("finalization", _write_json, directory / "manifest.json", manifest)
    call("finalization", marker.unlink)


@guarded("pipeline")
def run_local(config: LocalConfig, run_name: str, *, verify_repeat: bool = False) -> Path:
    """No network, GT, video or optional source discovery; return a new private run directory."""
    if (
        not isinstance(config, LocalConfig)
        or type(verify_repeat) is not bool
        or type(run_name) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_name) is None
    ):
        raise LocalError("invalid_run_request")
    _, output_root = check_paths(config)
    directory = output_root / run_name
    marker = call("output_setup", _reserve, directory)
    started = time.perf_counter()
    before = call("asset_checks", _input_hashes, config)
    slot_teams = call("metadata", load_slot_teams, config)
    tags = call("automatic_tags", load_tags, config)
    output = directory / "submission.csv"
    stats, inference_manifest = _pass(config, output, slot_teams, tags)
    output_hash = call("submission_writing", _hash, output)
    repeat = {"status": "not_requested", "csv_sha256": output_hash}
    if verify_repeat:
        call("repeat_verification", _unchanged, config, before)
        second = directory / "repeat.csv"
        replay_stats, _ = _pass(config, second, slot_teams, tags)
        call("repeat_verification", _verify_replay, second, output_hash, replay_stats, stats)
        repeat["status"] = "identical"
    call("finalization", _unchanged, config, before)
    call(
        "finalization",
        _finalize,
        config,
        before,
        stats,
        inference_manifest,
        repeat,
        output_hash,
        started,
        directory,
        marker,
        verify_repeat,
    )
    return directory
