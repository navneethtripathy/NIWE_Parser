from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class ChannelDef:
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
        cols = [self.name, f'{self.name}-STDev', f'{self.name}-Min', f'{self.name}-Max']
        if self.has_ti30:
            cols.append(f'{self.name}-TI30')
        return cols

@dataclass
class FileMetadata:
    file_signature: str
    format_version: str
    timezone: str
    date_format: str
    list_separator: str
    decimal_separator: str
    field_separator: str
    site_name: str
    site_id: str
    logger_serial: str
    session_guid: str
    integrity_hash: Optional[str] = None

@dataclass
class RawRecord:
    timestamp: datetime
    values: Dict[str, Optional[float]] = field(default_factory=dict)
    line_number: int = -1

@dataclass
class ParsedFile:
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