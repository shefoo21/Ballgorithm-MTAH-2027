import importlib
from pathlib import Path

import pytest


def config_module():
    try:
        return importlib.import_module("mtah.config")
    except ModuleNotFoundError:
        pytest.fail("Configuration module has not been implemented")


def test_explicit_relative_paths_and_no_asset_access(synthetic_bundle, monkeypatch):
    root, path = synthetic_bundle
    monkeypatch.chdir(root)
    monkeypatch.setenv("MTAH_DATA_DIR", "DO_NOT_USE_ENVIRONMENT")
    config = config_module().load_config(path)
    source = config.sources[0]
    assert source.name == "tactical"
    assert source.assets["atd_raw"] == root / "tracking.txt"
    assert source.frame_count == 3
    # Loading configuration must not require any asset to exist.
    (root / "tracking.txt").unlink()
    assert config_module().load_config(path) == config


@pytest.mark.parametrize(
    "old,new",
    [
        ("schema_version = 1", "schema_version = 2"),
        ("schema_version = 1", "schema_version = true"),
        ("frame_count = 3", "frame_count = 0"),
        ("frame_count = 3", "frame_count = true"),
        ("track_slots = 2", "track_slots = 2.5"),
        ("fps = 25", "fps = nan"),
        ("fps = 25", "fps = 0"),
        ("event_count = 1", "event_count = -1"),
        ("[sources.tactical]", "[sources.private_value]"),
        ("atd_raw =", "atd_raw_typo ="),
        ('"invented/tracking.txt"', '""'),
    ],
)
def test_config_errors_are_strict_and_sanitized(synthetic_bundle, old, new):
    _, path = synthetic_bundle
    path.write_text(path.read_text().replace(old, new), encoding="utf-8")
    m = config_module()
    with pytest.raises(m.ConfigError) as error:
        m.load_config(path)
    assert "private_value" not in str(error.value)
    assert str(path) not in str(error.value)


def test_config_rejects_unknown_root_key(synthetic_bundle):
    _, path = synthetic_bundle
    path.write_text('private_value = "secret"\n' + path.read_text(), encoding="utf-8")
    m = config_module()
    with pytest.raises(m.ConfigError):
        m.load_config(path)


def test_bad_toml_and_missing_config_have_no_path_or_content_leaks(tmp_path):
    path = tmp_path / "private-config.toml"
    m = config_module()
    for content in [None, 'secret = "unterminated']:
        if content is not None:
            path.write_text(content, encoding="utf-8")
        with pytest.raises(m.ConfigError) as error:
            m.load_config(path)
        assert "secret" not in str(error.value)
        assert str(path) not in str(error.value)


def test_config_paths_are_absolute_without_expanding_environment(synthetic_bundle):
    _, path = synthetic_bundle
    path.write_text(path.read_text().replace("invented/tracking.txt", "$SECRET/file.txt"))
    result = config_module().load_config(path)
    assert result.sources[0].assets["atd_raw"] == Path(path.parent / "$SECRET/file.txt")


NETWORK_PATHS = [
    r"\\server.invalid\share\toy.txt",
    "//server.invalid/share/toy.txt",
    r"\\?\UNC\server.invalid\share\toy.txt",
    r"\\.\UNC\server.invalid\share\toy.txt",
    r"\\?\C:\toy.txt",
]


@pytest.mark.parametrize("candidate", NETWORK_PATHS)
def test_network_config_is_rejected_before_any_file_access(candidate, monkeypatch):
    from mtah import _io

    def forbidden_open(_path):
        pytest.fail("Network/device path reached filesystem boundary")

    monkeypatch.setattr(_io, "open_binary", forbidden_open)
    m = config_module()
    with pytest.raises(m.ConfigError):
        m.load_config(candidate)


@pytest.mark.parametrize("candidate", NETWORK_PATHS)
def test_network_asset_is_rejected_lexically(synthetic_bundle, candidate):
    _, path = synthetic_bundle
    path.write_text(
        path.read_text().replace('"invented/tracking.txt"', "'" + candidate + "'"),
        encoding="utf-8",
    )
    m = config_module()
    with pytest.raises(m.ConfigError):
        m.load_config(path)
