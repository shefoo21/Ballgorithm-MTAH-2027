"""Invented evidence -> decoder -> CSV benchmark. No input/config/report-reading option."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from mtah.inference import EvidenceScores, RuleDecoder
from mtah.inference.submission import write_submission
from mtah.inference.temporal import OfflineTemporalDecoder
from mtah.local.diagnostics import peak_memory


def invented_evidence(count, scenario):
    for frame in range(count):
        # Invented halves and a repeating mixture of control, short possessions, D and gaps.
        period = 1 if frame < count // 2 else 2
        phase = frame % 1000
        label = (
            "H"
            if phase < 400 or 404 <= phase < 600
            else ("A" if phase < 404 or phase >= 850 else "D" if phase < 700 else "X")
        )
        if scenario == "continuous":
            period, label = 1, "H"
        yield EvidenceScores(
            frame,
            period,
            frame == 0 or scenario == "mixed" and frame == count // 2,
            1.0,
            0.95 if label == "H" else 0.0,
            0.95 if label == "A" else 0.0,
            label if label in ("H", "A") else None,
            0.95 if label == "D" else 0.0,
            label == "D",
            label in ("H", "A"),
            label == "X",
            1.0,
            1.0,
            False,
            None,
            False,
            False,
            False,
            (),
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="New invented CSV only")
    parser.add_argument("--mode", required=True, choices=("rules", "rules_temporal"))
    parser.add_argument("--frames", type=int, default=199319)
    parser.add_argument("--scenario", choices=("mixed", "continuous"), default="mixed")
    args = parser.parse_args(argv)
    if not 1 <= args.frames <= 200000:
        parser.error("Invented frame count must be between 1 and 200000")
    wall, cpu = time.perf_counter(), time.process_time()
    source = invented_evidence(args.frames, args.scenario)
    if args.mode == "rules_temporal":
        decoder = OfflineTemporalDecoder(fps=25)
        predictions = decoder.decode(source)
    else:
        decoder = RuleDecoder(fps=25)
        predictions = (decoder.step(e) for e in source)
    counts = Counter({label: 0 for label in "HADX"})

    def counted():
        for p in predictions:
            counts[p.label] += 1
            yield p

    write_submission(args.out, counted(), expected_rows=args.frames)
    report = {
        "kind": "invented_evidence_benchmark_not_accuracy",
        "mode": args.mode,
        "scenario": args.scenario,
        "rows": args.frames,
        "wall_seconds": time.perf_counter() - wall,
        "cpu_seconds": time.process_time() - cpu,
        "peak_memory": peak_memory(),
        "label_counts": dict(counts),
        "csv_sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
        "scope": "evidence_generation_decoder_csv_excludes_tracking_features_and_parsing",
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
