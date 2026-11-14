"""Stream text/CSV checks; parse XML safely; never decode video or repair inputs."""

import csv
import math
import re
import stat
from collections import Counter
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from mtah import _io
from mtah.config import ConfigError, SourceConfig, ValidationConfig
from mtah.tracking import parse_atd_line
from mtah.validation.report import CheckResult, ValidationReport

HOMOGRAPHY_HEADER = (
    "frame",
    "h00",
    "h01",
    "h02",
    "h10",
    "h11",
    "h12",
    "h20",
    "h21",
    "h22",
    "reprojection_error",
    "valid",
)

# Exact read_csv defaults in pandas 2.3, used by the official loader. Apply only to
# valid=0 numeric cells; do not normalize arbitrary tokens, frame IDs or valid flags.
# https://pandas.pydata.org/pandas-docs/version/2.3/reference/api/pandas.read_csv.html
_UNAVAILABLE_NA_TOKENS = frozenset(
    (
        "",
        "#N/A",
        "#N/A N/A",
        "#NA",
        "-1.#IND",
        "-1.#QNAN",
        "-NaN",
        "-nan",
        "1.#IND",
        "1.#QNAN",
        "<NA>",
        "N/A",
        "NA",
        "NULL",
        "NaN",
        "None",
        "n/a",
        "nan",
        "null",
    )
)


def _xml(path: Path):
    with _io.open_binary(path) as handle:
        tree = ElementTree.parse(
            handle, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    # Normalize namespace prefixes for equivalent EPTS/SportsCode documents.
    for element in tree.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    return tree


def _metadata(path: Path, source: SourceConfig, issues: Counter) -> int:
    tree = _xml(path)
    team_ids = [element.get("id") for element in tree.iter("Team")]
    if len(team_ids) != 2 or len(set(team_ids)) != 2 or not all(team_ids):
        issues["team_count"] += 1
    players = list(tree.iter("Player"))
    if len(players) != source.track_slots:
        issues["slot_count"] += 1
    for player in players:
        if not player.get("teamId") or player.get("teamId") not in team_ids:
            issues["team_reference"] += 1
    return len(players)


def _tracking(path: Path, source: SourceConfig, issues: Counter) -> int:
    rows = 0
    with _io.open_text(path) as handle:
        for index, line in enumerate(handle):
            rows += 1
            try:
                frame = parse_atd_line(line, expected_slots=source.track_slots)
            except ValueError:
                issues["invalid_record"] += 1
                continue
            if frame.video_frame != index:
                issues["frame_sequence"] += 1
    if rows != source.frame_count:
        issues["row_count"] += 1
    return rows


def _singular(matrix: tuple[float, ...]) -> bool:
    # Scale first: homographies have arbitrary scale. Avoid overflowing the determinant.
    scale = max(abs(value) for value in matrix)
    if scale == 0:
        return True
    a, b, c, d, e, f, g, h, i = (value / scale for value in matrix)
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g) == 0


def _reject(issues: Counter, rejections: Counter | None, reason: str, issue="invalid_record"):
    issues[issue] += 1
    if rejections is not None:
        rejections[reason] += 1


def _homography_record(
    row: list[str], index: int, issues: Counter, rejections: Counter | None
) -> bool:
    """Return whether this is an accepted unavailable row; count the first rejection.

    Categories are fixed strings only. Preserve validation order: sequence checking may
    precede a separate record failure, and numeric parsing precedes semantic checks.
    """
    if len(row) != 12:
        _reject(issues, rejections, "malformed_row_width")
        return False
    try:
        if re.fullmatch(r"[0-9]+", row[0]) is None:
            raise ValueError
        in_sequence = int(row[0]) == index
    except (ValueError, OverflowError):
        _reject(issues, rejections, "invalid_frame_index")
        return False
    if not in_sequence:
        _reject(issues, rejections, "out_of_sequence_frame", "frame_sequence")
    if row[11] not in ("0", "1"):
        _reject(issues, rejections, "invalid_valid_flag")
        return False
    unavailable = row[11] == "0"
    try:
        matrix = tuple(
            math.nan if unavailable and value in _UNAVAILABLE_NA_TOKENS else float(value)
            for value in row[1:10]
        )
    except (ValueError, OverflowError):
        _reject(issues, rejections, "malformed_matrix_numeric_cell")
        return False
    try:
        error = math.nan if unavailable and row[10] in _UNAVAILABLE_NA_TOKENS else float(row[10])
    except (ValueError, OverflowError):
        _reject(issues, rejections, "malformed_reprojection_error_numeric_cell")
        return False
    if not unavailable:
        if not all(math.isfinite(value) for value in matrix):
            _reject(issues, rejections, "nonfinite_valid_matrix")
        elif not math.isfinite(error):
            _reject(issues, rejections, "nonfinite_valid_reprojection_error")
        elif error < 0:
            _reject(issues, rejections, "negative_reprojection_error")
        elif _singular(matrix):
            _reject(issues, rejections, "noninvertible_matrix", "singular_matrix")
        return False
    if not all(math.isnan(value) for value in matrix):
        reason = (
            "finite_values_on_unavailable_matrix"
            if any(math.isfinite(value) for value in matrix)
            else "infinite_values_on_unavailable_matrix"
        )
        _reject(issues, rejections, reason)
        return False
    if math.isinf(error):
        _reject(issues, rejections, "infinite_unavailable_reprojection_error")
        return False
    if not math.isnan(error) and error < 0:
        _reject(issues, rejections, "negative_reprojection_error")
        return False
    return in_sequence


