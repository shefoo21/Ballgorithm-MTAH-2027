"""Exercise the user-only PowerShell gate with invented local files, never match data."""

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_local_pipeline import make_bundle
from test_local_temporal import enable

pytestmark = pytest.mark.skipif(
    os.name != "nt" or shutil.which("powershell.exe") is None,
    reason="The release gate explicitly targets Windows PowerShell 5.1",
)
ROOT = Path(__file__).resolve().parents[1]


def invoke(config, accepted):
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/reproduce_version_b.ps1"),
            "-Python",
            sys.executable,
            "-Config",
            str(config),
            "-AcceptedCsv",
            str(accepted),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def assert_private(result, tmp_path):
    assert str(tmp_path) not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    assert "home-id" not in result.stdout + result.stderr
    assert not result.stderr


@pytest.mark.parametrize("failure", ["rules", "override", "malformed_config", "malformed_atd"])
def test_gate_rejects_unsafe_or_failed_runs_without_private_output(tmp_path, failure):
    dataset, output, config = make_bundle(tmp_path, count=48, phase1=True)
    config.write_text(config.read_text().replace("frame_count = 48", "frame_count = 199319"))
    if failure != "rules":
        enable(config, "turnover_cost=0.2\n" if failure == "override" else "")
    if failure == "malformed_config":
        config.write_text("private_identifier = [\n")
    if failure == "malformed_atd":
        (dataset / "tracking.txt").write_text("invented-private-corruption\n")
    accepted = tmp_path / "invented-previous.csv"
    accepted.write_text("frame,label\n0,X\n")
    before = config.read_bytes(), accepted.read_bytes()
    result = invoke(config, accepted)
    assert result.returncode == 1
    expected = "inference" if failure == "malformed_atd" else "preflight"
    assert f"release_gate/{expected}" in result.stdout
    assert_private(result, tmp_path)
    assert (config.read_bytes(), accepted.read_bytes()) == before
    if failure == "malformed_atd":
        runs = list(output.iterdir())
        assert len(runs) == 1
        assert (runs[0] / ".incomplete").is_file()
        assert not (runs[0] / "submission.csv").exists()
    else:
        assert not list(output.iterdir())


@pytest.mark.parametrize("mismatch", [False, True])
def test_full_length_powershell_gate_requires_exact_bytes(tmp_path, mismatch):
    _, output, config = make_bundle(tmp_path, count=199319, phase1=True)
    enable(config)
    accepted = tmp_path / "invented-previous.csv"
    with accepted.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("frame,label\n")
        for frame in range(199319):
            label = "H" if 11185 <= frame < 90652 else "A" if 110808 <= frame < 190198 else "X"
            if mismatch and frame == 11185:
                label = "A"
            stream.write(f"{frame},{label}\n")
    original = hashlib.sha256(accepted.read_bytes()).hexdigest()
    result = invoke(config, accepted)
    assert_private(result, tmp_path)
    assert original not in result.stdout
    assert result.returncode == int(mismatch)
    assert ("release_gate/exact_bytes" if mismatch else "PASS: Version B") in result.stdout
    assert hashlib.sha256(accepted.read_bytes()).hexdigest() == original
    runs = list(output.iterdir())
    assert len(runs) == 1
    assert (runs[0] / "submission.csv").is_file()
    assert not (runs[0] / ".incomplete").exists()
    assert not (runs[0] / "repeat.csv").exists()
