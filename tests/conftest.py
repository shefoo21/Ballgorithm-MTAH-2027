"""Invented fixtures only. Never discover or open competition assets."""

import importlib
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def synthetic_input_boundary(tmp_path, monkeypatch):
    """Deny package input access outside this test's temporary directory."""
    try:
        boundary = importlib.import_module("mtah._io")
    except ModuleNotFoundError:
        return  # Allows the initial test-first red run before implementation exists.

    def guard(original):
        def guarded(path, *args, **kwargs):
            candidate = Path(path).absolute()
            assert candidate.is_relative_to(tmp_path), "Non-synthetic input access denied"
            assert candidate.resolve().is_relative_to(tmp_path.resolve()), "Link escape denied"
            return original(path, *args, **kwargs)

        return guarded

    for name in ("open_text", "open_binary", "stat_file"):
        monkeypatch.setattr(boundary, name, guard(getattr(boundary, name)))


@pytest.fixture
def synthetic_bundle(tmp_path):
    """Three toy frames, two invented slots, identity homography, one event."""
    root = tmp_path / "invented"
    root.mkdir()
    (root / "tracking.xml").write_text(
        '<EPTS><Team id="toy-home"/><Team id="toy-away"/>'
        '<Player id="slot-1" teamId="toy-home"/>'
        '<Player id="slot-2" teamId="toy-away"/></EPTS>',
        encoding="utf-8",
    )
    (root / "tracking.txt").write_text(
        "1:0.1,0.2,1;0.8,0.7,2:0.12,0.2,1\n"
        "2:NaN,NaN,NaN;0.7,0.7,2:NaN,NaN,NaN\n"
        "3:0.2,0.3,1;0.6,0.5,2:1.1,0.5,3\n",
        encoding="utf-8",
    )
    (root / "homography.csv").write_text(
        "frame,h00,h01,h02,h10,h11,h12,h20,h21,h22,reprojection_error,valid\n"
        "0,1,0,0,0,1,0,0,0,1,0,1\n"
        "1,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,0\n"
        "2,1,0,0,0,1,0,0,0,1,0.2,1\n",
        encoding="utf-8",
    )
    (root / "events.xml").write_text(
        "<file><ALL_INSTANCES><instance><start>0.04</start><end>0.12</end>"
        "<code>TOY PHASE</code><label><group>Team</group><text>N/A</text></label>"
        "</instance></ALL_INSTANCES></file>",
        encoding="utf-8",
    )
    (root / "toy.mp4").write_bytes(b"synthetic placeholder; never decode")
    config = tmp_path / "toy.toml"
    config.write_text(
        "schema_version = 1\n[sources.tactical]\nframe_count = 3\ntrack_slots = 2\n"
        "fps = 25\nevent_count = 1\n[sources.tactical.assets]\n"
        'video = "invented/toy.mp4"\natd_meta = "invented/tracking.xml"\n'
        'atd_raw = "invented/tracking.txt"\nhomography = "invented/homography.csv"\n'
        'smart_tagging = "invented/events.xml"\n',
        encoding="utf-8",
    )
    return root, config


@pytest.fixture
def snapshot():
    def take(root: Path):
        return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}

    return take
