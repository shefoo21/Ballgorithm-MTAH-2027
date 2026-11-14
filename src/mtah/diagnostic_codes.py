"""Static explanations of existing validator codes; no validation or file access."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Advice:
    category: str
    meaning: str
    causes: str
    action: str


ISSUES = {
    "missing_file": Advice(
        "File availability",
        "The configured file was not found when validation ran.",
        "A filename/extension mismatch, wrong relative folder, moved file, or incomplete download.",
        "Compare the exact filename with your private configuration locally. Relative paths start "
        "at the configuration's folder. Correct a wrong config path; preserve the original asset.",
    ),
    "not_regular_file": Advice(
        "File availability",
        "The configured path did not identify a regular file.",
        "A directory or special device was selected instead of an asset.",
        "Select the actual local file in your private configuration; do not replace the original.",
    ),
    "empty_file": Advice(
        "File availability",
        "The selected file was empty (zero bytes).",
        "An unfinished download, empty placeholder, or incorrect file selection.",
        "Check the local file size and download completion. Obtain a trusted replacement in a "
        "separate location if needed; retain the original for comparison.",
    ),
    "unreadable_file": Advice(
        "File access",
        "Validation could not read or decode the selected file.",
        "Permissions, an I/O problem, a file lock, unsupported encoding, or the wrong file type.",
        "Check local read permissions, locks and the documented encoding. Use the correct source "
        "export; do not rewrite the original or paste its contents into an assistant.",
    ),
    "header": Advice(
        "Malformed data",
        "The homography CSV header did not match the required columns/order.",
        "Wrong asset, wrong delimiter, altered header, or an unexpected export format.",
        "Compare only in your own editor with the public DATA.md header. Verify the selected "
        "source/export before considering a separate replacement; do not edit the original header.",
    ),
    "invalid_csv": Advice(
        "Malformed data",
        "The CSV parser could not complete the scan.",
        "Broken quoting, a truncated quoted field, or another CSV parsing error.",
        "Check download completion and export format locally. Keep the original unchanged; "
        "use a separate trusted copy to investigate. Partial counts may be unavailable.",
    ),
    "invalid_xml": Advice(
        "Malformed data",
        "The XML was not parseable as a well-formed document.",
        "Truncation, invalid XML syntax, or a non-XML file at the configured path.",
        "Verify the local file type and download completeness. Compare with a separate trusted "
        "copy; do not manually repair competition annotations.",
    ),
    "unsafe_xml": Advice(
        "Unsafe XML",
        "The safe XML parser rejected a DTD or entities.",
        "An export containing forbidden XML declarations or an unintended file.",
        "Confirm the source and documented export format locally. Keep XML protections enabled; "
        "do not enable external entities or alter the original to force a pass.",
    ),
    "xml_structure": Advice(
        "Malformed data",
        "The Smart Tagging document had the wrong container structure.",
        "Unrelated XML, missing/duplicate ALL_INSTANCES, or misplaced instance elements.",
        "Check that smart_tagging points to the SportsCode export with "
        "file/ALL_INSTANCES/instance, "
        "not the ATD metadata. Correct wrong configuration paths only.",
    ),
    "row_count": Advice(
        "Count mismatch",
        "The scanned row total differed from configured frame_count.",
        "Truncation, extra rows, wrong source file, or an incorrect configured count.",
        "Compare the configuration with the public source-specific count and confirm the selected "
        "asset. Tactical and broadcast have separate clocks. Do not pad, drop or duplicate rows.",
    ),
    "singular_matrix": Advice(
        "Malformed data",
        "A valid=1 homography was detected as singular by the validator.",
        "A degenerate matrix or damaged/altered numeric values.",
        "Confirm the correct source export locally and compare with a separate trusted copy. "
        "Do not invert it, replace it with identity, or flip its flag to bypass the check.",
    ),
    "team_count": Advice(
        "Metadata mismatch",
        "Metadata did not contain two distinct, nonempty team identifiers.",
        "Wrong XML, missing or duplicate team IDs, or an incompatible export.",
        "Verify that ATD XML and TXT belong to the same source/export. Preserve identifiers; "
        "do not invent or manually reassign teams.",
    ),
    "slot_count": Advice(
        "Metadata mismatch",
        "The metadata Player count differed from configured track_slots.",
        "Wrong camera metadata, wrong configured slot count, or incomplete metadata.",
        "Compare track_slots with public source documentation and the selected metadata. "
        "Track slots are not stable player identities; do not add or delete slots to force a pass.",
    ),
    "team_reference": Advice(
        "Metadata mismatch",
        "A Player teamId was missing or did not reference a declared team.",
        "Incomplete metadata, a mismatched export, or inconsistent identifiers.",
        "Verify the paired source files locally. Use a trusted export if needed, retaining "
        "the original; do not manually correct team assignments.",
    ),
    "invalid_interval": Advice(
        "Malformed data",
        "An event failed finite, ordered, nonnegative video-time bounds.",
        "Wrong units/source, incorrect fps/frame_count configuration, or malformed start/end.",
        "Verify seconds-from-video-start, source fps and configured duration using public docs. "
        "Do not shift, clamp or manually correct competition event times.",
    ),
    "missing_code": Advice(
        "Malformed data",
        "A Smart Tagging instance lacked a nonempty code.",
        "Incomplete export, wrong XML, or a missing event field.",
        "Confirm the selected SportsCode export locally. Keep original annotations unchanged; "
        "do not create labels to fill the field.",
    ),
    "event_count": Advice(
        "Count mismatch",
        "The number of instances differed from configured event_count.",
        "Incorrect configuration, wrong export/version, or missing/extra instances.",
        "Check the expected count against public documentation and the selected export. "
        "Do not set event_count to the observed number merely to suppress the failure.",
    ),
}

UNKNOWN = Advice(
    "Unresolved issue",
    "Unrecognized issue code; its failure status is retained.",
    "A newer/different validator or unsupported report content.",
    "Check the helper/validator version and public code documentation locally. For further "
    "development, reproduce the problem with synthetic inputs; keep the report private.",
)


def advice_for(code: str, asset: str) -> Advice:
    if code == "invalid_record" and asset.endswith(".homography"):
        return Advice(
            "Malformed data",
            "A homography record failed shape, numeric or validity checks.",
            "Wrong column count/flag, nonnumeric values, a corrupted valid=1 matrix/error, "
            "or finite matrix values where valid=0 requires missing observations.",
            "Confirm source and format locally. Missing matrices for valid=0 are expected when "
            "well-formed. This code alone does not identify the exact condition or prove the "
            "previous empty-cell bug persists. Do not change flags or matrix values to bypass it.",
        )
    if code == "invalid_record" and asset.endswith(".atd_raw"):
        return Advice(
            "Malformed data",
            "An ATD record failed frame, separator, slot or observation checks.",
            "Wrong triplets/slot count, invalid frame IDs, nonnumeric/infinite values, or only "
            "one of x/y missing. Paired NaN observations are permitted.",
            "Confirm the documented ATD format and source-specific track_slots locally. "
            "Do not fill NaNs, renumber frames or manually correct competition observations.",
        )
    if code == "frame_sequence" and asset.endswith((".atd_raw", ".homography")):
        base = "1-based" if asset.endswith(".atd_raw") else "0-based"
        return Advice(
            "Frame alignment",
            f"Frame IDs did not follow the required ordered {base} sequence.",
            "Duplicate, missing, reordered or offset frame IDs, or a wrong source/export.",
            "Compare the source's frame convention with public docs locally. Do not align "
            "broadcast by tactical row number, renumber frames, or drop rows to force a pass.",
        )
    return ISSUES.get(code, UNKNOWN)