def _homography(
    path: Path, source: SourceConfig, issues: Counter, rejections: Counter | None = None
) -> tuple[int, int]:
    rows = 0
    unavailable_rows = 0
    with _io.open_text(path) as handle:
        reader = csv.reader(handle, strict=True)
        if tuple(next(reader, ())) != HOMOGRAPHY_HEADER:
            issues["header"] += 1
            return rows, unavailable_rows
        for index, row in enumerate(reader):
            rows += 1
            unavailable_rows += _homography_record(row, index, issues, rejections)
    if rows != source.frame_count:
        issues["row_count"] += 1
    return rows, unavailable_rows


def _events(path: Path, source: SourceConfig, issues: Counter) -> int:
    tree = _xml(path)
    root = tree.getroot()
    containers = root.findall("ALL_INSTANCES")
    if root.tag != "file" or len(containers) != 1:
        issues["xml_structure"] += 1
        return 0
    events = list(containers[0])
    if any(event.tag != "instance" for event in events) or len(list(tree.iter("instance"))) != len(
        events
    ):
        issues["xml_structure"] += 1
        return 0
    count = 0
    for event in events:
        count += 1
        try:
            start = float(event.findtext("start", ""))
            end = float(event.findtext("end", ""))
            if not (math.isfinite(start) and math.isfinite(end)):
                raise ValueError
            if not 0 <= start < end <= source.frame_count / source.fps:
                raise ValueError
        except (ValueError, OverflowError):
            issues["invalid_interval"] += 1
        if not (event.findtext("code") or "").strip():
            issues["missing_code"] += 1
        # Overlaps, N/A teams and unfamiliar tag values are legitimate evidence.
        # Do not interpret tags as ground truth or assign possession here.
    if source.event_count is not None and count != source.event_count:
        issues["event_count"] += 1
    return count


_VALIDATORS = {
    "atd_meta": _metadata,
    "atd_raw": _tracking,
    "smart_tagging": _events,
}


def _check(source: SourceConfig, kind: str, *, diagnose: bool = False) -> CheckResult:
    issues: Counter[str] = Counter()
    rejections = Counter() if diagnose and kind == "homography" else None
    rows = None
    unavailable_rows = None
    path = source.assets[kind]
    status = "present_unverified" if kind == "video" else "passed"
    try:
        info = _io.stat_file(path)
        if not stat.S_ISREG(info.st_mode):
            issues["not_regular_file"] += 1
        elif info.st_size == 0:
            issues["empty_file"] += 1
        elif kind == "homography":
            rows, unavailable_rows = _homography(path, source, issues, rejections)
        elif kind != "video":
            rows = _VALIDATORS[kind](path, source, issues)
    except FileNotFoundError:
        issues["missing_file"] += 1
    except DefusedXmlException:
        issues["unsafe_xml"] += 1
    except ParseError:
        issues["invalid_xml"] += 1
    except csv.Error:
        issues["invalid_csv"] += 1
    except (OSError, UnicodeError, LookupError):
        issues["unreadable_file"] += 1
    if rejections is not None:
        # These checks happen outside the per-record classifier, including aborted scans.
        for issue, reason in (
            ("header", "invalid_header"),
            ("row_count", "row_count_mismatch"),
            ("invalid_csv", "malformed_csv"),
            ("missing_file", "missing_file"),
            ("not_regular_file", "not_regular_file"),
            ("empty_file", "empty_file"),
            ("unreadable_file", "unreadable_file"),
        ):
            if issues[issue]:
                rejections[reason] += issues[issue]
    return CheckResult(
        asset=f"{source.name}.{kind}",
        status="failed" if issues else status,
        rows=rows,
        issues=tuple(sorted(issues.items())),
        unavailable_rows=unavailable_rows,
        rejection_counts=tuple(sorted(rejections.items())) if rejections is not None else None,
        scan_complete=(rows is not None and "header" not in issues) if diagnose else None,
    )


def validate_bundle(config: ValidationConfig) -> ValidationReport:
    """Validate only explicitly configured paths. Never discover adjacent files.

    Runtime is O(number of tracking/CSV rows); text/CSV memory is O(track slots).
    XML documents are held in memory. Reports contain no paths or record excerpts,
    but reports derived from actual assets must still remain local.
    """
    checks = []
    for source in config.sources:
        for kind in ("video", "atd_meta", "atd_raw", "homography", "smart_tagging"):
            if kind in source.assets:
                checks.append(_check(source, kind))
    return ValidationReport(tuple(checks))


def diagnose_homography(config: ValidationConfig, source_name: str) -> ValidationReport:
    """Run the same checks for one source's homography, with aggregate branch counts.

    Called independently by the user. Other configured assets are never opened/statted.
    No paths, rows, frame IDs, tokens, matrices or error values enter the output.
    """
    source = next((item for item in config.sources if item.name == source_name), None)
    if source is None:
        raise ConfigError("Requested source is not configured")
    return ValidationReport((_check(source, "homography", diagnose=True),), scope="homography_only")
