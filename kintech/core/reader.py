from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from .exceptions import ChannelDefinitionError, HeaderFormatError, RecordParseError
from .models import ChannelDef, FileMetadata, ParsedFile, RawRecord
log = logging.getLogger(__name__)
EXPECTED_SIGNATURE = 'Kintech Engineering Atlas Output Data File'
_META_FIELD_ORDER = ['file_signature', 'format_version', 'timezone', 'date_format', 'list_separator', 'decimal_separator', 'field_separator', 'site_name', 'site_id', 'logger_serial', 'session_guid']

class KintechFileReader:

    def __init__(self, path: Union[str, Path], strict: bool=True):
        self.path = Path(path)
        self.strict = strict

    def parse(self) -> ParsedFile:
        log.debug('Opening %s', self.path)
        raw_text = self._read_text()
        lines = raw_text.splitlines()
        if len(lines) < 4:
            raise HeaderFormatError(f'Expected at least 4 header lines, file only has {len(lines)} lines total.')
        integrity_hash = self._parse_hash_line(lines[0])
        metadata, channels = self._parse_metadata_line(lines[1])
        short_headers, long_headers = self._parse_header_rows(lines[2], lines[3])
        self._reconcile_channels_with_headers(channels, long_headers)
        records = self._parse_data_rows(lines[4:], long_headers, start_line_no=5)
        if integrity_hash is not None:
            metadata = self._with_hash(metadata, integrity_hash)
        return ParsedFile(metadata=metadata, channels=channels, records=records, source_path=str(self.path), actual_columns=long_headers)

    def _read_text(self) -> str:
        try:
            return self.path.read_text(encoding='utf-8')
        except UnicodeDecodeError as exc:
            raise HeaderFormatError(f'File is not valid UTF-8 text ({exc}). Kintech Atlas .wnd files are text-based; a decode failure suggests this is not an Atlas file, or it is corrupted.') from exc

    @staticmethod
    def _with_hash(meta: FileMetadata, h: str) -> FileMetadata:
        meta.integrity_hash = h
        return meta

    def _parse_hash_line(self, line: str) -> Optional[str]:
        line = line.strip()
        if len(line) == 128 and all((c in '0123456789ABCDEFabcdef' for c in line)):
            log.debug('Line 0 looks like a 128-hex-char signature/checksum.')
            return line
        log.warning('Line 0 did not match the expected 128-hex-char signature pattern (got length %d). Continuing anyway since this field is not used for parsing, but the file may be non-standard.', len(line))
        return line or None

    def _parse_metadata_line(self, line: str):
        parts = line.split('#')
        if not parts or parts[0] != EXPECTED_SIGNATURE:
            if self.strict:
                raise HeaderFormatError(f'Line 1 does not start with the expected signature {EXPECTED_SIGNATURE!r}; got {parts[0]!r}. This file may not be a Kintech Atlas Output Data File.')
            log.warning('Unexpected file signature %r; proceeding in non-strict mode.', parts[0])
        if len(parts) < 12:
            raise HeaderFormatError(f"Expected at least 12 '#'-delimited metadata fields, found {len(parts)}.")
        meta_kwargs = {}
        for idx, attr in enumerate(_META_FIELD_ORDER):
            meta_kwargs[attr] = parts[idx] if idx < len(parts) else ''
        metadata = FileMetadata(**meta_kwargs)
        channels_json = parts[11]
        channels = self._parse_channel_json(channels_json)
        return (metadata, channels)

    def _parse_channel_json(self, channels_json: str) -> List[ChannelDef]:
        channels_json = channels_json.strip()
        if not channels_json:
            raise ChannelDefinitionError('Channel definition field (expected JSON array) is empty.')
        try:
            raw_channels = json.loads(channels_json)
        except json.JSONDecodeError as exc:
            raise ChannelDefinitionError(f'Could not parse channel definitions as JSON: {exc}') from exc
        if not isinstance(raw_channels, list) or not raw_channels:
            raise ChannelDefinitionError('Channel definition JSON did not contain a non-empty array.')
        channels: List[ChannelDef] = []
        for entry in raw_channels:
            try:
                prefix = entry['ColumnPrefix']
                channels.append(ChannelDef(column_prefix=prefix, channel_number=int(entry['ChannelNumber']), name=entry['Name'], units=entry.get('Units', ''), height_m=float(entry.get('Height', 0.0)), orientation_deg=float(entry.get('Orientation', 0.0)), magnitude=int(entry.get('Magnitude', 0)), slope=float(entry.get('Slope', 1.0)), offset=float(entry.get('Offset', 0.0)), is_frequency=prefix.upper().startswith('FRQ')))
            except (KeyError, TypeError, ValueError) as exc:
                raise ChannelDefinitionError(f'Malformed channel definition entry {entry!r}: {exc}') from exc
        channels.sort(key=lambda c: c.channel_number)
        log.debug('Parsed %d channel definitions from header JSON.', len(channels))
        return channels

    def _parse_header_rows(self, short_line: str, long_line: str):
        short_headers = short_line.strip().split(' ')
        long_headers = long_line.strip().split(' ')
        if short_headers[0] != 'DateTime' or long_headers[0] != 'DateTime':
            raise HeaderFormatError(f"Expected both header rows (lines 3 and 4) to start with the 'DateTime' column; got {short_headers[0]!r} / {long_headers[0]!r}.")
        if len(short_headers) != len(long_headers):
            raise HeaderFormatError(f'Header row column-count mismatch: short header has {len(short_headers)} columns, long header has {len(long_headers)}.')
        log.debug('Header rows parsed: %d logical columns.', len(long_headers))
        return (short_headers, long_headers)

    def _reconcile_channels_with_headers(self, channels: List[ChannelDef], long_headers: List[str]) -> None:

        def _norm(s: str) -> str:
            return s.replace(' ', '_').lower()
        header_set = set(long_headers)
        norm_header_lookup: Dict[str, str] = {}
        for h in long_headers:
            if any((h.endswith(suf) for suf in ('-STDev', '-Min', '-Max', '-TI30'))):
                continue
            norm_header_lookup[_norm(h)] = h
        missing = []
        for ch in channels:
            if ch.name in header_set:
                resolved = ch.name
            else:
                resolved = norm_header_lookup.get(_norm(ch.name))
                if resolved is None:
                    missing.append(ch.name)
                    continue
                log.warning("Channel name %r from JSON header did not exactly match any column header; matched by normalization to %r instead. The file's JSON metadata and column headers disagree on this sensor's exact name (a known real-world inconsistency in this format) - using the column header's spelling for all data lookups.", ch.name, resolved)
                ch.name = resolved
            ch.has_ti30 = f'{resolved}-TI30' in header_set
        if missing:
            raise ChannelDefinitionError(f'The following channels declared in the JSON header were not found in the column header row (even after space/underscore normalization): {missing}. The file may use a channel-definition format this parser does not yet support.')
        declared_cols = {'DateTime'}
        for ch in channels:
            declared_cols.update(ch.stat_columns)
        unmapped = [h for h in long_headers if h not in declared_cols]
        if unmapped:
            log.warning("Header row has %d column(s) not traceable to any declared channel: %s. These will be preserved in 'raw' output format under their literal header names but are NOT included in 'windographer' style output unless explicitly mapped.", len(unmapped), unmapped)

    def _parse_data_rows(self, data_lines: List[str], long_headers: List[str], start_line_no: int) -> List[RawRecord]:
        records: List[RawRecord] = []
        value_cols = long_headers[1:]
        for offset, raw_line in enumerate(data_lines):
            line_no = start_line_no + offset
            line = raw_line.rstrip('\r\n')
            if not line.strip():
                continue
            try:
                record = self._parse_one_row(line, value_cols, line_no)
            except RecordParseError as exc:
                if self.strict:
                    raise
                log.warning('Skipping unparsable row: %s', exc)
                continue
            records.append(record)
        log.debug('Parsed %d data rows.', len(records))
        return records

    @staticmethod
    def _parse_one_row(line: str, value_cols: List[str], line_no: int) -> RawRecord:
        if ',' not in line:
            raise RecordParseError(line_no, line, "Missing ',' between date and time fields.")
        date_part, rest = line.split(',', 1)
        tokens = rest.split(' ')
        if len(tokens) < 1:
            raise RecordParseError(line_no, line, 'Row has no time/value tokens after the comma.')
        time_part = tokens[0]
        value_tokens = tokens[1:]
        if len(value_tokens) != len(value_cols):
            raise RecordParseError(line_no, line, f'Expected {len(value_cols)} data values, found {len(value_tokens)}.')
        try:
            timestamp = datetime.strptime(f'{date_part} {time_part}', '%Y-%m-%d %H:%M')
        except ValueError as exc:
            raise RecordParseError(line_no, line, f"Could not parse timestamp '{date_part} {time_part}': {exc}") from exc
        values: Dict[str, Optional[float]] = {}
        for col_name, tok in zip(value_cols, value_tokens):
            values[col_name] = _parse_numeric(tok)
        return RawRecord(timestamp=timestamp, values=values, line_number=line_no)

def _parse_numeric(token: str) -> Optional[float]:
    if token == '':
        return None
    try:
        return float(token)
    except ValueError:
        log.debug('Non-numeric token %r encountered; treating as missing.', token)
        return None