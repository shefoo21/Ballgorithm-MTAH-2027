# Frozen Version B specification

Internal pre-release algorithm checkpoint (not the final public Git revision): `1c4030de6ac4371aa5aeb84039ba8c07c34b54bb`.
Mode: `rules_temporal`; adapter implementation `rules-with-offline-temporal-v1`.
There is no production-code change in this release. Source hashes are in
[source-fingerprints.json](source-fingerprints.json). The owner independently confirmed the final
configuration: tactical ATD TXT and metadata XML only; no homography, Smart Tagging, broadcast
or video inference; no learned component and no rule or temporal overrides. The
[public template](version-b.example.toml) matches these non-sensitive settings. Preserve the
owner's accepted private TOML; organizers populate their own paths and H/A IDs.

| Setting | Owner-confirmed final Version B value |
| --- | --- |
| Inference mode | `rules_temporal` |
| Frame count / tracking slots | 199,319 / 46 |
| Sampling rate | 25 FPS |
| Pitch dimensions | 105 x 68 m |
| Proximity radii | 1, 3, 5 m |
| `nearest_k` | 3 |
| First period | `[11185, 90652)` |
| Second period | `[110808, 190198)` |
| Rule and temporal overrides | None; frozen defaults |

## Input and feature contracts

`mtah.local.inputs` streams explicitly configured tactical ATD records. One-based ATD indices
map to zero-based video frames. XML supplies ordered player-slot team references. The runner
assigns H/A using explicitly configured team IDs; it does not independently infer orientation
from Score. The owner separately verified those roles against explicit EPTS Score metadata.
Neither XML team order nor slot identity establishes H/A roles. Slots are not persistent
identities and are never sorted. Invalid alignment/metadata fails rather than filling
frames. Missing coordinates remain NaNs. No private directory discovery occurs.

`mtah.features` produces per-team nearest/nearest-k ball distances, proximity counts, coverage,
motion/speed evidence, missingness and reliability. Normalized x/y coordinates are converted
using the **configured** pitch dimensions. Histories reset at gaps and period boundaries.
Homography availability/error and Smart Tagging are optional library capabilities, both disabled
in final Version B. Neither supplies possession truth. Geometric proximity does not prove control.

`EvidenceModel` applies the unchanged `RuleConfig` to these features: direct-control support,
opponent margin, source reliability, corroborated stoppage candidates and restart-motion evidence.
B uses this shared evidence model directly, **not** a post-filter on Version A's final labels.
Version A separately uses the causal confirmation/continuity `RuleDecoder` and is unchanged.

## Offline decoder

`mtah.local.temporal.temporal_pass` connects features, `EvidenceModel` and `OfflineTemporalDecoder`.
The dynamic program uses H/A/D states and capped dwell age. Reliable anchors permit entry and
transitions; soft duration/transition costs discourage unsupported flicker while allowing strong
short control. It may use future evidence within a bounded evidence island. Exact ties follow
fixed state/age iteration order. D entry requires corroborated evidence; leaving D additionally
requires restart motion. Missingness is not D evidence. Unsupported continuity expires and emits
X. Half changes, stream discontinuities and expired evidence islands reset state independently.
No learned probability, adaptive fitting or data-dependent threshold selection occurs.

Costs are additive support-seconds, not negative log probabilities. Observation cost is
`observation_weight * (source_confidence - state_support) / fps`. A transition adds its base cost
times `(1 - turnover_discount * destination_support)` plus a capped-age early-exit penalty.
There is no hard minimum possession duration or terminal exit penalty. Resource limits reject
excessively large islands rather than silently changing the model. The private operational
report describes runs; it does not measure label correctness or select parameters.

| Frozen temporal setting | Value |
| --- | ---: |
| observation_weight | 1.0 |
| turnover_cost | 0.12 |
| dead_entry_cost | 0.12 |
| restart_cost | 0.12 |
| turnover_discount | 0.8 |
| duration_s | 0.4 |
| short_exit_cost | 0.08 |
| min_source_confidence | 0.3 |
| min_support | 0.55 |
| min_confidence | 0.2 |
| max_unsupported_s | 1.0 |
| continuity_half_life_s | 1.5 |
| max_segment_frames | 200000 |
| max_age_bins | 64 |
| max_backpointer_bytes | 67108864 |

The numerical values are inherited synthetic-design engineering defaults, not fitted or
calibrated on the supplied match, its GT, or external matches. External comparisons supported
choosing this frozen architecture; they do not retrospectively calibrate its constants.
[The rule schema](inference-config.schema.json) and [temporal schema](temporal-config.schema.json)
record settings. The final configuration has empty rule/temporal override tables. Public-template
comments do not change parsed values. The library default remains rule-only; explicitly select B.
Metadata-audit PASS verifies roles/references/slots within that audit, not TXT values or accuracy.

## Output and execution

Phase 1: 25 fps, 46 ordered slots, 199,319 frames. Graded periods are half-open
`[11185, 90652)` and `[110808, 190198)`; all other frames emit X. These are public alignment
contracts, not newly inferred match labels. The writer enforces exact ordered coverage and
H/A/D/X. A fresh run is reserved exclusively, marked incomplete, and becomes complete only
after input fingerprints, replay (when requested) and final report writes pass. Inputs stay
read-only. B needs CPU and bounded evidence storage, not a GPU or network.

Peak memory includes Python/evidence objects beyond the traceback allocation. No cross-platform
bitwise guarantee is made. Use the pinned Windows environment and the exact private hash gate.
Failure never authorizes fallback predictions, label edits or parameter changes.
