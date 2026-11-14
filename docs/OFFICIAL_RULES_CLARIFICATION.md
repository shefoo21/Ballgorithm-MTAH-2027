# Controlling official rules clarification

**Controlling authority: the organizers' updated clarification email**, as communicated by
the project owner on 2026-11-03. It explicitly supersedes earlier documentation, emails and
individual answers wherever they conflict. The original email was not retrieved by this
assistant; this record faithfully captures the project owner's supplied clarification and
its mandatory engineering consequences. Preserve the original email locally as provenance.

## Strictly prohibited

1. Checking our possession predictions against the provided match video.
2. Manually creating labels, corrections, annotations or other human-produced data for the
   provided match, including selected transitions or indirect handwritten rule exceptions.
3. Uploading restricted competition data or extracts to hosted AI services.
4. Training, retraining, fitting, calibrating or tuning any algorithm on the provided match
   video or its ground-truth possession data. This supersedes earlier permission for learning
   without human labels; unsupervised/self-supervised/pseudo-label training on this match is
   not an exception to the updated prohibition.
5. Using the provided match to select hyperparameters, thresholds or model variants based on
   observed prediction quality. The public five-minute GT cannot select parameters or models.

## Explicitly permitted

1. Automatic structural and operational checks using the provided data.
2. Inspecting provided data/video to understand possession meaning and format, without
   comparing predictions to video or manually labeling the match. The assistant's stricter
   development boundary below still applies.
3. Inference using supplied video, automatic tracking, Smart Tagging and generated inputs with
   an algorithm not trained on the supplied video or possession GT.
4. Producing intermediate files while respecting licensing and restrictions on AI uploads.
5. Training and tuning exclusively on appropriately licensed external datasets.

## Mandatory engineering implications

- Develop using public format documentation and invented fixtures only. The user independently
  executes all restricted-data processing locally. Never inspect, upload or receive match
  prediction files, tracking records, private configs/reports or video extracts through this
  assistant. No automatic directory discovery, cloud telemetry or hosted inference on assets.
- Keep integrity/operational diagnostics separate from performance evaluation. Runtime, memory,
  row coverage, missingness, output label/run statistics and byte-repeatability are operational
  facts, not correctness or spellF1 evidence. They cannot drive match-specific parameter/model
  selection. Diagnostic warnings never auto-tune, smooth, correct or relabel predictions.
- Do not implement prediction-versus-video review, overlays, clickable prediction timestamps,
  manual correction workflows or any equivalent tool for this match.
- Preserve source assets and official evaluation implementation. Write new local outputs outside
  the original dataset root, keep them out of public Git, and never transmit report contents.
- Freeze explicit parameters and record code, environment, effective configuration and input
  fingerprints. Identical input/config/code must reproduce the same CSV; elapsed time/memory
  are intentionally variable measurements and are recorded separately.
- Choose tunable parameters on permitted external data or document provisional externally
  justified engineering assumptions. The existing rule constants are inherited unvalidated
  synthetic-design defaults; their numerical values have **not** been externally calibrated.
  This integration milestone freezes those defaults and makes no new performance claim.
  Establish external justification/validation before describing any settings as competition
  optimized; do not create that justification by inspecting this match's output quality.
- Record external dataset identity, source, license and training/derivative permissions,
  organizer accessibility, acquisition/version/checksums, label provenance, exclusions of the
  supplied match, match-level splits, selected parameters, procedure and code revision.
  No external training/tuning dataset has been used in this implementation.

## Conflicts with preserved upstream material

Upstream files remain unchanged as public format/evaluation references. This clarification
controls behavior even where they contain incompatible older advice:

| Earlier material | Current treatment |
| --- | --- |
| `RULES.md`: learning without human labels on the supplied game | Superseded; no training/fitting/tuning on the supplied match |
| `RULES.md`/`CHALLENGE.md`: general hosted LLM/API permission | Does not authorize uploading restricted data or extracts |
| `starter/load_homography.py`: project a spurious prediction transition onto video to inspect mistakes | Prohibited for this competition match; no such tool or workflow here |
| Evaluation/starter examples comparing baseline variants on public GT | Not a parameter/model selection workflow; never run for development or tuning |
| Earlier broad debugging/video-review suggestions | Limited to permitted format understanding and automatic operational checks; no prediction-versus-video comparisons |

The local runner's release checks use the unchanged **submission format validator**, not
`run_evaluation.py` or any GT. No claim of improved competition performance is permitted
without legitimate evidence. This file controls the planning and operating documents below.
