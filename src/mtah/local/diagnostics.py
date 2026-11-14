"""Local aggregate operations only: no accuracy scores, frame records or auto-tuning."""

import os
import sys
from collections import Counter


class OperationalStats:
    def __init__(self, config):
        self.config = config
        self.rows = self.graded = self.missing_ball = self.missing_player_slots = 0
        self.labels = Counter({label: 0 for label in "HADX"})
        self.period_labels = {
            str(p.period_id): Counter({label: 0 for label in "HADX"})
            for p in config.features.periods
        }
        self.reasons = Counter()
        self.run_label = self.run_period = None
        self.run_length = 0
        self.spells = {
            team: {"count": 0, "frames": 0, "min_frames": None, "max_frames": 0, "short_count": 0}
            for team in "HA"
        }

    def add(self, sample, prediction):
        self.observe(sample)
        self.add_prediction(prediction)

    def observe(self, sample):
        """Count observations while reading; temporal mode does not retain tracking samples."""
        self.missing_ball += not sample.tracking.ball.observed
        self.missing_player_slots += sum(not p.observed for p in sample.tracking.players)

    def add_prediction(self, prediction):
        """Consume ordered final predictions after causal or offline decoding."""
        self.rows += 1
        label, period = prediction.label, prediction.period_id
        self.labels[label] += 1
        self.reasons.update(prediction.reason_codes)
        if period is not None:
            self.graded += 1
            self.period_labels[str(period)][label] += 1
        if (label, period) != (self.run_label, self.run_period):
            self._finish_run()
            self.run_label, self.run_period, self.run_length = label, period, 0
        self.run_length += 1

    def _finish_run(self):
        if self.run_label in ("H", "A") and self.run_period is not None and self.run_length:
            s = self.spells[self.run_label]
            s["count"] += 1
            s["frames"] += self.run_length
            s["min_frames"] = min(s["min_frames"] or self.run_length, self.run_length)
            s["max_frames"] = max(s["max_frames"], self.run_length)
            s["short_count"] += (
                self.run_length / self.config.features.fps
                < self.config.diagnostics.short_fragment_s
            )
        self.run_length = 0

    def finish(self):
        self._finish_run()
        fps = self.config.features.fps
        possessions = {}
        for team, s in self.spells.items():
            possessions[team] = {
                "count": s["count"],
                "short_count": s["short_count"],
                "min_seconds": s["min_frames"] / fps if s["count"] else None,
                "mean_seconds": s["frames"] / fps / s["count"] if s["count"] else None,
                "max_seconds": s["max_frames"] / fps if s["count"] else None,
            }
        total_runs = sum(s["count"] for s in self.spells.values())
        short = sum(s["short_count"] for s in self.spells.values())
        x = sum(counts["X"] for counts in self.period_labels.values())
        x_fraction = x / self.graded if self.graded else 0.0
        short_fraction = short / total_runs if total_runs else 0.0
        alerts = []
        if x_fraction > self.config.diagnostics.max_abstention_fraction:
            alerts.append("high_graded_abstention")
        if short_fraction > self.config.diagnostics.max_short_fragment_fraction:
            alerts.append("many_short_prediction_runs")
        return {
            "coverage": {
                "rows": self.rows,
                "expected_rows": self.config.frame_count,
                "complete_ordered": self.rows == self.config.frame_count,
                "graded_rows": self.graded,
                "ungraded_rows": self.rows - self.graded,
            },
            "missing_ball_frames": self.missing_ball,
            "missing_player_slot_observations": self.missing_player_slots,
            "label_counts": dict(self.labels),
            "period_label_counts": {p: dict(v) for p, v in self.period_labels.items()},
            "predicted_possessions": possessions,
            "graded_abstention_fraction": x_fraction,
            "short_prediction_run_fraction": short_fraction,
            "reason_counts": dict(sorted(self.reasons.items())),
            "operational_alerts": alerts,
        }


def peak_memory():
    """OS peak resident/working-set size for this process lifetime, not a sampled run peak."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t)
                    for name in (
                        "peak",
                        "working",
                        "peak_paged",
                        "paged",
                        "peak_nonpaged",
                        "nonpaged",
                        "pagefile",
                        "peak_pagefile",
                    )
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(Counters),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if not psapi.GetProcessMemoryInfo(
                kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            ):
                raise OSError
            value, method = counters.peak, "windows_peak_working_set"
        else:
            import resource

            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            value *= 1 if sys.platform == "darwin" else 1024
            method = "getrusage_maxrss"
        return {"bytes": int(value), "method": method, "scope": "process_lifetime_not_run_delta"}
    except (OSError, ImportError, AttributeError):
        return {"bytes": None, "method": "unavailable", "scope": "process_lifetime_not_run_delta"}
