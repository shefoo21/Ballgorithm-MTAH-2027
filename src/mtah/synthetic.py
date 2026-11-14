"""Input-free invented pipeline. This example is not a prediction of the competition match."""

import argparse
import math
from pathlib import Path

from mtah.features import FeatureConfig, FeatureInput, HomographyQuality, Period, iter_features
from mtah.inference import FeatureContract, InferenceError, iter_predictions
from mtah.inference.submission import write_submission
from mtah.tracking import Observation, TrackingFrame


def synthetic_predictions(frame_count: int = 199319):
    """O(1) history, invented periods and repeating control/stoppage scenarios."""
    if type(frame_count) is not int or frame_count < 1:
        raise InferenceError("Invalid synthetic length")
    periods = (
        (Period(1, 2, frame_count // 2 - 2), Period(2, frame_count // 2 + 2, frame_count - 2))
        if frame_count >= 16
        else (Period(1, 0, frame_count),)
    )
    config = FeatureConfig(100.0, 50.0, 25.0, periods)
    teams = ("H", "A")
    players = (Observation(0.2, 0.5, 0.0), Observation(0.8, 0.5, 0.0))

    def samples():
        for index in range(frame_count):
            phase = index % 500
            speed = 0.0
            if 330 <= phase < 360:
                ball = Observation(math.nan, math.nan, math.nan)
            else:
                if 180 <= phase < 188 or 210 <= phase < 330:
                    x = 0.8
                elif 360 <= phase < 420:
                    x = 1.1
                elif phase >= 420:
                    # Small reversible motion near home; no persistent person identities.
                    step = (phase - 420) % 20
                    x, speed = 0.2 + 0.0004 * min(step, 20 - step), 1.0
                else:
                    x = 0.2
                ball = Observation(x, 0.5, speed)
            yield FeatureInput(
                TrackingFrame(index, players, ball), HomographyQuality(index, True, 0.0)
            )

    yield from iter_predictions(
        iter_features(samples(), config=config, slot_teams=teams),
        contract=FeatureContract(config, teams),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, required=True, help="New output path in an existing directory"
    )
    parser.add_argument(
        "--frames", type=int, default=199319, help="Invented frame count (default 199319)"
    )
    args = parser.parse_args(argv)
    try:
        count = write_submission(
            args.out, synthetic_predictions(args.frames), expected_rows=args.frames
        )
    except InferenceError as error:
        parser.exit(1, f"Synthetic pipeline failed: {error}\n")
    print(f"Wrote {count} invented frames. Format check only; no match score or performance claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
