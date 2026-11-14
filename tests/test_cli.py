import importlib
import json
import os
import subprocess
import sys

import pytest


def run_cli(*args):
    env = dict(os.environ, MTAH_DATA_DIR="DO_NOT_ACCESS_ENVIRONMENT")
    return subprocess.run(
        [sys.executable, "-m", "mtah.cli", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_cli_requires_local_opt_in_before_loading_config(monkeypatch):
    try:
        cli = importlib.import_module("mtah.cli")
    except ModuleNotFoundError:
        pytest.fail("CLI has not been implemented")

    def never_load(*args):
        pytest.fail("Configuration was accessed before local opt-in")

    monkeypatch.setattr(cli, "load_config", never_load)
    with pytest.raises(SystemExit) as error:
        cli.main(["--config", "nonexistent.toml"])
    assert error.value.code == 2


def test_cli_output_is_deterministic_and_inputs_are_unchanged(synthetic_bundle, snapshot):
    root, path = synthetic_bundle
    before = snapshot(root)
    first = run_cli("--local-only", "--config", path)
    second = run_cli("--local-only", "--config", path)
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    assert first.stderr == ""
    assert json.loads(first.stdout)["ok"]
    assert str(root) not in first.stdout
    assert snapshot(root) == before


def test_cli_validation_failure_exits_one_without_excerpts(synthetic_bundle):
    root, path = synthetic_bundle
    (root / "tracking.txt").write_text("private-value", encoding="utf-8")
    result = run_cli("--local-only", "--config", path)
    assert result.returncode == 1
    assert not json.loads(result.stdout)["ok"]
    assert "private-value" not in result.stdout + result.stderr


def test_cli_config_failure_exits_two_without_path_or_traceback(tmp_path):
    result = run_cli("--local-only", "--config", tmp_path / "secret.toml")
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"] == "invalid_configuration"
    assert "secret" not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr


def test_unexpected_library_error_is_sanitized_at_cli_boundary(
    synthetic_bundle, monkeypatch, capsys
):
    from mtah import cli

    _, path = synthetic_bundle

    def broken_validator(_config):
        raise RuntimeError("private-value-in-library-exception")

    monkeypatch.setattr(cli, "validate_bundle", broken_validator)
    assert cli.main(["--config", str(path), "--local-only"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"] == "internal_validation_error"
    assert "private-value" not in captured.out + captured.err
