import importlib
import json

import pytest


def validate(path):
    try:
        config = importlib.import_module("mtah.config")
        validation = importlib.import_module("mtah.validation")
    except ModuleNotFoundError:
        pytest.fail("Validation modules have not been implemented")
    return validation.validate_bundle(config.load_config(path)).to_dict()


def check(report, asset):
    return next(item for item in report["checks"] if item["asset"] == asset)


def test_valid_bundle_is_read_only_and_video_is_explicitly_unverified(synthetic_bundle, snapshot):
    root, path = synthetic_bundle
    before = snapshot(root)
    report = validate(path)
    assert report["ok"]
    assert len(report["checks"]) == 5
    assert check(report, "tactical.video")["status"] == "present_unverified"
    assert check(report, "tactical.atd_raw")["rows"] == 3
    assert check(report, "tactical.smart_tagging")["rows"] == 1
    assert snapshot(root) == before
    assert str(root) not in json.dumps(report)


@pytest.mark.parametrize(
    "filename", ["tracking.txt", "tracking.xml", "homography.csv", "events.xml", "toy.mp4"]
)
def test_missing_asset_does_not_abort_other_checks(synthetic_bundle, filename):
    root, path = synthetic_bundle
    (root / filename).unlink()
    report = validate(path)
    assert not report["ok"]
    assert len(report["checks"]) == 5
    assert sum(item["status"] == "failed" for item in report["checks"]) == 1
    assert "missing_file" in json.dumps(report)


@pytest.mark.parametrize(
    "text,code",
    [
        ("1:0,0,0;0,0,0:0,0,0\n1:0,0,0;0,0,0:0,0,0\n3:0,0,0;0,0,0:0,0,0\n", "frame_sequence"),
        ("1:0,0,0;0,0,0:0,0,0\n", "row_count"),
        ("\n\n\n", "invalid_record"),
        ("secret\nsecret\nsecret\n", "invalid_record"),
    ],
)
def test_tracking_errors_are_aggregated_without_record_excerpts(synthetic_bundle, text, code):
    root, path = synthetic_bundle
    (root / "tracking.txt").write_text(text, encoding="utf-8")
    report = validate(path)
    assert not report["ok"]
    assert code in check(report, "tactical.atd_raw")["issues"]
    assert "secret" not in json.dumps(report)


def test_invalid_encoding_is_sanitized(synthetic_bundle):
    root, path = synthetic_bundle
    (root / "tracking.txt").write_bytes(b"\xffprivate-value")
    report = validate(path)
    assert "unreadable_file" in check(report, "tactical.atd_raw")["issues"]
    assert "private-value" not in json.dumps(report)


@pytest.mark.parametrize(
    "xml,code",
    [
        ('<EPTS><Team id="a"/><Team id="b"/><Player teamId="a"/></EPTS>', "slot_count"),
        (
            '<EPTS><Team id="a"/><Team id="b"/><Player teamId="z"/><Player teamId="b"/></EPTS>',
            "team_reference",
        ),
        ('<EPTS><Team id="a"/><Player teamId="a"/><Player teamId="a"/></EPTS>', "team_count"),
        (
            '<EPTS><Team id="a"/><Team id="a"/><Player teamId="a"/><Player teamId="a"/></EPTS>',
            "team_count",
        ),
        ("<EPTS>private-value", "invalid_xml"),
        ('<!DOCTYPE a [<!ENTITY x SYSTEM "file:///never-read-private">]><a>&x;</a>', "unsafe_xml"),
    ],
)
def test_metadata_structure_and_safe_xml(synthetic_bundle, xml, code):
    root, path = synthetic_bundle
    (root / "tracking.xml").write_text(xml, encoding="utf-8")
    report = validate(path)
    assert code in check(report, "tactical.atd_meta")["issues"]
    assert not report["ok"]
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize(
    "old,new,code",
    [
        ("frame,h00", "wrong,h00", "header"),
        ("2,1,0,0,0,1,0,0,0,1,0.2,1", "1,1,0,0,0,1,0,0,0,1,0.2,1", "frame_sequence"),
        ("0,1,0,0,0,1,0,0,0,1,0,1", "0,1,0,0,0,1,0,0,0,1,0,2", "invalid_record"),
        ("0,1,0,0,0,1,0,0,0,1,0,1", "0,1,0,0,0,1,0,0,0,0,0,1", "singular_matrix"),
        ("0,1,0,0,0,1,0,0,0,1,0,1", "0,inf,0,0,0,1,0,0,0,1,0,1", "invalid_record"),
        ("0,1,0,0,0,1,0,0,0,1,0,1", "0,1,0,0,0,1,0,0,0,1,-1,1", "invalid_record"),
        ("0,1,0,0,0,1,0,0,0,1,0,1", "0,1,0,0,0,1,0,0,0,1,0,0", "invalid_record"),
        ("0,1,0,0,0,1,0,0,0,1,0,1", "0,1,0,0,0,1,0,0,0,1,0,1,secret", "invalid_record"),
    ],
)
def test_homography_checks(synthetic_bundle, old, new, code):
    root, path = synthetic_bundle
    target = root / "homography.csv"
    target.write_text(target.read_text().replace(old, new), encoding="utf-8")
    report = validate(path)
    assert not report["ok"]
    assert code in check(report, "tactical.homography")["issues"]
    assert "secret" not in json.dumps(report)


