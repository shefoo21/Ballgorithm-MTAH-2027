"""Interpret one saved local report. Never load configs, assets, or validator code."""

import argparse
import json
import stat
from dataclasses import dataclass
from pathlib import Path

from mtah import _io
from mtah.diagnostic_codes import UNKNOWN, advice_for

MAX_REPORT_BYTES = 1024 * 1024
ASSETS = frozenset(
    f"{source}.{kind}"
    for source in ("tactical", "broadcast")
    for kind in ("video", "atd_meta", "atd_raw", "homography", "smart_tagging")
    if source != "broadcast" or kind != "smart_tagging"
)


class ReportError(ValueError):
    """Static, safe error text with no report contents or private paths."""


@dataclass(frozen=True)
class SavedCheck:
    asset: str
    status: str
    issues: tuple[tuple[str, int], ...]
    unavailable_rows: int | None


@dataclass(frozen=True)
class SavedReport:
    ok: bool
    checks: tuple[SavedCheck, ...] = ()
    error: str | None = None


def _invalid():
    raise ReportError(
        "Cannot interpret report: unsupported or inconsistent report format. "
        "Use an unedited schema-version-1 validator report; inspect any mismatch locally."
    )


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def _reject_constant(_value):
    _invalid()


def interpret_report(document: object) -> SavedReport:
    """Validate report structure only; never reevaluate or repair underlying assets."""
    if not isinstance(document, dict):
        _invalid()
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        _invalid()
    if type(document.get("ok")) is not bool:
        _invalid()
    if "error" in document:
        if document["ok"] or type(document["error"]) is not str or "checks" in document:
            _invalid()
        return SavedReport(False, error=document["error"])
    if document.get("scope") != "structural_only_videos_unverified":
        _invalid()
    entries = document.get("checks")
    if not isinstance(entries, list) or not entries:
        _invalid()
    checks = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not {"asset", "status", "rows", "issues"} <= entry.keys():
            _invalid()
        asset, status, rows, issues = (entry[key] for key in ("asset", "status", "rows", "issues"))
        if type(asset) is not str or asset not in ASSETS or asset in seen:
            _invalid()
        seen.add(asset)
        if status not in ("passed", "failed", "present_unverified"):
            _invalid()
        if rows is not None and not _nonnegative_integer(rows):
            _invalid()
        if not isinstance(issues, dict) or any(
            type(code) is not str or not code or not _nonnegative_integer(count) or count == 0
            for code, count in issues.items()
        ):
            _invalid()
        if (status == "failed") != bool(issues):
            _invalid()
        if status != "failed" and (status == "present_unverified") != asset.endswith(".video"):
            _invalid()
        unavailable = entry.get("unavailable_rows")
        if "unavailable_rows" in entry and (
            not asset.endswith(".homography")
            or not _nonnegative_integer(unavailable)
            or rows is None
            or unavailable > rows
        ):
            _invalid()
        checks.append(SavedCheck(asset, status, tuple(sorted(issues.items())), unavailable))
    if document["ok"] != all(check.status != "failed" for check in checks):
        _invalid()
    return SavedReport(document["ok"], tuple(checks))


def read_report(path: str | Path) -> SavedReport:
    try:
        if "://" in str(path):
            raise ValueError
        candidate = _io.local_path(path)
    except (ValueError, TypeError):
        raise ReportError(
            "Choose an ordinary local report file; remote/device paths are rejected."
        ) from None
    try:
        info = _io.stat_file(candidate)
        if not stat.S_ISREG(info.st_mode):
            raise ReportError("Cannot read report: select a regular local JSON file.")
        if info.st_size > MAX_REPORT_BYTES:
            raise ReportError(
                "Cannot interpret report: 1 MiB size limit exceeded. Check selection locally."
            )
        with _io.open_binary(candidate) as handle:
            content = handle.read(MAX_REPORT_BYTES + 1)
        if len(content) > MAX_REPORT_BYTES:
            raise ReportError(
                "Cannot interpret report: 1 MiB size limit exceeded. Check selection locally."
            )
    except OSError:
        raise ReportError(
            "Cannot read report: check its local filename, existence and read permissions."
        ) from None
    try:
        document = json.loads(
            content.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        return interpret_report(document)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, ReportError):
            raise
        raise ReportError(
            "Cannot interpret report: invalid UTF-8 JSON. Select the saved validator JSON, "
            "not console text; preserve the original and investigate locally."
        ) from None


