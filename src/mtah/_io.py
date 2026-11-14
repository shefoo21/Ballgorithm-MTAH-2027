"""Explicit read-only file boundary; no discovery or environment fallback."""

from pathlib import Path


def local_path(path: str | Path) -> Path:
    """Reject explicit UNC/device paths lexically, before any filesystem operation.

    This does not detect mapped network drives or links; callers must select ordinary
    local files. It is a guard against explicit remote inputs, not an OS sandbox.
    """
    if str(path).replace("\\", "/").startswith("//"):
        raise ValueError("Network and device paths are not supported")
    return Path(path)


def open_text(path: Path):
    return local_path(path).open("r", encoding="utf-8-sig", newline="")


def open_binary(path: Path):
    return local_path(path).open("rb")


def stat_file(path: Path):
    return local_path(path).stat()
