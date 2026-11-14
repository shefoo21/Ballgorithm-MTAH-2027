"""Strict CSV output, published only when complete, without overwriting any file."""

import csv
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from mtah.inference.contracts import InferenceError, Prediction


def write_submission(
    path: Path | str, predictions: Iterable[Prediction], *, expected_rows: int
) -> int:
    """Stream 0..N-1 to UTF-8 CSV. Parent must exist; target must be new.

    A same-directory temporary file is published exclusively after validation and
    flush: Windows rename (which refuses an existing target), POSIX hard link. Never
    inspect an existing output or silently pad, sort, truncate or renumber a stream.
    """
    if type(expected_rows) is not int or expected_rows < 1:
        raise InferenceError("Invalid expected submission length")
    temporary = None
    try:
        target = Path(path)
        if os.path.lexists(target):
            raise InferenceError("Submission target must be new")
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=target.parent,
            prefix=".mtah-submission-",
            suffix=".tmp",
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("frame", "label"))
            count = 0
            for prediction in predictions:
                if (
                    not isinstance(prediction, Prediction)
                    or type(prediction.video_frame) is not int
                    or prediction.video_frame != count
                    or type(prediction.label) is not str
                    or prediction.label not in ("H", "A", "D", "X")
                    or count >= expected_rows
                ):
                    raise InferenceError("Invalid submission sequence")
                writer.writerow((count, prediction.label))
                count += 1
            if count != expected_rows:
                raise InferenceError("Submission length mismatch")
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            os.rename(temporary, target)  # Windows rename is exclusive, unlike POSIX rename.
        else:
            os.link(temporary, target)
        return count
    except (OSError, TypeError):
        raise InferenceError("Could not create a new submission file") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