def render_diagnosis(report: SavedReport) -> str:
    lines = [
        "Local validation report diagnosis",
        "This interprets a saved report only; it does not rerun validation "
        "or verify current files.",
        "Keep this output and its source report local. "
        "Causes below are possibilities, not findings.",
        "Issue counts are occurrences, not necessarily distinct rows; "
        "do not sum them as bad frames.",
        "",
    ]
    if report.error is not None:
        advice = {
            "invalid_configuration": (
                "The validator could not load a supported configuration.",
                "Check TOML syntax, required fields, schema version and explicit local paths "
                "in your own editor. The helper never opens that configuration.",
            ),
            "internal_validation_error": (
                "The validator stopped with a sanitized internal error; "
                "asset validity is unresolved.",
                "Check the local installation/version. Reproduce defects with synthetic fixtures "
                "before debugging with an assistant; do not expose real-data tracebacks.",
            ),
        }.get(
            report.error,
            (
                "Unrecognized validator error; the report remains unresolved.",
                "Check the helper/validator version against public documentation locally.",
            ),
        )
        return "\n".join(lines + [advice[0], "Local action: " + advice[1]]) + "\n"
    failures = [check for check in report.checks if check.status == "failed"]
    lines.append(
        f"Report result: FAIL ({len(failures)} failed check(s))."
        if failures
        else "Reported checks passed. A structural report is not a full integrity certificate."
    )
    for check in sorted(failures, key=lambda item: item.asset):
        lines.extend(["", f"Failed check: {check.asset}"])
        for code, count in check.issues:
            advice = advice_for(code, check.asset)
            label = "Unrecognized issue code" if advice is UNKNOWN else code
            lines.extend(
                [
                    f"  {label}: {count} occurrence(s) [{advice.category}]",
                    "    Meaning: " + advice.meaning,
                    "    Possible causes: " + advice.causes,
                    "    Local action: " + advice.action,
                ]
            )
    lines.extend(["", "Expected missing observations and video limits:"])
    for check in sorted(report.checks, key=lambda item: item.asset):
        if check.asset.endswith(".homography"):
            if check.unavailable_rows is None:
                lines.append(
                    f"  {check.asset}: unavailable count was not recorded; do not assume zero."
                )
            else:
                lines.append(
                    f"  {check.asset}: {check.unavailable_rows} expected unavailable homography "
                    "row(s), not a structural error. Separate issues still require attention."
                )
        elif check.asset.endswith(".video"):
            presence = "presence check failed" if check.status == "failed" else "present_unverified"
            lines.append(
                f"  {check.asset}: {presence}. Video content remains unverified; "
                "no decoding, frame-count confirmation or checksum comparison is established."
            )
    lines.extend(
        [
            "  Paired missing ATD coordinates (NaN) are allowed. These reports do not count them; "
            "missing observations alone do not establish a dead-ball state.",
            "",
            "Next: investigate the listed failures locally, preserve original files "
            "and keep validation rules intact. After any justified configuration/export "
            "correction, rerun validation independently and diagnose the new saved report. "
            "Do not upload or paste either output.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explain a saved validation report locally")
    parser.add_argument("--report", required=True, help="Explicit local UTF-8 JSON report path")
    parser.add_argument(
        "--local-only",
        action="store_true",
        required=True,
        help="Acknowledge that the report and diagnosis stay local",
    )
    args = parser.parse_args(argv)
    try:
        report = read_report(args.report)
        diagnosis = render_diagnosis(report)
    except ReportError as error:
        print(str(error))
        return 2
    except Exception:
        # Never expose report values through an unexpected exception/traceback.
        print("Cannot interpret report: internal diagnostic error. Reproduce with synthetic JSON.")
        return 2
    print(diagnosis, end="")
    return 2 if report.error is not None else (0 if report.ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
