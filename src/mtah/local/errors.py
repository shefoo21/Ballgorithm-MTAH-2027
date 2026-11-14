"""Fixed, allowlisted local failure diagnostics. Never stringify an exception payload."""

import csv
import errno
import tomllib
from functools import wraps

from mtah.features import FeatureError
from mtah.inference import InferenceError


class LocalError(ValueError):
    """Backward-compatible local operation error base."""


STAGES = frozenset(
    {
        "configuration",
        "asset_checks",
        "output_setup",
        "metadata",
        "automatic_tags",
        "atd_input",
        "homography_input",
        "feature_extraction",
        "rule_inference",
        "submission_writing",
        "repeat_verification",
        "finalization",
        "pipeline",
    }
)
COMMON_CODES = frozenset(
    {
        "not_found",
        "permission_denied",
        "already_exists",
        "not_a_directory",
        "is_a_directory",
        "storage_full",
        "io_error",
        "invalid_encoding",
        "resource_exhausted",
        "interrupted",
        "unexpected_error",
    }
)
# Only fixed codes written by the adapter are eligible for output. A free-form LocalError
# from a dependency or extension is not trusted, even though it shares the exception class.
_GROUPS = {
    "configuration": "invalid_diagnostic_settings invalid_inference_mode "
    "invalid_configuration_keys "
    "invalid_configuration_value configuration_too_large invalid_profile_or_schema "
    "ambiguous_team_mapping unknown_tag_team_cannot_be_assigned period_outside_timeline "
    "phase1_contract_mismatch invalid_parameter_provenance invalid_configuration "
    "invalid_run_request "
    "diagnostics_require_rules_mode invalid_toml invalid_arguments",
    "asset_checks": "roots_must_be_absolute root_must_be_directory "
    "output_overlaps_dataset "
    "input_escapes_dataset assets_must_be_relative invalid_local_path",
    "metadata": "metadata_team_mismatch metadata_slot_count "
    "metadata_team_reference invalid_metadata",
    "automatic_tags": "invalid_tag_structure invalid_tag_interval invalid_automatic_tags",
    "atd_input": "tracking_frame_sequence tracking_row_count "
    "invalid_tactical_input invalid_atd_record",
    "homography_input": "homography_header invalid_homography_record "
    "homography_row_count invalid_csv",
    "feature_extraction": "invalid_features",
    "rule_inference": "invalid_inference",
    "submission_writing": "invalid_submission",
    "repeat_verification": "non_deterministic_replay",
    "finalization": "invalid_report",
}
_LOCAL_CODES = {code: stage for stage, codes in _GROUPS.items() for code in codes.split()}
_CONTEXT_CODES = frozenset(
    {
        "invalid_xml_size_or_type",
        "input_line_too_long",
        "input_must_be_regular_file",
        "inputs_changed_during_run",
    }
)
_KNOWN_CODES = frozenset(_LOCAL_CODES) | _CONTEXT_CODES | COMMON_CODES


class LocalFailure(LocalError):
    """Display fields contain static identifiers; Python's in-memory chain is never printed."""

    def __init__(self, stage, code):
        if (
            type(stage) is not str
            or stage not in STAGES
            or type(code) is not str
            or code not in _KNOWN_CODES
        ):
            stage, code = "pipeline", "unexpected_error"
        self.stage, self.code = stage, code
        super().__init__(code)


def fixed_details(failure):
    """Validate again at the print boundary, including objects altered after construction."""
    if type(failure) is LocalFailure:
        stage, code = failure.stage, failure.code
        if type(stage) is str and stage in STAGES and type(code) is str and code in _KNOWN_CODES:
            return stage, code
    return "pipeline", "unexpected_error"


def _local_code(error):
    if type(error) is LocalError and len(error.args) == 1 and type(error.args[0]) is str:
        return error.args[0]
    return None


def classify(stage, error):
    """Inspect at most eight exception types; never repr/str/format an exception or path."""
    chain = []
    current = error
    for _ in range(8):
        if current is None or any(current is previous for previous in chain):
            break
        chain.append(current)
        if type(current) is LocalFailure:
            return LocalFailure(*fixed_details(current))
        # Follow only known exception-collapsing boundaries. An unrelated exception
        # being handled by a caller must not override a new failure's classification.
        wrapped = _local_code(current) in (
            "invalid_tactical_input",
            "invalid_configuration",
            "invalid_metadata",
            "invalid_automatic_tags",
        ) or (
            type(current) is InferenceError
            and len(current.args) == 1
            and type(current.args[0]) is str
            and current.args[0] == "Could not create a new submission file"
        )
        context = current.__context__
        current = context if wrapped else None
    for item in chain:
        if isinstance(item, KeyboardInterrupt):
            return LocalFailure(stage, "interrupted")
        if isinstance(item, MemoryError):
            return LocalFailure(stage, "resource_exhausted")
        if isinstance(item, OSError):
            code = "io_error"
            for kind, name in (
                (FileNotFoundError, "not_found"),
                (PermissionError, "permission_denied"),
                (FileExistsError, "already_exists"),
                (NotADirectoryError, "not_a_directory"),
                (IsADirectoryError, "is_a_directory"),
            ):
                if isinstance(item, kind):
                    code = name
                    break
            if item.errno == errno.ENOSPC:
                code = "storage_full"
            return LocalFailure(stage, code)
        if isinstance(item, UnicodeError):
            return LocalFailure(stage, "invalid_encoding")
        if stage == "configuration" and isinstance(item, tomllib.TOMLDecodeError):
            return LocalFailure(stage, "invalid_toml")
        if stage == "homography_input" and isinstance(item, csv.Error):
            return LocalFailure(stage, "invalid_csv")
    # Preserve expected adapter failures before inspecting broader ValueError bases.
    code = _local_code(error)
    if code is not None:
        if code in _CONTEXT_CODES:
            return LocalFailure(stage, code)
        if code in _LOCAL_CODES and code not in ("invalid_tactical_input", "invalid_configuration"):
            return LocalFailure(_LOCAL_CODES[code], code)
    for item in chain:
        if stage == "feature_extraction" and isinstance(item, FeatureError):
            return LocalFailure(stage, "invalid_features")
        if isinstance(item, InferenceError) and stage in (
            "rule_inference",
            "submission_writing",
        ):
            return LocalFailure(
                stage,
                {
                    "rule_inference": "invalid_inference",
                    "submission_writing": "invalid_submission",
                }[stage],
            )
        if type(item) is not LocalError and isinstance(item, ValueError):
            codes = {
                "configuration": "invalid_configuration",
                "asset_checks": "invalid_local_path",
                "atd_input": "invalid_atd_record",
                "finalization": "invalid_report",
            }
            if stage in codes:
                return LocalFailure(stage, codes[stage])
    if code in ("invalid_tactical_input", "invalid_configuration"):
        return LocalFailure(_LOCAL_CODES[code], code)
    return LocalFailure(stage, "unexpected_error")


def call(stage, function, /, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except LocalFailure:
        raise
    except (Exception, KeyboardInterrupt) as error:
        raise classify(stage, error) from None


def iterate(stage, factory, /, *args, **kwargs):
    """Tag next()/generator failures at their producer, before the CSV consumer catches them."""
    try:
        yield from factory(*args, **kwargs)
    except LocalFailure:
        raise
    except (Exception, KeyboardInterrupt) as error:
        raise classify(stage, error) from None


def guarded(stage, *, generator=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            return (iterate if generator else call)(stage, function, *args, **kwargs)

        return wrapped

    return decorate
