# License, origin and release scope

The upstream repository is [Metrica Sports / more-than-a-hack-2027](https://github.com/metrica-sports/more-than-a-hack-2027).
Its MIT notice is preserved verbatim in [LICENSE](LICENSE). That license covers source and
documentation, **not** competition match assets. None of those assets or public GT files is
distributed here.

The owner explicitly authorizes distribution of the Ballgorithm project contributions they
control and have the right to license under the included MIT License, with all applicable
third-party notices retained. This authorization does not extend to third-party material
the owner does not control and is not a claim of blanket legal clearance.

The owner confirms personally directed development used the existing Codex/ChatGPT workflow,
with no independent third-party code imports, external contributors' work or undocumented
manual changes. This describes the owner's activity; it is not a legal clearance of generated
code or proof of all provenance. Source notices and available public development records were
reviewed. Absence of another source header does not establish rights.

LICENSE retains the upstream scope preamble verbatim. Its references to `evaluation/gt/`,
`DATA.md` and `RULES.md` describe upstream contents; those paths are not shipped in this release.
See upstream [DATA.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/DATA.md)
and [RULES.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md) for context;
the [November 3 clarification](docs/OFFICIAL_RULES_CLARIFICATION.md) controls conflicting advice.

Production source is copied byte-for-byte from the internal pre-release algorithm checkpoint
`1c4030de6ac4371aa5aeb84039ba8c07c34b54bb`. The three `evaluation/*.py` files and `games.py`
are unchanged public upstream code. The official scorer is retained only because synthetic
compatibility tests call it with explicit invented inputs; the reproduction workflow uses only
the unchanged **format** validator. No supplied-match GT evaluation is part of this release.

`starter/load_homography.py` is retained for synthetic compatibility tests. Its executable code
is unchanged; its module docstring was replaced to remove superseded prediction/video-review
advice. The same November 3 clarification overrides obsolete advice printed by the unchanged
official validator. Do not follow its suggestion to evaluate the provided public GT for selection.
Public constants and illustrative asset filenames in `games.py` are upstream format metadata,
not private configuration. Merely importing that module does not open a data directory.

Pending rule-only packaging work was reviewed and adapted into this release: locked explicit-
interpreter installation, private-config separation, honest technical-template provenance,
file allowlisting, ignore rules and local hash checks. The original 11 files were not altered.
Historical plans, old verification claims and contradictory rule-only submission prose are not
copied into the selected Version B guide. This tree has no inherited Git history.

External research considered IDSSE (DFL-authorized CC BY 4.0, DOI
[10.6084/m9.figshare.28196177.v1](https://doi.org/10.6084/m9.figshare.28196177.v1)) and the original
ten-match [SkillCorner Open Data](https://github.com/SkillCorner/opendata) release (MIT; pinned
revision `741bdb798b0c1835057e3fa77244c1571a00e4aa`). IDSSE attribution: Bassek, Rein, Weber and
Memmert (2025), Scientific Data 12, 195, [DOI 10.1038/s41597-025-04505-y](https://doi.org/10.1038/s41597-025-04505-y).
SkillCorner's [competition call](https://pretalx.pysport.org/skillcorner-x-pysport-analytics-cup-2026/cfp)
provided data-specific MIT evidence. No external dataset, learned model, adapter or predictions
are redistributed here. Those rights findings concern the researched versions, not future datasets.

Dependencies retain their own notices in their installed distributions; they are not vendored.
Publishing the code does not grant permission to publish match inputs, private configs, generated
predictions, run manifests or diagnostics. Only the required CSV goes privately to the organizer.

IDSSE data credit also belongs to Deutsche Fussball Liga (DFL); the applicable license is
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Comparative research transformed
external coordinates and provider labels for evaluation; no such data is distributed here.
The controlling clarification's historical no-external-training statement describes the
foundation at that time. Subsequent external challenger research is disclosed in the technical
report; the selected Version B itself still has no trained component.

## Development evidence reviewed for documentation completion

Existing external-research records dated November 10-11, 2026 were reviewed without reading
datasets or prediction artifacts: IDSSE provenance, the Milestone 4 report/protocol, the
Milestone 5 protocol/rights report, and the final-selection report/protocol. These records remain
outside this 83-file release; their absence here does not imply external data were never used.
They document IDSSE challenger training on four matches, selection on one and two reused tests;
SkillCorner's ten-match frozen comparison; later reuse for selection without subsequent
SkillCorner tuning; and the exclusion of learned challengers from final B. Numerical B defaults
remain provisional engineering assumptions. These are reviewed historical records, not newly
rerun external experiments or an exhaustive audit of every development conversation.

The final B inference inputs are tactical TXT/XML only. Homography-quality and Smart Tagging
integrations were implemented and tested using synthetic fixtures; neither input is enabled in final Version B. Homography format and structural-validator
issues were also investigated. The reviewed nonrestricted historical records do not independently
establish an earlier competition-match inference run using these optional inputs. This is a
limit of the available evidence, not a claim that such runs never happened.
External IDSSE/SkillCorner experiments and Version C research remain separate from final B inference.
