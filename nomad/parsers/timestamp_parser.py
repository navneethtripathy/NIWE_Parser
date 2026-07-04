"""
timestamp_parser.py
---------------------
Timestamp handling for logger record streams.

IMPORTANT REVERSE-ENGINEERING FINDING (Nomad NDF, this file):
We searched exhaustively for a per-scan or per-record timestamp field
encoded in the binary and did not find one. Every data record shares the
same fixed 4-byte "session" constant, and the field that does vary
per-record was confirmed (by direct comparison against the reference
Windographer export) to be a non-temporal value -- most likely a per-sample
checksum/hash, not a clock value. The file's 64-byte preamble record also
contains no field that decodes to a sensible 2012-era date under any
standard epoch we tried (Unix seconds, Unix ms, common logger epochs).

Conclusion: this particular .ndf file format relies on an *external*
start timestamp plus a *fixed, uniform sampling interval* (here, 10
minutes, confirmed exactly against 125 consecutive reference rows with zero
gaps) to reconstruct the time axis. This module supports that workflow
explicitly, while leaving room for future decoders (or a later, deeper
pass on Nomad firmware) to supply a true decoded-from-bytes timestamp
instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass
class TimeIndexConfig:
    """Describes how to reconstruct timestamps for a record stream that has
    no embedded per-record clock value."""
    start_time: datetime
    interval: timedelta
    count: int
    timezone_label: Optional[str] = None  # informational only, e.g. "UTC+05:30"

    def generate(self) -> List[datetime]:
        return [self.start_time + i * self.interval for i in range(self.count)]


def uniform_time_index(start_time: datetime, interval_minutes: int, count: int,
                        timezone_label: Optional[str] = None) -> List[datetime]:
    """Build a uniform timestamp index. This is the supported path for the
    Nomad NDF decoder as implemented: no timestamp bytes were found in the
    file, so the caller must supply (or the calling code must obtain from a
    companion export / user input) the true start time."""
    cfg = TimeIndexConfig(
        start_time=start_time,
        interval=timedelta(minutes=interval_minutes),
        count=count,
        timezone_label=timezone_label,
    )
    return cfg.generate()


def infer_interval_minutes(sample_timestamps: List[datetime]) -> Optional[int]:
    """Given at least two known timestamps (e.g. from a reference export),
    infer the sampling interval in whole minutes. Returns None if the
    timestamps are not uniformly spaced."""
    if len(sample_timestamps) < 2:
        return None
    deltas = {
        (sample_timestamps[i + 1] - sample_timestamps[i])
        for i in range(len(sample_timestamps) - 1)
    }
    if len(deltas) != 1:
        return None
    only_delta = next(iter(deltas))
    minutes = only_delta.total_seconds() / 60
    if minutes != int(minutes):
        return None
    return int(minutes)
