from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

@dataclass
class TimeIndexConfig:
    start_time: datetime
    interval: timedelta
    count: int
    timezone_label: Optional[str] = None

    def generate(self) -> List[datetime]:
        return [self.start_time + i * self.interval for i in range(self.count)]

def uniform_time_index(start_time: datetime, interval_minutes: int, count: int, timezone_label: Optional[str]=None) -> List[datetime]:
    cfg = TimeIndexConfig(start_time=start_time, interval=timedelta(minutes=interval_minutes), count=count, timezone_label=timezone_label)
    return cfg.generate()

def infer_interval_minutes(sample_timestamps: List[datetime]) -> Optional[int]:
    if len(sample_timestamps) < 2:
        return None
    deltas = {sample_timestamps[i + 1] - sample_timestamps[i] for i in range(len(sample_timestamps) - 1)}
    if len(deltas) != 1:
        return None
    only_delta = next(iter(deltas))
    minutes = only_delta.total_seconds() / 60
    if minutes != int(minutes):
        return None
    return int(minutes)