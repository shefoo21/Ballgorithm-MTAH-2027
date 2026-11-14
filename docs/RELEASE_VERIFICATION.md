# Version B release verification

The November 12 sections below are historical. The [November 14 documentation completion](#documentation-completion--2026-11-14)
section records the seven-file update; the [final documentation closure](#final-documentation-closure--2026-11-14)
records the subsequent narrow authorization and proportionate checks.

**Status: the owner confirms the clean-release exact reproduction gate passed. Publication
remains pending separate explicit approval and an actual public revision; both owner-confirmation
gates are resolved within the scopes below.** This report contains synthetic/public-source evidence only. No
competition assets, private configurations, accepted CSVs, manifests, reports or backups were
opened. No competition performance is measured or claimed.

## Frozen implementation and original-work protection

- Original stable checkout: branch `main`; research worktree: `codex/idsse-external-benchmark`.
  Both remain at `1c4030de6ac4371aa5aeb84039ba8c07c34b54bb`, with their existing changes intact
  and no staged additions. No commit, merge, reset, push or publication was performed.
- All **36 production Python modules** are byte-identical to the stable source. The three official
  evaluation modules, `games.py`, `.python-version`, `pyproject.toml` and `uv.lock` are unchanged.
  All **18 existing test files** and four Python scripts were retained unchanged.
- The copied source fingerprint set contains **69 unchanged files**. An independent pre-copy
  snapshot confirmed **81 reviewed public originals** unchanged, including all 11 pending
  rule-only packaging files. Research/stable line-ending differences were distinguished from
  code changes; the release preserves stable source bytes.
- The only upstream loader modification is the module docstring of `starter/load_homography.py`,
  removing superseded prediction/video-review advice. An AST comparison excluding that docstring
  confirms identical executable code. No possession logic, features, thresholds or team mapping
  were changed. Version A is still the library default; B is an explicit opt-in configuration.
- The new source tree has no `.git` directory or inherited objects/history. Restricted assets,
  upstream GT/baseline CSVs, notebooks, research datasets/models, private settings and outputs
  were excluded by an explicit source allowlist, not a recursive checkout copy.

## Exact release inventory

The complete **83-file inventory** is [release-files.txt](release-files.txt):

| Group | Files |
| --- | ---: |
| Production `src/mtah` modules | 36 |
| Tests: 18 existing + 1 new gate test module | 19 |
| Scripts: 4 unchanged Python scripts + PowerShell reproduction gate | 5 |
| Unchanged official evaluation modules | 3 |
| Public upstream homography helper for synthetic compatibility | 1 |
| Documentation, schemas, template, inventory and source fingerprints | 10 |
| Root README/NOTICE/LICENSE, ignore rules, Python version, games, metadata, lock, manifest | 9 |

New release-specific content: README, NOTICE, explicit MANIFEST.in, source-only .gitignore,
ARCHITECTURE, REPRODUCE, TECHNICAL_REPORT, this report, the neutral Version B config template,
source fingerprints, release inventory, PowerShell gate and its regression test module.
Useful pending packaging work was adapted, not blindly copied: reproducible installation,
private-config separation, honest provenance fields, explicit publication inventory and byte checks.
Old rule-only submission claims, historical plans and research artifacts are excluded.

## Historical verification results — 2026-11-12

Target: **Windows x64 / CPython 3.13.7 / uv 0.9.5 / Windows PowerShell 5.1.26100.9818**.
Environments, downloads, invented inputs, reports and archives were isolated in a separate
verification directory, outside the distributable source tree and every original project.

| Check | Result |
| --- | --- |
| Documented PowerShell 5.1 bootstrap + locked installation | Passed; fresh bootstrap and project environments, 16 packages |
| `uv pip check` and explicit-interpreter offline lock check | Passed; lockfile unchanged |
| Entire existing synthetic suite | **588 passed in 499.72 s**, exit 0 |
| New PowerShell gate synthetic regressions | **6 passed in 414.97 s**, exit 0 |
| Combined exercised test inventory | **594 cases**, all passed; existing suite and new module run separately |
| Ruff lint and formatting | Passed; **59** team Python files checked |
| Full-length B inference, repeat, periods, frame alignment and official format | Passed on invented 199,319-frame fixtures |
| Version A compatibility | Existing default/explicit-rule and pipeline tests passed |
| Exact-byte gate | Full-length success and deliberate one-label mismatch both behaved correctly |
| Invalid mode/override, malformed config and malformed tracking | Fixed failure categories; no private fixture values leaked; incomplete failed run retained |
| PowerShell syntax | All three documented blocks and the gate script parsed with PowerShell 5.1 |
| Source distribution and wheel-from-sdist | Built; allowlist/content and license notices checked |
| Fresh installed-wheel environment | 2 packages compatible; isolated imports and A/B inference passed |
| Installed-wheel network-disabled smoke | Two B runs and replay identical on 48 invented frames; input fingerprints unchanged |
| Public-source audit | Local Markdown links resolved; high-signal credential/private-path scan clear |

The existing suite includes the full-length rule-only and temporal pipelines and unchanged
official scorer compatibility on explicitly invented labels. No supplied-match GT evaluation
was performed. These are correctness/operation checks, not a performance estimate.

The new wrapper initially failed under a Python-launched PowerShell 5.1 subprocess because it
inherited a PowerShell 7 module path and could not discover `Get-FileHash`. A failing synthetic
test established the defect. The wrapper now imports the Windows system Utility module by
explicit path; all six regression cases pass. This is a release-tool correction only.

Initial offline installation of the separate wheel environment lacked cached dependency
resolution metadata. Resolving the pinned public `defusedxml==0.7.1` dependency from PyPI
succeeded; subsequent inference required no network. No cold-cache offline-install claim is
made. The final source directory excludes verification environments, caches and build metadata.
The wheel is the runtime library; complete reproduction/testing uses this source tree or sdist,
which also includes the lockfile, documentation and official format validator.

## Publication and licensing review

- [LICENSE](../LICENSE) preserves the upstream Metrica Sports MIT notice verbatim. Match assets
  have separate competition rights and are absent. [NOTICE](../NOTICE.md) records upstream
  code, helper documentation changes, external-research attribution and scope.
- No external tracking data, learned weights or research code is redistributed. External
  comparative evidence is clearly separated from competition accuracy and from B parameter
  provenance. The November 3 organizer email, as supplied by the project owner, controls.
- No private absolute paths, real private Team IDs, credentials or restricted content were
  introduced. Generic paths/IDs inside invented tests and public upstream format constants are
  not real private configuration. Pattern scanning is a bounded audit, not a universal security
  guarantee. Only the reviewed source allowlist should be considered for later publication.
- No inherited GT, baseline, notebook or historical object was opened or copied. No repository
  was initialized. Owner approval is still required before creating/publishing a new repository.
- The owner now authorizes MIT distribution only for contributions they control and have the
  right to license, with applicable third-party notices retained. This does not extend to
  material they do not control or establish blanket legal clearance. Dependencies are not vendored.

## Current owner-only gates

Closed by owner confirmation: Ballgorithm identity, clean-release exact-byte reproduction,
the exact TXT/XML-only B configuration and all four Metadata Audit v3 PASS outputs.
The metadata numeric exit code was not separately captured. These confirmations do not
establish tracking TXT value correctness or competition prediction quality.

The licensing gate is closed by the owner's narrow MIT authorization. The historical-assets
gate is closed using the approved evidence-qualified account, without asserting that earlier
optional-input runs never happened. External research remains distinct from final B inference.

1. Separately approve clean local history and source-only publication to the existing
   `shefoo21/Ballgorithm-MTAH-2027` repository, last verified private and empty in the
   November 14 read-only review. Recheck remote state before later Git actions.
2. Verify the eventual public revision/83-file contents and public-clone reproduction locally;
   fill that actual revision only in the separate upload document.
3. Validate the exact private `Ballgorithm.csv` upload copy and submit it with
   `Ballgorithm.md` or `.pdf` and the public code URL through the current organizer-emailed
   form before the owner-confirmed November 17, 2026, 23:59 CET deadline.

Original Version A, accepted Version B outputs, frozen settings, source assets, backups and
pending packaging work remain untouched. Format validity and exact reproduction cannot establish
competition accuracy, dead-ball quality, spellF1 or placement.


## Final documentation and publication audit — 2026-11-12

The registered team name is confirmed as **Ballgorithm**. The owner independently confirms
successful clean-release B inference, official format acceptance, deterministic repeats and
exact byte reproduction. README and technical-report status now reflect that confirmation;
the private CSV/configuration and all real-data artifacts remain uninspected.

This pass reviews the existing **83 files**, without expanding the publication inventory.
All files were read/scanned as public source; all 64 Python files parse; the 69 frozen source
fingerprints match. Inventory and MANIFEST.in agree, there are no extra/missing files or links,
no `.git` history, and no restricted asset/prediction/config/cache payloads. High-signal secret
and private-absolute-path scanning found no matches. Public upstream constants and invented test
identifiers are explicitly distinct from private match configuration.

Only four documentation files are updated: `README.md`, `docs/TECHNICAL_REPORT.md`,
`docs/REPRODUCE.md` and this verification document. All other 79 files, including model code,
parameters, dependencies, the official evaluator, scripts, tests, templates and the exact
allowlist, are preserved byte-for-byte against the verified source-distribution snapshot. The historical
594-test/build results above remain the prior verification record; this documentation-only
pass does not claim a new full-suite or real-match run. The published source tree is authoritative;
older verification archives predate these prose updates and must not substitute for it.

The report now covers precise frame/half semantics, B's direct evidence-to-temporal architecture,
external A/B/C selection evidence and reuse/coverage limits, weak dead-ball recall, exact local
reproduction and November 3 compliance. Its numerical performance table concerns external data
only, not the provided match. No new model-selection or parameter experiment was performed.

[REPRODUCE.md](REPRODUCE.md) contains proposed PowerShell 5.1 commands for a new one-root-commit
repository, guarded allowlist staging and exact staged bytes, public commit identity review,
separately approved GitHub creation/push, remote inventory/visibility checks, clean-clone checks,
and private `Ballgorithm.csv` / `Ballgorithm.md` upload preparation. These Git mutation/network
publication commands were **not executed**, including in disposable repositories. Syntax and
read-only guards can be checked without staging, committing or contacting a team repository.
`gh` was not found on the audit shell's PATH; the guide supplies its prerequisite and a
browser-based creation alternative. No account or team-owned repository was inspected in that November 12 pass. The later
November 14 read-only review verified the specified repository as private and empty.

At the time of the November 12 audit, publication/submission blockers included the exact enabled optional inputs and
non-sensitive input/parameter provenance, truthful whole-workflow/licensing confirmation,
approved public repository ownership/URL and commit identity, actual final public revision,
explicit publication approval, and the organizer's current emailed form/cutoff timezone.
The clean-release reproduction gate and registered-team-name questions are already resolved.
The final Git SHA belongs in the standalone upload document after the commit exists; a commit
cannot embed its own hash. No private information is needed by the assistant to finish those
owner-only steps.

Publication-only Windows detail: the immutable source mixes LF and CRLF. The proposed Git
configuration preserves both and explicitly recognizes CRLF in whitespace checks. No source
line endings were changed. A read-only initial-add comparison checks this policy without an index.

Final documentation checks passed: 28 local Markdown links/anchors resolve; all eight proposed
PowerShell blocks parse in Windows PowerShell 5.1.26100.9818; the extracted read-only preflight
passes inventory, ancestor-history, path/link and frozen-byte checks. No Git mutation block
was run. Ruff lint and formatting pass for all 59 team Python files, and the existing locked
environment passes the offline 16-package dependency check. The read-only initial-add whitespace
check passes for all 83 files under the documented CRLF-preserving Git policy. The prior
594 synthetic tests were not rerun because only prose changed; all 79 other release files
match the independently checked, previously verified public source archive.

## Documentation completion — 2026-11-14

The owner explicitly authorized only seven documentation files and synthetic verification.
Production source, frozen settings, dependencies/lock, official evaluation, scripts, tests,
the 83-file allowlist and accepted private configuration/output are outside the edit scope.
No Git initialization, staging, commit, push, visibility change or submission is authorized.

### Confirmed configuration and metadata

The final mode is `rules_temporal`, tactical ATD TXT/XML only, with no homography, Smart Tagging,
broadcast/video inference or learned component. Settings are 199,319 frames, 46 slots, 25 FPS,
105 x 68 m, radii 1/3/5 m, nearest_k=3, periods `[11185, 90652)` and `[110808, 190198)`,
and no rule/temporal overrides. Numeric defaults remain provisional engineering assumptions.

The owner reports Metadata Audit v3 returned PASS for `HOME_AWAY_ROLES`,
`CHANNEL_REFERENCES`, `RELEASE_TEAM_SLOTS` and `METADATA_AUDIT`. The numeric exit code
was not separately captured. This closes the metadata review within the audit's stated
scope; it does not validate tracking TXT channel values, predictions or possession accuracy.

### Historical and licensing evidence

The owner confirms personally directed development used Codex/ChatGPT, with no independent
third-party code imports, external contributors' work or undocumented manual changes. This
does not establish blanket ownership or license compatibility. Existing IDSSE provenance,
Milestone 4/5 research and final-selection records were reviewed; no external experiments
were rerun. They support the disclosed external training, evaluation, split/reuse and frozen
SkillCorner comparison history. Competition-asset history and contribution authority were
recorded as open at this seven-file verification point; the subsequent closure below resolves
them with scoped statements. The external D-recall limitation (about 1.86%) remains.

### Authorized changed-file inventory

- `README.md`
- `docs/TECHNICAL_REPORT.md`
- `docs/ARCHITECTURE.md`
- `docs/REPRODUCE.md`
- `docs/RELEASE_VERIFICATION.md`
- `docs/version-b.example.toml` (comments only)
- `NOTICE.md`

### Verification for this documentation change

| Check | Fresh result | Exit code |
| --- | --- | ---: |
| Full synthetic pytest suite | 594 passed in 850.15 s; no skips/failures | 0 |
| Ruff lint | Passed | 0 |
| Ruff formatting | 59 team Python files already formatted | 0 |
| Offline dependency check | 16 installed packages compatible | 0 |
| Offline lock consistency | 16 packages; lockfile unchanged | 0 |
| Inventory and packaging manifest | Exactly the same 83 files; no additions/deletions | 0 |
| Before/after source comparison | Exactly the seven approved files changed; other 76 byte-identical | 0 |
| Frozen fingerprints | All 69 recorded SHA-256 values match | 0 |
| Public TOML template | Parsed values and every active non-comment line unchanged | 0 |
| Local Markdown targets | 31 links resolved, including 2 checked anchors | 0 |
| PowerShell 5.1.26100.9818 syntax | 10 documented blocks plus unchanged gate script parsed | 0 |
| Public-template loader smoke | Invented local paths/fixtures loaded by the real frozen loader; unused tag aliases accepted | 0 |
| Report-export transformation | 3 invented-text checks: pinned-link conversion and OWNER_CONFIRM/legacy-marker rejection | 0 |
| Bounded source security scan | No tested credential/private-absolute-path pattern matches | 0 |

The full synthetic suite includes 199,319-frame A/B inference, repeated-run byte checks,
period/alignment checks, official format compatibility and the six PowerShell release-gate
regressions. No new tests or source scripts were added to the release. Additional template/export
checks used only invented material outside it; no final upload document was produced.

The initial sandboxed dependency check exited 2 because its interpreter-cache write was denied.
Repeating the offline check with the existing external verification cache passed, exit 0.
No dependencies or lockfile were changed. Environments and verification artifacts stay outside
the source tree. No new wheel/build is claimed for this prose-only pass; the unchanged manifest
and packaging inputs were checked, and the historical build results above retain their dates.

All seven documentation diffs were reviewed. Two owner-confirmation gates remained open at
that point; the subsequent final documentation closure below records their resolution.
The exact public revision is intentionally unresolved until a public commit exists.
No Git mutation/publication command, competition processing or match-based evaluation was run.

The seven-file change updates confirmed input/settings disclosure, metadata-audit scope,
historical provenance, organizer generation instructions and the existing-repository plan.
The final public Git revision intentionally remains unresolved. The future separate
`Ballgorithm.md` export uses that actual SHA and absolute pinned GitHub links, outside the
83-file release. Publication blocks are documentation only and have not been executed.

## Final documentation closure — 2026-11-14

The owner explicitly authorized the narrow MIT statement and the qualified historical-asset
account. The technical report and NOTICE now record both. README and this verification record
were updated only to remove stale open-gate status. No ownership warranty or complete
competition-experiment history is inferred. IDSSE/SkillCorner experiments and the excluded
learned Version C remain separate from the submitted TXT/XML-only Version B.

Exactly four existing documentation files changed in this closure: `docs/TECHNICAL_REPORT.md`,
`NOTICE.md`, `README.md` and `docs/RELEASE_VERIFICATION.md`. The original LICENSE, frozen
model/settings, dependencies/lock, scripts, tests and public template are outside this edit.
The final public SHA remains `[FINAL_PUBLIC_GIT_REVISION]` in the source technical report.

| Documentation-specific check | Result | Exit code |
| --- | --- | ---: |
| Release inventory and packaging manifest | Exactly the same 83 files | 0 |
| Change scope and byte comparison | Four approved documentation files changed; other 79 byte-identical | 0 |
| Frozen fingerprints | All 69 SHA-256 values match; original LICENSE and public TOML unchanged | 0 |
| Placeholder check | No unresolved owner-confirmation fields; final public SHA remains intentionally pending | 0 |
| Markdown file targets and anchors | 32 local links resolved, including 3 anchors | 0 |
| Bounded sensitive-information scan | No tested credential/private-absolute-path matches; added prose reviewed | 0 |
| Synthetic report-export transformation and guards | 3 checks passed; no upload document written | 0 |

The first constrained-shell export-check launch was denied by PowerShell AuthorizationManager
(exit 1). The unchanged command passed in the approved verification context (exit 0); no
execution-policy setting was changed. The exact four-file diff was reviewed.

The earlier 594-test success, exit 0, remains the prior synthetic verification result.
The full suite was not rerun for these prose-only changes. No Git action, public-repository
mutation, competition inference, private-data access, model tuning or submission occurred.
