from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from parsers.metadata_parser import LoggerMetadata
from parsers.record_parser import RecordStream

class BaseLoggerDecoder(ABC):
    format_name: str = 'base'
    typical_extensions: tuple = ()

    @abstractmethod
    def sniff(self, data: bytes) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse_metadata(self, data: bytes) -> LoggerMetadata:
        raise NotImplementedError

    @abstractmethod
    def parse_records(self, data: bytes, metadata: LoggerMetadata, start_time=None, interval_minutes: Optional[int]=None) -> RecordStream:
        raise NotImplementedError

    def describe_findings(self, data: bytes) -> str:
        return f"No findings report implemented for format '{self.format_name}'."

    @classmethod
    def from_file(cls, path: Path) -> bytes:
        return Path(path).read_bytes()