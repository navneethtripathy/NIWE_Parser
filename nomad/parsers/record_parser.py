"""
record_parser.py
-------------------
Generic, format-agnostic representation of a decoded logger record stream.

A decoder (e.g. NomadNDFDecoder) is responsible for turning raw bytes into
a `RecordStream`: a list of timestamps paired with a 2D array of per-channel
float values, plus a mapping from "slot index in the raw stream" to
"SensorDefinition" so the exporter can label every column correctly.

Keeping this layer generic is what lets exporters/excel_exporter.py and
main.py work identically for Nomad, Campbell, Ammonit, Kintech, or Second
Wind data, once each has its own decoder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from parsers.metadata_parser import SensorDefinition


@dataclass
class ChannelSlot:
    """Maps one position in the raw per-scan value array to a sensor and a
    statistic type (Average / StdDev / Gust / TimeOfMax / TimeOfMin /
    Sample / Raw)."""
    slot_index: int
    sensor: SensorDefinition
    statistic: str   # "Avg", "SD", "Gust", "TimeOfMax", "TimeOfMin", "Sample", "Raw"
    windographer_name: Optional[str] = None  # exact Windographer column name; None = not exported
    frequency_group: str = "10min" # "10min" or "1min"

    @property
    def column_name(self) -> str:
        base = self.sensor.display_name
        if self.statistic == "Avg":
            return base
        return f"{base}_{self.statistic}"


@dataclass
class RecordStream:
    """The fully decoded record stream: one row per scan, one column per
    ChannelSlot."""
    timestamps: List[datetime]
    values: List[List[float]]            # values[row][slot_index]
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
            raise ValueError(
                f"RecordStream inconsistency: {len(self.slots)} slots defined "
                f"but rows have {len(self.values[0])} values."
            )
        if len(self.timestamps) != len(self.values):
            raise ValueError(
                f"RecordStream inconsistency: {len(self.timestamps)} timestamps "
                f"but {len(self.values)} value rows."
            )

    @property
    def num_scans(self) -> int:
        return len(self.timestamps)

    def _resolved_column_names(self) -> List[str]:
        """Compute column names with duplicates disambiguated.

        CONFIRMED real-world case (Rojmal-2 file): two anemometers can
        share the same height (two booms at 80m, pointed in different
        directions -- SE and NW) and would otherwise produce an identical
        'WindSpeed_80m' column name for both. When a collision is
        detected, the sensor's serial number (always unique) is appended
        to every colliding name so no data is silently overwritten/lost
        in wide-format export.
        """
        raw_names = [slot.column_name for slot in self.slots]
        from collections import Counter
        counts = Counter(raw_names)
        resolved = []
        for slot, name in zip(self.slots, raw_names):
            if counts[name] > 1 and slot.sensor.serial_number:
                resolved.append(f"{name}_SN{slot.sensor.serial_number}")
            else:
                resolved.append(name)
        # If serial-number suffixing still left duplicates (e.g. no serial
        # available), fall back to a numeric suffix as a last resort so
        # columns are never silently merged.
        final_counts = Counter(resolved)
        seen: Dict[str, int] = {}
        out = []
        for name in resolved:
            if final_counts[name] > 1:
                seen[name] = seen.get(name, 0) + 1
                out.append(f"{name}_{seen[name]}")
            else:
                out.append(name)
        return out

    def column_names(self) -> List[str]:
        return self._resolved_column_names()

    def to_long_rows(self):
        """Yield (timestamp, channel_name, value, unit) tuples -- the 'long'
        / tidy format requested for Excel export."""
        names = self._resolved_column_names()
        for row_idx, ts in enumerate(self.timestamps):
            row = self.values[row_idx]
            for slot, name in zip(self.slots, names):
                value = row[slot.slot_index]
                unit = slot.sensor.unit
                yield ts, name, value, unit

    def to_wide_dict(self) -> Dict[str, list]:
        """Return a dict suitable for pandas.DataFrame(...) in wide format:
        {'Timestamp': [...], 'WindSpeed_80m': [...], ...}"""
        names = self._resolved_column_names()
        result: Dict[str, list] = {"Timestamp": list(self.timestamps)}
        for slot, name in zip(self.slots, names):
            result[name] = [row[slot.slot_index] for row in self.values]
        return result
