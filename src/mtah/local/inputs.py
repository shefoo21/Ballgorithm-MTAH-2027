"""Explicit read-only adapters; existing strict structural rules are reused unchanged."""

import csv
import math
import stat
from collections import Counter

from mtah import _io
from mtah.features import FeatureInput, HomographyQuality, TagInterval
from mtah.local.config import MAX_LINE_CHARS, MAX_XML_BYTES, LocalError
from mtah.local.errors import guarded
from mtah.tracking import parse_atd_line
from mtah.validation.bundle import HOMOGRAPHY_HEADER, _homography_record, _xml


def _bounded_xml(path):
    info = _io.stat_file(path)
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_XML_BYTES:
        raise LocalError("invalid_xml_size_or_type")
    return _xml(path)


@guarded("metadata")
def load_slot_teams(config):
    try:
        tree = _bounded_xml(config.assets["metadata"])
        teams = [t.get("id") for t in tree.iter("Team")]
        if len(teams) != 2 or set(teams) != {config.home_id, config.away_id}:
            raise LocalError("metadata_team_mismatch")
        players = list(tree.iter("Player"))
        if len(players) != config.track_slots:
            raise LocalError("metadata_slot_count")
        mapping = {config.home_id: "H", config.away_id: "A"}
        if any(p.get("teamId") not in mapping for p in players):
            raise LocalError("metadata_team_reference")
        return tuple(mapping[p.get("teamId")] for p in players)
    except LocalError:
        raise
    except Exception:
        raise LocalError("invalid_metadata") from None


@guarded("automatic_tags")
def load_tags(config):
    if "smart_tagging" not in config.assets:
        return None
    try:
        root = _bounded_xml(config.assets["smart_tagging"]).getroot()
        containers = root.findall("ALL_INSTANCES")
        if root.tag != "file" or len(containers) != 1:
            raise LocalError("invalid_tag_structure")
        events = list(containers[0])
        if any(e.tag != "instance" for e in events) or len(list(root.iter("instance"))) != len(
            events
        ):
            raise LocalError("invalid_tag_structure")
        mapping = {config.tag_home.strip().casefold(): "H", config.tag_away.strip().casefold(): "A"}
        tags = []
        for event in events:
            start, stop = float(event.findtext("start", "")), float(event.findtext("end", ""))
            if not (
                math.isfinite(start)
                and math.isfinite(stop)
                and 0 <= start < stop <= config.frame_count / config.features.fps
            ):
                raise LocalError("invalid_tag_interval")
            names = {
                (label.findtext("text") or "").strip().casefold()
                for label in event.findall("label")
                if (label.findtext("group") or "").strip().casefold() == "team"
            }
            team = mapping.get(next(iter(names))) if len(names) == 1 else None
            tags.append(
                TagInterval.from_seconds(
                    start, stop, event.findtext("code", ""), team, fps=config.features.fps
                )
            )
        return tuple(tags)
    except LocalError:
        raise
    except Exception:
        raise LocalError("invalid_automatic_tags") from None


def _lines(stream):
    while True:
        line = stream.readline(MAX_LINE_CHARS + 1)
        if not line:
            break
        if len(line) > MAX_LINE_CHARS:
            raise LocalError("input_line_too_long")
        yield line


@guarded("homography_input", generator=True)
def _qualities(config):
    with _io.open_text(config.assets["homography"]) as stream:
        reader = csv.reader(_lines(stream), strict=True)
        if tuple(next(reader, ())) != HOMOGRAPHY_HEADER:
            raise LocalError("homography_header")
        rows = 0
        for index, row in enumerate(reader):
            issues = Counter()
            _homography_record(row, index, issues, None)
            if issues or index >= config.frame_count:
                raise LocalError("invalid_homography_record")
            valid = row[11] == "1"
            # Strict validation already established this row's valid/NaN contract.
            error = float(row[10]) if valid else math.nan
            if not valid:
                try:
                    error = float(row[10])
                except ValueError:
                    pass  # A documented unavailable token already passed strict validation.
            yield HomographyQuality(index, valid, error)
            rows += 1
        if rows != config.frame_count:
            raise LocalError("homography_row_count")


@guarded("atd_input", generator=True)
def iter_inputs(config):
    """Reject missing records; missing observations remain NaNs without interpolation."""
    quality = _qualities(config) if "homography" in config.assets else None
    try:
        rows = 0
        with _io.open_text(config.assets["tracking"]) as stream:
            for index, line in enumerate(_lines(stream)):
                frame = parse_atd_line(line, expected_slots=config.track_slots)
                if frame.video_frame != index or index >= config.frame_count:
                    raise LocalError("tracking_frame_sequence")
                q = next(quality, None) if quality is not None else None
                if quality is not None and q is None:
                    raise LocalError("homography_row_count")
                yield FeatureInput(frame, q)
                rows += 1
        if rows != config.frame_count:
            raise LocalError("tracking_row_count")
        if quality is not None and next(quality, None) is not None:
            raise LocalError("homography_row_count")
    except LocalError:
        raise
    except Exception:
        raise LocalError("invalid_tactical_input") from None
    finally:
        if quality is not None:
            quality.close()
