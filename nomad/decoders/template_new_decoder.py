from __future__ import annotations
from datetime import datetime
from typing import Optional
from decoders.base_decoder import BaseLoggerDecoder
from parsers.metadata_parser import LoggerInfo, LoggerMetadata
from parsers.record_parser import RecordStream

class TemplateNewDecoder(BaseLoggerDecoder):
    format_name = 'template_new_format'
    typical_extensions = ()

    def sniff(self, data: bytes) -> bool:
        return False

    def parse_metadata(self, data: bytes) -> LoggerMetadata:
        return LoggerMetadata(logger_info=LoggerInfo(logger_model=self.format_name))

    def parse_records(self, data: bytes, metadata: LoggerMetadata, start_time: Optional[datetime]=None, interval_minutes: Optional[int]=None) -> RecordStream:
        raise NotImplementedError('Template decoder: implement parse_records() for the real format.')