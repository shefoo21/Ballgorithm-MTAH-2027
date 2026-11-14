# Ballgorithm — More Than a Hack 2027, Version B

Deterministic tactical football-possession inference on CPU. The selected system is
**frozen rule evidence plus offline temporal decoding**, `rules_temporal` mode.
There are no learned weights or training steps in this release. Version A (`rules`)
remains the unchanged library default and preserved fallback.

```text
Tactical ATD TXT + metadata XML
  -> ordered frame/slot adapter -> deterministic features
  -> rule-based control/stoppage evidence
  -> offline H/A/D temporal decoder with explicit X abstention
  -> frame,label CSV (199,319 ordered tactical frames)
```

- [Install and reproduce, including the private exact-byte gate](docs/REPRODUCE.md)
- [Architecture and frozen specification](docs/ARCHITECTURE.md)
- [Technical report](docs/TECHNICAL_REPORT.md)
- [Controlling organizer clarification](docs/OFFICIAL_RULES_CLARIFICATION.md)
- [Release verification and remaining gates](docs/RELEASE_VERIFICATION.md)
- [Exact file inventory](docs/release-files.txt), [source fingerprints](docs/source-fingerprints.json)
- [License and attribution](NOTICE.md)

H/A mean home/away live possession; D means dead ball; X means abstention. Output is UTF-8
with `frame,label`, indices 0 through 199318, no blank cells or extra index column.
The submitted Version B uses tactical ATD TXT and metadata XML only. Tactical homography,
Smart Tagging, broadcast data and video inference are disabled. There are no rule or temporal
overrides. The [public template](docs/version-b.example.toml) matches the owner-confirmed
non-sensitive settings; paths and H/A IDs must be populated locally from licensed inputs.
Rules and temporal parameters remain frozen provisional engineering defaults, not calibrated
constants. No possession ground truth is an inference input.

The user reports successful original Version B inference, repeat verification, official format
acceptance and an independent SHA-256 match. The owner has also confirmed that the clean
source-only release passed its local exact-byte reproduction gate. The assistant did not inspect
private inputs or outputs. Format acceptance does not establish accuracy or competition spellF1.

The owner reports Metadata Audit v3 returned PASS for `HOME_AWAY_ROLES`,
`CHANNEL_REFERENCES`, `RELEASE_TEAM_SLOTS` and `METADATA_AUDIT`. The numeric exit code
was not separately captured. This closes the metadata review within the audit's stated
scope; it does not validate tracking TXT channel values, predictions or possession accuracy.

Tested target: Windows x64, CPython 3.13.7, uv 0.9.5. Reproduction instructions support
Windows PowerShell 5.1. Other Python/platform combinations are not certified. Installation may
download public dependencies; inference is offline. Restricted assets and all derived outputs
must remain outside this tree and hosted AI services.

Selection used external comparative evidence, not competition prediction quality. B improved
external spell matching over A in the examined comparisons but had lower frame macroF1 and
more abstention. Dead-ball/restart recognition remains weak. See the technical report for
evidence coverage, reuse and provenance limitations. No competition performance is claimed.

The destination is [shefoo21/Ballgorithm-MTAH-2027](https://github.com/shefoo21/Ballgorithm-MTAH-2027),
verified private and empty during the November 14, 2026 read-only review. The two owner-confirmation
gates are resolved with the scoped statements in the technical report and NOTICE. Publication
remains pending separate explicit approval. The
[guarded publication procedure](docs/REPRODUCE.md#5-proposed-clean-history-and-existing-repository-publication)
uses clean Git history and the unchanged 83-file allowlist. Submission filenames are
**Ballgorithm.csv** and **Ballgorithm.md** (or **Ballgorithm.pdf**). The owner-confirmed cutoff is
**November 17, 2026, 23:59 CET**.
