"""Explicit local invocation only; no auto-discovery or input writes."""

import argparse
import json

from mtah.config import ConfigError, load_config
from mtah.validation import validate_bundle
from mtah.validation.bundle import diagnose_homography


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local asset validation")
    parser.add_argument("--config", required=True, help="Explicit path to a local TOML config")
    parser.add_argument(
        "--diagnose-homography",
        choices=("tactical", "broadcast"),
        help="Check only this source's homography with aggregate rejection categories",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        required=True,
        help="Acknowledge that inputs and derived reports stay on this machine",
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        report = (
            diagnose_homography(config, args.diagnose_homography)
            if args.diagnose_homography
            else validate_bundle(config)
        )
    except ConfigError:
        print(json.dumps({"schema_version": 1, "ok": False, "error": "invalid_configuration"}))
        return 2
    except Exception:
        # Last-resort privacy boundary: library exceptions may contain input values.
        # Reproduce defects with synthetic fixtures; never print a real-data traceback.
        print(json.dumps({"schema_version": 1, "ok": False, "error": "internal_validation_error"}))
        return 2
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
