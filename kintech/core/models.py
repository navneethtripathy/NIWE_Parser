"""Data model for a parsed Kintech Atlas (.wnd) file.

These are plain dataclasses with no parsing logic of their own - all
parsing lives in reader.py. Keeping the model separate from the reader
makes it straightforward to plug in a different logger format later
(Campbell, Ammonit, Second Wind, ...) that produces the same model shape,
which is the same plugin-registry pattern used elsewhere in this project's
universal logger-decoder system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ChannelDef:
    """One physical sensor channel, as declared in the embedded JSON
    channel-definition block in the file header.

    Attributes
    ----------
    column_prefix:
        The short slot name used in the file's "short" header row,
        e.g. ``"FRQ(1)"`` or ``"ANL(3)"``.
    channel_number:
        Logger-internal channel index (0-based for frequency channels,
        continuing upward for analog channels in this format revision).
    name:
        Descriptive sensor name from the "long" header row, e.g.
        ``"F1_WS_100_0_TFCA"``. Encodes sensor type (WS/WD/PR/RAD/V),
        height in metres, and orientation in degrees by convention,
        but this parser never parses that sub-structure - it only uses
        `name` as an opaque column-matching key, since the convention
        is logger-configuration-specific and not guaranteed stable.
    units:
        Engineering unit string from the channel definition (e.g. "m/s").
    height_m:
        Sensor mounting height in metres, as declared by the logger
        configuration (not re-derived from `name`).
    orientation_deg:
        Boom/sensor orientation in degrees, as declared.
    magnitude:
        Logger-internal scaling magnitude/exponent field. Present in the
        source JSON but NOT used by this parser: empirically, the data
        rows in the .wnd file already contain post-slope/offset
        engineering-unit values (see REVERSE_ENGINEERING_REPORT.md,
        "Are values pre-scaled?"). Retained here for completeness/future
        formats where it may matter.
    slope / offset:
        Linear calibration coefficients (engineering_value = raw*slope +
        offset). Confirmed against physical sensor calibration
        certificates during reverse engineering. NOT re-applied by this
        parser's default pipeline since the .wnd values are already
        scaled; exposed so a future raw-counts format variant could
        reuse this model and apply them.
    is_frequency:
        True for FRQ(n) channels (typically anemometers/pressure wired
        as frequency-output sensors), False for ANL(n) / Battery
        channels (analog voltage-output sensors, direction vanes,
        pyranometers, battery monitor).
    has_ti30:
        True if this channel has a logger-computed "-TI30" turbulence
        intensity column in the data rows. Confirmed: present only for
        the two 100 m anemometer channels in the analyzed sample; NOT
        assumed true for every frequency channel.
    """

    column_prefix: str
    channel_number: int
    name: str
    units: str
    height_m: float
    orientation_deg: float
    magnitude: int
    slope: float
    offset: float
    is_frequency: bool
    has_ti30: bool = False

    @property
    def stat_columns(self) -> List[str]:
        """Logical column-name suffixes this channel contributes to the
        data rows, in on-disk order: Avg, STDev, Min, Max, [TI30]."""
        cols = [self.name, f"{self.name}-STDev", f"{self.name}-Min", f"{self.name}-Max"]
        if self.has_ti30:
            cols.append(f"{self.name}-TI30")
        return cols


@dataclass
class FileMetadata:
    """Header metadata from line 1 of the .wnd file (the '#'-delimited
    record preceding the JSON channel array)."""

    file_signature: str  # e.g. "Kintech Engineering Atlas Output Data File"
    format_version: str  # e.g. "2.0.0.342"
    timezone: str  # e.g. "UTC+00:00:00"
    date_format: str  # e.g. "yyyy/MM/dd" (declared; actual data rows use yyyy-MM-dd, see report)
    list_separator: str  # e.g. ","
    decimal_separator: str  # e.g. "."
    field_separator: str  # e.g. " "
    site_name: str  # e.g. "Narendra-IWSKA8"
    site_id: str  # e.g. "150008"
    logger_serial: str  # e.g. "9571112094"
    session_guid: str
    integrity_hash: Optional[str] = None  # line 0; algorithm unconfirmed, see report


@dataclass
class RawRecord:
    """One native-resolution data row exactly as stored on disk, before
    any resampling/derived-column computation."""

    timestamp: datetime
    values: Dict[str, Optional[float]] = field(default_factory=dict)
    line_number: int = -1


@dataclass
class ParsedFile:
    """Top-level container returned by KintechFileReader.parse()."""

    metadata: FileMetadata
    channels: List[ChannelDef]
    records: List[RawRecord]
    source_path: str

    actual_columns: List[str] = field(default_factory=list)

    def channel_by_name(self, name: str) -> Optional[ChannelDef]:
        for c in self.channels:
            if c.name == name:
                return c
        return None
