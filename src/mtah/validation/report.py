"""Deterministic reports containing logical asset names and issue counts only."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    asset: str
    status: str
    rows: int | None
    issues: tuple[tuple[str, int], ...] = ()
    unavailable_rows: int | None = None
    rejection_counts: tuple[tuple[str, int], ...] | None = None
    scan_complete: bool | None = None

    def to_dict(self) -> dict:
        result = {
            "asset": self.asset,
            "status": self.status,
            "rows": self.rows,
            "issues": dict(self.issues),
        }
        if self.unavailable_rows is not None:
            result["unavailable_rows"] = self.unavailable_rows
        if self.rejection_counts is not None:
            result["rejection_counts"] = dict(self.rejection_counts)
            result["scan_complete"] = self.scan_complete
        return result


@dataclass(frozen=True)
class ValidationReport:
    checks: tuple[CheckResult, ...]
    scope: str = "structural_only_videos_unverified"

    @property
    def ok(self) -> bool:
        return all(check.status != "failed" for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "ok": self.ok,
            "scope": self.scope,
            "checks": [check.to_dict() for check in self.checks],
        }
