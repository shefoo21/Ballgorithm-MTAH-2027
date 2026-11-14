"""Explicit user-run CLI; never prints private paths, diagnostics or raw errors."""

import argparse

from mtah.local.config import LocalError, load_local_config
from mtah.local.errors import LocalFailure, call, classify, fixed_details
from mtah.local.runner import run_local


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default messages can echo private paths or mistyped arguments.
        self.exit(2, "Local inference failed: configuration/invalid_arguments\n")


def main(argv=None):
    parser = _PrivateArgumentParser(
        prog="python -m mtah.local",
        description="Local-only tactical inference; no GT or video review",
    )
    parser.add_argument("--config", required=True, help="Explicit private local TOML configuration")
    parser.add_argument("--run-name", required=True, help="New output subdirectory name")
    parser.add_argument(
        "--local-only",
        required=True,
        action="store_true",
        help="Keep all inputs/outputs/reports local",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Fixed local stage/error output; require rules mode and a new run directory",
    )
    parser.add_argument(
        "--verify-repeat",
        action="store_true",
        help="Repeat inference and compare CSV bytes and aggregates",
    )
    args = parser.parse_args(argv)
    try:
        config = call("configuration", load_local_config, args.config)
        if args.diagnose and config.mode != "rules":
            raise LocalFailure("configuration", "diagnostics_require_rules_mode")
        run_local(config, args.run_name, verify_repeat=args.verify_repeat)
    except (Exception, KeyboardInterrupt) as error:
        stage, code = fixed_details(classify("pipeline", error))
        print(f"Local inference failed: {stage}/{code}")
        return 130 if code == "interrupted" else 1 if isinstance(error, LocalError) else 2
    if args.diagnose:
        print("Local inference complete: complete/ok")
        return 0
    print(
        "Local inference complete. Reports remain local; "
        "run the official submission format check locally."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
