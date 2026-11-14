# Ballgorithm — Tactical possession with frozen temporal decoding

> Complete bracketed fields locally before submission. Do not paste private configurations,
> identifiers, hashes, run reports or match observations. Remove this completion note and use
> final public revision links when exporting **Ballgorithm.md** or **Ballgorithm.pdf**. The
> final revision placeholder is filled in the upload copy after the public commit exists;
> a commit cannot contain its own hash. The owner-confirmation statements below are now resolved.

**Team:** Ballgorithm

**Source repository:** [shefoo21/Ballgorithm-MTAH-2027](https://github.com/shefoo21/Ballgorithm-MTAH-2027)
(publication pending; verified private and empty on November 14, 2026).

**Final public Git revision:** [FINAL_PUBLIC_GIT_REVISION]

**Internal pre-release algorithm checkpoint (not a revision in the new public history):** `1c4030de6ac4371aa5aeb84039ba8c07c34b54bb`

**Submitted method:** Version B, `rules_temporal`; no learned-model component.

## Objective and architecture

We infer H/A/D/X on all 199,319 tactical video frames: home possession, away possession,
dead ball and explicit abstention. Deterministic tracking features feed fixed rule-based control
evidence, then an offline duration-aware H/A/D decoder. CPU execution, exact frame coverage,
independent half resets and repeatable output are explicit contracts. H/A describe live team
possession, D means the ball is not in play, and X records uncertainty or an ungraded frame.
X is not interchangeable with D. Version A's causal rule-only
decoder remains a fallback; it is not the selected B pipeline.

## Features and possession semantics

Tactical ATD TXT supplies ordered player/ball observations; XML supplies team-slot mapping.
One-based ATD indices become zero-based video frames. Normalized coordinates use configured
pitch dimensions; NaNs and original slot order are preserved. Slots are not player identities.
Features include team ball distances, nearest-k/proximity statistics, coverage, ball and team
motion evidence, missingness and uncertainty. Missing coordinates are not silently filled. Motion
history resets across gaps and halves. The public Phase 1 contract is 25 fps and 46 ordered track
slots. Output has exactly `frame,label`, indices 0 through 199318 in order and no blank cells.
The public half-open periods are `[11185, 90652)` and `[110808, 190198)`; all other frames emit X.
These boundaries are format metadata, not labels manually created for the provided match.

Direct control requires geometry, opponent separation, visibility and reliability support.
Version B feeds the shared rule evidence directly to the temporal decoder; it does not smooth
Version A's final labels. A dynamic program over H/A/D and capped dwell age balances reliable
anchors against frozen transition and soft early-exit costs, using future evidence only inside
bounded islands. A brief opposing observation need not create
a turnover; strong brief possession can overcome the soft cost. Missing or loose-ball intervals
carry supported ownership for bounded time, then abstain; missingness alone never means dead ball.
D entry needs corroborated stoppage evidence; restarts require fresh control and motion.
Smart Tagging is disabled in the submitted system; its optional library cues are never labels.
Tie breaking is fixed, and expired unsupported intervals or half boundaries
reset the decoder. Evidence islands have explicit memory limits; exceeding a limit fails rather
than silently changing predictions. Exact settings and implementation are in [architecture](ARCHITECTURE.md).

## Assets actually used

| Asset | Submitted run |
| --- | --- |
| Tactical ATD TXT and metadata XML | Used: the only enabled input sources |
| Tactical homography CSV | Omitted |
| Tactical Smart Tagging XML | Omitted |
| Broadcast assets and both videos | Excluded from this inference pipeline |
| Provided possession GT | Excluded from inference and all fitting/tuning/model selection |

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

**Temporal settings:** all defaults in the architecture table, with no overrides. The owner
independently confirmed the accepted private configuration; the clean-release gate also checks
`rules_temporal` mode and the temporal defaults. No private TOML, identifiers or paths are published.

**Research assets and excluded candidates:** recorded external experiments used IDSSE tracking,
provider possession/status targets, and SkillCorner tracking/metadata/partial phase references.
Learned challengers were trained and compared externally but excluded from final Version B.
Those datasets, adapters, weights and external outputs are not inference dependencies or shipped
assets.

**Optional challenge-input history:** Homography-quality and Smart Tagging integrations were
implemented and tested using synthetic fixtures; neither input is enabled in final Version B. Homography format and structural-validator
issues were also investigated. The reviewed nonrestricted historical records do not independently
establish an earlier competition-match inference run using these optional inputs. This is a
limit of the available evidence, not a claim that such runs never happened.

## Training, parameter and selection provenance

Version B has no training, fitting, learned weights or calibration step. Its numeric rules and
temporal defaults are inherited provisional engineering assumptions, not externally fitted
constants. No provided-match video/GT was used for parameter selection or model comparison.
Public contracts and invented fixtures supported implementation correctness.

External research compared A, B and trained challengers; **no trained challenger is included in
the submitted B system**. IDSSE v1 (DFL-authorized CC BY 4.0, 7 matches) supplied provider possession
and active/inactive labels. Challenger training used 4 matches and selection used 1; the 2 test
matches had already been examined. Those targets are released provider possession/status fields,
not labels created by this team. The original SkillCorner ten-match MIT release supplied partial,
automatically generated ownership/phase evidence; these are noisy references, not verified referee
truth. No reliable full D reference was inferred from gaps. Sources,
versions and attribution are in [NOTICE](../NOTICE.md). No manual competition labels were used.

The previously recorded equal-match means are:

| Frozen candidate | IDSSE spellF1, 2 reused tests | IDSSE macroF1 | SkillCorner partial spellF1, 10 matches | SkillCorner H/A macroF1 |
| --- | ---: | ---: | ---: | ---: |
| A: causal rules | 0.2743 | 0.5066 | 0.4720 | 0.4743 |
| **B: rule evidence + temporal (selected)** | **0.4002** | **0.4820** | **0.4904** | **0.4241** |
| C: robust learned challenger + temporal (excluded) | 0.4223 | 0.8406 | 0.4670 | 0.5883 |

SkillCorner reference coverage was 49.80%; gaps were not assigned fabricated dead-ball labels.
The comparison unit is the match, not independent adjacent frames. IDSSE's two test matches had
already been reused; SkillCorner was a frozen independent-provider comparison, subsequently
reanalyzed for selection. This is reused evidence, not a fresh independent post-selection
estimate. Provider labels
are not proven identical to the competition definition; partial and full scores are not comparable.
We selected B because spell matching was the priority, its external advantage over A appeared
on both reused IDSSE tests and eight of ten SkillCorner matches, and the temporal path was
already integrated and reproducible. C had stronger IDSSE frame/dead-ball results, but its
partial SkillCorner spellF1 was below B and independent-provider full H/A/D generalization
remained unresolved. No late learned-model integration was justified. B accepts lower frame
agreement, more abstention and weak dead-ball detection. This is not proof of improved
competition performance. The reviewed Milestone 5 and final-selection records document frozen
comparison and no subsequent SkillCorner tuning; no new evaluation was run for this document.

**Development provenance:** the owner confirms all personally directed development occurred
through the existing Codex/ChatGPT workflow, with no independent third-party code imports,
external contributors' work or undocumented manual changes. Existing research records support
the external experiment account above. This statement does not establish blanket code ownership
or license compatibility. Known notices, record scope and the limits of this review are
disclosed in [NOTICE](../NOTICE.md).

**Licensing authorization:** The owner explicitly authorizes distribution of the Ballgorithm
project contributions they control and have the right to license under the included MIT License, with all applicable
third-party notices retained. This authorization does not extend to third-party material
the owner does not control and is not a claim of blanket legal clearance.

## Limitations and verification

Dead-ball recognition remains weak: B's mean D recall on the two reused IDSSE tests was about
1.86%; restart detection was also weak. SkillCorner cannot validate full D performance. Tracking
gaps conceal turnovers, proximity is not control, and temporal costs can erase short possessions.
X intervals can produce many raw fragments. Confidence is uncalibrated.
No competition accuracy, spellF1, placement or generalization guarantee is claimed.

The user reports original B inference exit 0, 199,319 ordered rows accepted by the unchanged
official format validator, repeat verification and independent byte-identical outputs. The
clean-release synthetic checks are recorded in [verification](RELEASE_VERIFICATION.md).
**Clean-release reproduction:** the owner independently confirmed successful full-length B
inference, deterministic repeat execution, official format acceptance and byte-identical
reproduction from the clean source-only release. No private configuration, CSV, hash or report
was inspected by the assistant. The documented synthetic verification comprises 588 existing
cases plus six release-gate cases (594 total), including full-length success and deliberate
mismatch rejection. Structural validity and repeatability do not establish prediction quality.

The owner reports Metadata Audit v3 returned PASS for `HOME_AWAY_ROLES`,
`CHANNEL_REFERENCES`, `RELEASE_TEAM_SLOTS` and `METADATA_AUDIT`. The numeric exit code
was not separately captured. This closes the metadata review within the audit's stated
scope; it does not validate tracking TXT channel values, predictions or possession accuracy.

## Complete reproduction

Obtain licensed inputs separately. Follow [REPRODUCE.md](REPRODUCE.md) from the final source tree:
Windows x64 CPython 3.13.7, uv 0.9.5, locked install with the evaluation extra and synthetic tests.
Organizers create their own private TOML from the public template using licensed tactical TXT/XML,
the settings above and locally verified H/A IDs from explicit EPTS Score metadata. Slot order
is preserved; it does not establish H/A orientation. Generate into a fresh private run directory.
The owner retains the existing accepted private TOML unchanged. The CLI is
`python -m mtah.local --config <private> --run-name <new> --local-only --verify-repeat`.
Do not use `--diagnose`, which is rule-only. The user-only gate runs the unchanged format
validator and requires SHA-256 equality with the accepted B CSV. A mismatch stops release;
it never triggers parameter tuning. Inputs, private settings, outputs and diagnostics stay local.
Generating predictions does not require the owner's private TOML or accepted CSV. Byte equality
does require comparison with the accepted output, locally by its authorized holder. The required
tag-name fields are unused with Smart Tagging disabled; new organizer configs may use distinct
neutral aliases. No external research dataset, trained weights, model download or network
inference is needed. Other Python/platform combinations have no byte-identical guarantee.

No prediction/video comparison, manual labels/corrections, restricted AI uploads or match-based
fitting/calibration/tuning are permitted. Any future training/tuning must use licensed external
data. The organizer's November 3, 2026 clarification is controlling and supersedes earlier
permission for learning on the provided game. Local structural/operational checks are separate
from accuracy evaluation and cannot select settings. Preserve the accepted B output and fallback A.

Submit the unchanged verified output as **Ballgorithm.csv** and this completed document as
**Ballgorithm.md** (or **Ballgorithm.pdf**), with the final public repository URL and actual Git revision.
The owner-confirmed deadline is November 17, 2026, 23:59 CET. Export the upload document outside
this source tree after the approved public commit exists.
