from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from parsers.metadata_parser import SensorDefinition

@dataclass
class ChannelSlot:
    slot_index: int
    sensor: SensorDefinition
    statistic: str
    windographer_name: Optional[str] = None
    frequency_group: str = '10min'

    @property
    def column_name(self) -> str:
        base = self.sensor.display_name
        if self.statistic == 'Avg':
            return base
        return f'{base}_{self.statistic}'

@dataclass
class RecordStream:
    timestamps: List[datetime]
    values: List[List[float]]
    slots: List[ChannelSlot]
    interval_minutes: Optional[int] = None
    source_file: Optional[str] = None
    records_per_scan: Optional[int] = None
    bytes_per_record: Optional[int] = None
    data_region_offset: Optional[int] = None
    layout_name: Optional[str] = None
    layout_confirmed: Optional[bool] = None
    timezone_label: Optional[str] = None
    windographer_column_order: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.values and len(self.values[0]) != len(self.slots):
            raise ValueError(f'RecordStream inconsistency: {len(self.slots)} slots defined but rows have {len(self.values[0])} values.')
        if len(self.timestamps) != len(self.values):
            raise ValueError(f'RecordStream inconsistency: {len(self.timestamps)} timestamps but {len(self.values)} value rows.')

    @property
    def num_scans(self) -> int:
        return len(self.timestamps)

    def _resolved_column_names(self) -> List[str]:
        raw_names = [slot.column_name for slot in self.slots]
        from collections import Counter
        counts = Counter(raw_names)
        resolved = []
        for slot, name in zip(self.slots, raw_names):
            if counts[name] > 1 and slot.sensor.serial_number:
                resolved.append(f'{name}_SN{slot.sensor.serial_number}')
            else:
                resolved.append(name)
        final_counts = Counter(resolved)
        seen: Dict[str, int] = {}
        out = []
        for name in resolved:
            if final_counts[name] > 1:
                seen[name] = seen.get(name, 0) + 1
                out.append(f'{name}_{seen[name]}')
            else:
                out.append(name)
        return out

    def column_names(self) -> List[str]:
        return self._resolved_column_names()

    def to_long_rows(self):
        names = self._resolved_column_names()
        for row_idx, ts in enumerate(self.timestamps):
            row = self.values[row_idx]
            for slot, name in zip(self.slots, names):
                value = row[slot.slot_index]
                unit = slot.sensor.unit
                yield (ts, name, value, unit)

    def to_wide_dict(self) -> Dict[str, list]:
        names = self._resolved_column_names()
        result: Dict[str, list] = {'Timestamp': list(self.timestamps)}
        for slot, name in zip(self.slots, names):
            result[name] = [row[slot.slot_index] for row in self.values]
        return result