@pytest.mark.parametrize(
    "start,end", [("-1", "0.1"), ("0.1", "0.04"), ("nan", "0.12"), ("0.04", "0.13")]
)
def test_event_intervals_have_explicit_video_timebase(synthetic_bundle, start, end):
    root, path = synthetic_bundle
    target = root / "events.xml"
    target.write_text(target.read_text().replace("0.04", start).replace("0.12", end))
    report = validate(path)
    assert "invalid_interval" in check(report, "tactical.smart_tagging")["issues"]


def test_empty_video_is_not_reported_as_present(synthetic_bundle):
    root, path = synthetic_bundle
    (root / "toy.mp4").write_bytes(b"")
    report = validate(path)
    assert "empty_file" in check(report, "tactical.video")["issues"]


def test_unknown_xml_encoding_is_reported_without_a_traceback(synthetic_bundle):
    root, path = synthetic_bundle
    (root / "tracking.xml").write_bytes(
        b'<?xml version="1.0" encoding="private-unknown-encoding"?><EPTS/>'
    )
    report = validate(path)
    assert not report["ok"]
    assert "unreadable_file" in check(report, "tactical.atd_meta")["issues"]
    assert "private-unknown-encoding" not in json.dumps(report)


@pytest.mark.parametrize(
    "xml",
    [
        "<unrelated/>",
        "<file/>",
        "<EPTS><ALL_INSTANCES/></EPTS>",
        "<file><ALL_INSTANCES/><ALL_INSTANCES/></file>",
        "<file><ALL_INSTANCES><wrapper><instance/></wrapper></ALL_INSTANCES></file>",
        "<file><ALL_INSTANCES/><instance/></file>",
    ],
)
def test_wrong_smart_tagging_document_cannot_pass_without_expected_count(synthetic_bundle, xml):
    root, path = synthetic_bundle
    path.write_text(path.read_text().replace("event_count = 1\n", ""), encoding="utf-8")
    (root / "events.xml").write_text(xml, encoding="utf-8")
    report = validate(path)
    assert not report["ok"]
    assert "xml_structure" in check(report, "tactical.smart_tagging")["issues"]


@pytest.mark.parametrize("expected", ["", "event_count = 0\n"])
def test_valid_empty_sports_code_container_is_explicitly_supported(synthetic_bundle, expected):
    root, path = synthetic_bundle
    path.write_text(path.read_text().replace("event_count = 1\n", expected), encoding="utf-8")
    (root / "events.xml").write_text("<file><ALL_INSTANCES/></file>", encoding="utf-8")
    assert validate(path)["ok"]


def test_video_content_is_never_opened(synthetic_bundle, monkeypatch):
    from mtah import _io

    root, path = synthetic_bundle
    binary, text = _io.open_binary, _io.open_text

    def guard(original):
        def checked(candidate):
            assert candidate != root / "toy.mp4", "Video must only be statted"
            return original(candidate)

        return checked

    monkeypatch.setattr(_io, "open_binary", guard(binary))
    monkeypatch.setattr(_io, "open_text", guard(text))
    assert validate(path)["ok"]


def test_optional_broadcast_has_its_own_counts(synthetic_bundle):
    root, path = synthetic_bundle
    (root / "broadcast.txt").write_text("1:0,0,0:0,0,0\n", encoding="utf-8")
    (root / "broadcast.xml").write_text(
        '<EPTS><Team id="a"/><Team id="b"/><Player teamId="a"/></EPTS>', encoding="utf-8"
    )
    header, row, *_ = (root / "homography.csv").read_text().splitlines()
    (root / "broadcast.csv").write_text(header + "\n" + row + "\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n[sources.broadcast]\nframe_count = 1\ntrack_slots = 1\nfps = 30\n"
            '[sources.broadcast.assets]\nvideo = "invented/toy.mp4"\n'
            'atd_meta = "invented/broadcast.xml"\natd_raw = "invented/broadcast.txt"\n'
            'homography = "invented/broadcast.csv"\n'
        )
    report = validate(path)
    assert report["ok"]
    assert len(report["checks"]) == 9
    assert check(report, "broadcast.atd_raw")["rows"] == 1
