from __future__ import annotations
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from decoders.base_decoder import BaseLoggerDecoder
from parsers.metadata_parser import LoggerInfo, LoggerMetadata, SensorDefinition
from parsers.record_parser import ChannelSlot, RecordStream
from parsers.timestamp_parser import uniform_time_index
PREAMBLE_OFFSET = 0
PREAMBLE_LENGTH = 64
CHANNEL_TABLE_OFFSET = 64
EXTERNAL_SENSOR_RECORD_LEN = 88
INTERNAL_CHANNEL_RECORD_LEN = 68
INTERNAL_CHANNEL_TAG = b'\xd4\x01'
STUB_RECORD_TAG = b'\xd7\x01'
STUB_RECORD_LEN = 24
DATA_RECORD_TAG = b'\xd8\x01'
DATA_RECORD_LEN = 16
DEFAULT_START_TIME = datetime(2012, 3, 13, 3, 10, 0)
DEFAULT_INTERVAL_MINUTES = 10

@dataclass
class SlotMapping:
    slot_index: int
    channel_index: Optional[int]
    statistic: str
    windographer_name: Optional[str] = None
    frequency_group: str = '10min'

@dataclass
class DeploymentLayout:
    name: str
    fingerprint: tuple
    slot_layout: List[SlotMapping]
    timezone_label: Optional[str] = None
    default_start_time: Optional[datetime] = None
    sampling_interval_minutes: Optional[int] = None
    windographer_column_order: Optional[List[str]] = None

def _fingerprint_channels(data: bytes, stub_start: int, stub_count: int) -> tuple:
    from collections import Counter
    counts = Counter()
    for i in range(stub_count):
        off = stub_start + i * STUB_RECORD_LEN
        rec = data[off:off + STUB_RECORD_LEN]
        if len(rec) < STUB_RECORD_LEN:
            break
        chan = rec[8]
        counts[chan] += 1
    return tuple(sorted(counts.items()))
SOMAGUDDA_460_LAYOUT = DeploymentLayout(name='somagudda_460_serial_8772', fingerprint=((0, 7), (1, 7), (2, 7), (3, 7), (16, 6), (17, 6), (18, 6), (19, 7)), default_start_time=datetime(2012, 3, 13, 3, 10, 0), sampling_interval_minutes=10, timezone_label='UTC+05:30', slot_layout=[SlotMapping(0, 0, 'Avg', 'Spd 80m S [m/s]'), SlotMapping(1, 0, 'SD', 'Spd 80m S SD [m/s]'), SlotMapping(2, 0, 'Gust', 'Spd 80m S Gust [m/s]'), SlotMapping(3, 0, 'TimeOfMax', 'C1-SWI C3 TimeOfMax [m/s]'), SlotMapping(4, 0, 'Raw1', None), SlotMapping(5, 0, 'TimeOfMin', 'C1-SWI C3 TimeOfMin [m/s]'), SlotMapping(6, 0, 'Sample', 'C1-SWI C3 Sample [m/s]'), SlotMapping(7, 1, 'Avg', 'Spd 78m S [m/s]'), SlotMapping(8, 1, 'SD', 'Spd 78m S SD [m/s]'), SlotMapping(9, 1, 'Gust', 'Spd 78m S Gust [m/s]'), SlotMapping(10, 1, 'TimeOfMax', 'C2-SWI C3 TimeOfMax [m/s]'), SlotMapping(11, 1, 'Raw1', None), SlotMapping(12, 1, 'TimeOfMin', 'C2-SWI C3 TimeOfMin [m/s]'), SlotMapping(13, 1, 'Sample', 'C2-SWI C3 Sample [m/s]'), SlotMapping(14, 2, 'Avg', 'Spd 50m S [m/s]'), SlotMapping(15, 2, 'SD', 'Spd 50m S SD [m/s]'), SlotMapping(16, 2, 'Gust', 'Spd 50m S Gust [m/s]'), SlotMapping(17, 2, 'TimeOfMax', 'C3-SWI C3 TimeOfMax [m/s]'), SlotMapping(18, 2, 'Raw1', None), SlotMapping(19, 2, 'TimeOfMin', 'C3-SWI C3 TimeOfMin [m/s]'), SlotMapping(20, 2, 'Sample', 'C3-SWI C3 Sample [m/s]'), SlotMapping(21, 3, 'Avg', 'Spd 20m S [m/s]'), SlotMapping(22, 3, 'SD', 'Spd 20m S SD [m/s]'), SlotMapping(23, 3, 'Gust', 'Spd 20m S Gust [m/s]'), SlotMapping(24, 3, 'TimeOfMax', 'C4-SWI C3 TimeOfMax [m/s]'), SlotMapping(25, 3, 'Raw1', None), SlotMapping(26, 3, 'TimeOfMin', 'C4-SWI C3 TimeOfMin [m/s]'), SlotMapping(27, 3, 'Sample', 'C4-SWI C3 Sample [m/s]'), SlotMapping(28, 16, 'Avg', 'Dir 80m N [°]'), SlotMapping(29, 16, 'SD', 'Dir 80m N SD [°]'), SlotMapping(30, 16, 'Raw1', None), SlotMapping(31, 16, 'TimeOfMax', 'A5-SWI PV1 TimeOfMax [°]'), SlotMapping(32, 16, 'Raw2', None), SlotMapping(33, 16, 'TimeOfMin', 'A5-SWI PV1 TimeOfMin [°]'), SlotMapping(34, 17, 'Avg', 'Dir 50m N [°]'), SlotMapping(35, 17, 'SD', 'Dir 50m N SD [°]'), SlotMapping(36, 17, 'Raw1', None), SlotMapping(37, 17, 'TimeOfMax', 'A6-SWI PV1 TimeOfMax [°]'), SlotMapping(38, 17, 'Raw2', None), SlotMapping(39, 17, 'TimeOfMin', 'A6-SWI PV1 TimeOfMin [°]'), SlotMapping(40, 18, 'Avg', 'Tmp 10m [°C]'), SlotMapping(41, 18, 'Raw1', None), SlotMapping(42, 18, 'Raw2', None), SlotMapping(43, 18, 'TimeOfMax', 'A7-SWI 10k Probe TimeOfMax [°C]'), SlotMapping(44, 18, 'Raw3', None), SlotMapping(45, 18, 'TimeOfMin', 'A7-SWI 10k Probe TimeOfMin [°C]'), SlotMapping(46, 19, 'Avg', 'A8-Insolation Avg'), SlotMapping(47, 19, 'SD', 'A8-Insolation StdDev'), SlotMapping(48, 19, 'Raw1', None), SlotMapping(49, 19, 'TimeOfMax', 'A8-Insolation TimeOfMax'), SlotMapping(50, 19, 'Raw2', None), SlotMapping(51, 19, 'TimeOfMin', 'A8-Insolation TimeOfMin'), SlotMapping(52, 19, 'Sample', 'A8-Insolation Sample')], windographer_column_order=['Spd 80m S [m/s]', 'Spd 80m S SD [m/s]', 'Spd 80m S Gust [m/s]', 'Spd 78m S [m/s]', 'Spd 78m S SD [m/s]', 'Spd 78m S Gust [m/s]', 'Spd 50m S [m/s]', 'Spd 50m S SD [m/s]', 'Spd 50m S Gust [m/s]', 'Spd 20m S [m/s]', 'Spd 20m S SD [m/s]', 'Spd 20m S Gust [m/s]', 'Dir 80m N [°]', 'Dir 80m N SD [°]', 'Dir 50m N [°]', 'Dir 50m N SD [°]', 'Tmp 10m [°C]', 'C1-SWI C3 TimeOfMax [m/s]', 'C1-SWI C3 TimeOfMin [m/s]', 'C1-SWI C3 Sample [m/s]', 'A5-SWI PV1 TimeOfMax [°]', 'A5-SWI PV1 TimeOfMin [°]', 'C2-SWI C3 TimeOfMax [m/s]', 'C2-SWI C3 TimeOfMin [m/s]', 'C2-SWI C3 Sample [m/s]', 'C3-SWI C3 TimeOfMax [m/s]', 'C3-SWI C3 TimeOfMin [m/s]', 'C3-SWI C3 Sample [m/s]', 'A6-SWI PV1 TimeOfMax [°]', 'A6-SWI PV1 TimeOfMin [°]', 'C4-SWI C3 TimeOfMax [m/s]', 'C4-SWI C3 TimeOfMin [m/s]', 'C4-SWI C3 Sample [m/s]', 'A7-SWI 10k Probe TimeOfMax [°C]', 'A7-SWI 10k Probe TimeOfMin [°C]', 'A8-Insolation Avg', 'A8-Insolation TimeOfMax', 'A8-Insolation TimeOfMin', 'A8-Insolation Sample', 'A8-Insolation StdDev'])
assert len(SOMAGUDDA_460_LAYOUT.slot_layout) == 53
ROJMAL_2_LAYOUT = DeploymentLayout(name='rojmal_2_serial_9601', fingerprint=((0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (16, 2), (19, 2), (20, 1), (21, 1), (22, 1), (32, 1), (33, 1), (34, 1), (35, 1)), timezone_label='UTC+05:30', default_start_time=datetime(2010, 12, 2, 0, 0, 0), sampling_interval_minutes=10, windographer_column_order=['Spd 80m SE [m/s]', 'Spd 80m SE SD [m/s]', 'Spd 80m SE Gust [m/s]', 'Spd 80m NW [m/s]', 'Spd 80m NW SD [m/s]', 'Spd 80m NW Gust [m/s]', 'Spd 65m SE [m/s]', 'Spd 65m SE SD [m/s]', 'Spd 65m SE Gust [m/s]', 'Spd 50m SE [m/s]', 'Spd 50m SE SD [m/s]', 'Spd 50m SE Gust [m/s]', 'Spd 33.5m SE [m/s]', 'Spd 33.5m SE SD [m/s]', 'Spd 33.5m SE Gust [m/s]', 'Dir 78m SE [°]', 'Dir 48m SE [°]', 'Dir 48m SE SD [°]', 'Tmp 5m [°C]', 'Tmp 2m [°C]', 'BattV A [V]', 'BattV B [V]', 'BattV C [V]', 'A9-Setra 276 Avg [mbar]', 'A10-Humidity Avg [%]'], slot_layout=[*(SlotMapping(i, 19, f'VectorStdDev_1min_sample{i + 1}', 'A6-NRG 200P VectorStdDev [°]', '1min') for i in range(10)), SlotMapping(10, 0, 'Avg', 'Spd 80m SE [m/s]'), SlotMapping(11, 0, 'SD', 'Spd 80m SE SD [m/s]'), SlotMapping(12, 0, 'Gust', 'Spd 80m SE Gust [m/s]'), SlotMapping(13, 1, 'Avg', 'Spd 80m NW [m/s]'), SlotMapping(14, 1, 'SD', 'Spd 80m NW SD [m/s]'), SlotMapping(15, 1, 'Gust', 'Spd 80m NW Gust [m/s]'), SlotMapping(16, 2, 'Avg', 'Spd 65m SE [m/s]'), SlotMapping(17, 2, 'SD', 'Spd 65m SE SD [m/s]'), SlotMapping(18, 2, 'Gust', 'Spd 65m SE Gust [m/s]'), SlotMapping(19, 3, 'Avg', 'Spd 50m SE [m/s]'), SlotMapping(20, 3, 'SD', 'Spd 50m SE SD [m/s]'), SlotMapping(21, 3, 'Gust', 'Spd 50m SE Gust [m/s]'), SlotMapping(22, 4, 'Avg', 'Spd 33.5m SE [m/s]'), SlotMapping(23, 4, 'SD', 'Spd 33.5m SE SD [m/s]'), SlotMapping(24, 4, 'Gust', 'Spd 33.5m SE Gust [m/s]'), SlotMapping(25, 16, 'Avg', 'Dir 78m SE [°]'), SlotMapping(26, 19, 'Avg', 'Dir 48m SE [°]'), SlotMapping(27, 19, 'SD', 'Dir 48m SE SD [°]'), SlotMapping(28, 20, 'Avg', 'Tmp 5m [°C]'), SlotMapping(29, 21, 'Avg', 'A9-Setra 276 Avg [mbar]'), SlotMapping(30, 22, 'Avg', 'A10-Humidity Avg [%]'), SlotMapping(31, 32, 'Avg', 'Tmp 2m [°C]'), SlotMapping(32, 33, 'Avg', 'BattV A [V]'), SlotMapping(33, 34, 'Avg', 'BattV B [V]'), SlotMapping(34, 35, 'Avg', 'BattV C [V]')])
assert len(ROJMAL_2_LAYOUT.slot_layout) == 35
KNOWN_DEPLOYMENT_LAYOUTS: List[DeploymentLayout] = [SOMAGUDDA_460_LAYOUT, ROJMAL_2_LAYOUT]

class NomadNDFDecoder(BaseLoggerDecoder):
    format_name = 'nomad_ndf'
    typical_extensions = ('.ndf',)

    def sniff(self, data: bytes) -> bool:
        if len(data) < PREAMBLE_LENGTH + DATA_RECORD_LEN:
            return False
        if data[0:2] != b'\xd1\x02':
            return False
        idx = data.find(DATA_RECORD_TAG, CHANNEL_TABLE_OFFSET)
        if idx == -1:
            return False
        return True

    def parse_metadata(self, data: bytes) -> LoggerMetadata:
        logger_info = self._parse_preamble(data)
        sensors = self._parse_channel_table(data, logger_info.serial_number)
        return LoggerMetadata(logger_info=logger_info, sensors=sensors)

    def _parse_preamble(self, data: bytes) -> LoggerInfo:
        chunk = data[PREAMBLE_OFFSET:PREAMBLE_OFFSET + PREAMBLE_LENGTH]
        serial = struct.unpack('<I', chunk[8:12])[0]
        build_id_1 = struct.unpack('<I', chunk[12:16])[0]
        build_id_2 = struct.unpack('<I', chunk[16:20])[0]
        elevation = struct.unpack('<f', chunk[20:24])[0]
        text_region = chunk[28:]
        text = text_region.split(b'\x00')[0].split(b'\xff')[0]
        raw_site_text = text.decode('ascii', errors='replace').strip()
        tokens = raw_site_text.split()
        while tokens and len(tokens[0]) <= 2:
            tokens.pop(0)
        site_name = ' '.join(tokens) if tokens else raw_site_text
        return LoggerInfo(logger_model='Nomad', serial_number=str(serial), site_name=site_name, elevation_m=elevation, firmware_or_build_ids=[build_id_1, build_id_2], raw_preamble_offset=PREAMBLE_OFFSET, raw_preamble_length=PREAMBLE_LENGTH)

    def _parse_channel_table(self, data: bytes, logger_serial: Optional[str]) -> List[SensorDefinition]:
        sensors: List[SensorDefinition] = []
        offset = CHANNEL_TABLE_OFFSET
        while offset < len(data):
            tag = data[offset:offset + 2]
            if tag == INTERNAL_CHANNEL_TAG:
                rec = data[offset:offset + INTERNAL_CHANNEL_RECORD_LEN]
                if len(rec) < INTERNAL_CHANNEL_RECORD_LEN:
                    break
                sensor = self._parse_internal_channel_record(rec, offset)
                sensors.append(sensor)
                offset += INTERNAL_CHANNEL_RECORD_LEN
                continue
            if tag == STUB_RECORD_TAG:
                break
            rec = data[offset:offset + EXTERNAL_SENSOR_RECORD_LEN]
            if len(rec) < EXTERNAL_SENSOR_RECORD_LEN:
                break
            sensor = self._parse_external_sensor_record(rec, offset)
            if sensor is None:
                break
            sensors.append(sensor)
            offset += EXTERNAL_SENSOR_RECORD_LEN
        return sensors

    def _parse_external_sensor_record(self, rec: bytes, file_offset: int) -> Optional[SensorDefinition]:
        if len(rec) < EXTERNAL_SENSOR_RECORD_LEN:
            return None
        channel_index = rec[8]
        slope = struct.unpack('<f', rec[12:16])[0]
        offset_val = struct.unpack('<f', rec[16:20])[0]
        height = struct.unpack('<f', rec[20:24])[0]
        range_val = struct.unpack('<f', rec[24:28])[0]
        text = rec[28:].split(b'\x00')[0].split(b'\xff')[0].decode('ascii', errors='replace')
        text = self._strip_trailing_control_chars(text)
        sensor_type, sensor_model, measurement, serial, unit = self._split_sensor_text(text)
        serial = self._normalize_placeholder(serial)
        return SensorDefinition(channel_index=channel_index, sensor_type=sensor_type, sensor_model=sensor_model, measurement=measurement, serial_number=serial, unit=self._normalize_unit(unit), height_m=height if 0 < height < 1000 else None, calibration_slope=slope, calibration_offset=offset_val, range_or_scale=range_val, raw_record_offset=file_offset)

    @staticmethod
    def _split_placeholder_serial_and_unit(remainder: Optional[str]):
        if not remainder:
            return (None, None)
        import re
        m = re.match('^(\\.+)(\\S*)$', remainder)
        if m:
            dots, rest = (m.group(1), m.group(2))
            return (dots if dots else None, rest or None)
        return (remainder, None)

    @staticmethod
    def _split_sensor_text(text: str):
        import re
        fields = [f.strip() for f in re.split('\\s{2,}', text) if f.strip()]
        if fields and fields[0] == 'Other':
            sensor_type = fields[0]
            sensor_model = ''
            measurement = fields[1] if len(fields) > 1 else ''
            remainder = fields[2] if len(fields) > 2 else None
            serial, unit = NomadNDFDecoder._split_placeholder_serial_and_unit(remainder)
            return (sensor_type, sensor_model, measurement, serial, unit)
        measurement_keywords = ('Temperature', 'Direction', 'Speed', 'Voltage', 'Insolation')
        sensor_type = fields[0] if len(fields) > 0 else 'Unknown'
        rest = fields[1:] if len(fields) > 1 else []
        sensor_model = ''
        measurement = ''
        serial = None
        unit = None
        if rest:
            kw_field_idx, kw_match = (None, None)
            for i, f in enumerate(rest):
                for kw in measurement_keywords:
                    if kw in f:
                        kw_field_idx, kw_match = (i, kw)
                        break
                if kw_field_idx is not None:
                    break
            if kw_field_idx is not None:
                field_with_kw = rest[kw_field_idx]
                kw_pos = field_with_kw.index(kw_match)
                before = field_with_kw[:kw_pos].strip()
                after = field_with_kw[kw_pos:].strip()
                model_tokens = rest[:kw_field_idx] + ([before] if before else [])
                sensor_model = ' '.join(model_tokens).strip()
                after_tokens = after.split()
                measurement = after_tokens[0] if after_tokens else kw_match
                trailing = after_tokens[1:]
                remaining = trailing + rest[kw_field_idx + 1:]
                serial = remaining[0] if len(remaining) > 0 else None
                unit = remaining[1] if len(remaining) > 1 else None
            else:
                sensor_model = rest[0] if len(rest) > 0 else ''
                measurement = rest[1] if len(rest) > 1 else ''
                serial = rest[2] if len(rest) > 2 else None
                unit = rest[3] if len(rest) > 3 else None
        return (sensor_type, sensor_model, measurement, serial, unit)

    def _parse_internal_channel_record(self, rec: bytes, file_offset: int) -> SensorDefinition:
        channel_index = rec[8]
        scale = struct.unpack('<f', rec[12:16])[0]
        text = rec[20:].split(b'\x00')[0].split(b'\xff')[0].decode('ascii', errors='replace')
        text = self._strip_trailing_control_chars(text)
        sensor_type, label, measurement, unit = self._split_internal_channel_text(text)
        return SensorDefinition(channel_index=channel_index, sensor_type=sensor_type, sensor_model=label, measurement=measurement, serial_number=None, unit=self._normalize_unit(unit), height_m=None, calibration_slope=scale, calibration_offset=None, range_or_scale=None, raw_record_offset=file_offset)

    @staticmethod
    def _split_internal_channel_text(text: str):
        import re
        known_types = ['DC Voltage', 'Temperature']
        sensor_type = None
        rest = text
        for t in known_types:
            if text.startswith(t):
                sensor_type = t
                rest = text[len(t):].strip()
                break
        if sensor_type is None:
            fields = [f.strip() for f in re.split('\\s{2,}', text) if f.strip()]
            sensor_type = fields[0] if fields else 'Internal'
            rest = '  '.join(fields[1:])
        fields = [f.strip() for f in re.split('\\s{2,}', rest) if f.strip()]
        label = fields[0] if len(fields) > 0 else ''
        measurement = fields[1] if len(fields) > 1 else ''
        unit = fields[2] if len(fields) > 2 else None
        if not unit and measurement and (' ' in measurement):
            parts = measurement.split()
            if len(parts) >= 2:
                measurement, unit = (' '.join(parts[:-1]), parts[-1])
        return (sensor_type, label, measurement, unit)

    @staticmethod
    def _strip_trailing_control_chars(text: str) -> str:
        while text and (ord(text[-1]) < 32 or ord(text[-1]) > 126):
            text = text[:-1]
        return text.rstrip()

    @staticmethod
    def _normalize_placeholder(value: Optional[str]) -> Optional[str]:
        if value and set(value) == {'.'}:
            return None
        return value

    @staticmethod
    def _normalize_unit(raw_unit: Optional[str]) -> Optional[str]:
        if not raw_unit:
            return raw_unit
        cleaned = raw_unit.replace('�', 'deg').strip()
        if cleaned in ('', '\x00'):
            return None
        return cleaned

    def _locate_stub_region(self, data: bytes) -> tuple:
        stub_start = data.find(STUB_RECORD_TAG, CHANNEL_TABLE_OFFSET)
        data_start = data.find(DATA_RECORD_TAG, CHANNEL_TABLE_OFFSET)
        if stub_start == -1 or data_start == -1 or data_start <= stub_start:
            return (stub_start, 0, data_start)
        stub_count = (data_start - stub_start) // STUB_RECORD_LEN
        return (stub_start, stub_count, data_start)

    def _select_layout(self, data: bytes, metadata: LoggerMetadata) -> Optional[DeploymentLayout]:
        stub_start, stub_count, _ = self._locate_stub_region(data)
        if stub_start == -1 or stub_count == 0:
            return None
        fingerprint = _fingerprint_channels(data, stub_start, stub_count)
        for layout in KNOWN_DEPLOYMENT_LAYOUTS:
            if layout.fingerprint == fingerprint:
                return layout
        return None

    @staticmethod
    def _generic_layout_from_stub_counts(data: bytes, stub_start: int, stub_count: int) -> DeploymentLayout:
        from collections import Counter
        order: List[int] = []
        counts: Counter = Counter()
        for i in range(stub_count):
            off = stub_start + i * STUB_RECORD_LEN
            rec = data[off:off + STUB_RECORD_LEN]
            if len(rec) < STUB_RECORD_LEN:
                break
            chan = rec[8]
            if chan not in counts:
                order.append(chan)
            counts[chan] += 1
        layout: List[SlotMapping] = []
        slot_idx = 0
        for chan in order:
            n = counts[chan]
            if n == 1:
                layout.append(SlotMapping(slot_idx, chan, 'Avg'))
                slot_idx += 1
            else:
                for k in range(n):
                    layout.append(SlotMapping(slot_idx, chan, f'Stat{k + 1}_UNCONFIRMED'))
                    slot_idx += 1
        fingerprint = tuple(sorted(counts.items()))
        return DeploymentLayout(name='generic_unconfirmed_fallback', fingerprint=fingerprint, slot_layout=layout)

    def parse_records(self, data: bytes, metadata: LoggerMetadata, start_time: Optional[datetime]=None, interval_minutes: Optional[int]=None) -> RecordStream:
        user_supplied_interval = interval_minutes
        stub_start, stub_count, data_start = self._locate_stub_region(data)
        if data_start == -1:
            raise ValueError('Could not locate the start of the Nomad data region (0xD801 tag not found).')
        layout = self._select_layout(data, metadata)
        layout_is_confirmed = layout is not None
        if layout is None:
            layout = self._generic_layout_from_stub_counts(data, stub_start, stub_count)
        slots_per_scan = len(layout.slot_layout)
        remaining = len(data) - data_start
        total_records = remaining // DATA_RECORD_LEN
        num_scans = total_records // slots_per_scan
        if user_supplied_interval is not None:
            interval_minutes = user_supplied_interval
        elif getattr(layout, 'sampling_interval_minutes', None) is not None:
            interval_minutes = layout.sampling_interval_minutes
        else:
            estimated_interval = round(1440 / num_scans)
            valid_intervals = [1, 2, 5, 10, 15, 30, 60]
            interval_minutes = min(valid_intervals, key=lambda x: abs(x - estimated_interval))
        values: List[List[float]] = []
        offset = data_start
        for _scan in range(num_scans):
            row = [0.0] * slots_per_scan
            for slot_idx in range(slots_per_scan):
                rec = data[offset:offset + DATA_RECORD_LEN]
                value = struct.unpack('<f', rec[12:16])[0]
                row[slot_idx] = value
                offset += DATA_RECORD_LEN
            values.append(row)
        actual_start_time = start_time or getattr(layout, 'default_start_time', None) or DEFAULT_START_TIME
        timestamps = uniform_time_index(actual_start_time, interval_minutes, num_scans)
        slots: List[ChannelSlot] = []
        for mapping in layout.slot_layout:
            sensor = metadata.sensor_by_index(mapping.channel_index) if mapping.channel_index is not None else None
            if sensor is None:
                label = 'Unresolved' if mapping.channel_index is None else f'Channel{mapping.channel_index}'
                sensor = SensorDefinition(channel_index=mapping.channel_index if mapping.channel_index is not None else -1, sensor_type='Unknown', sensor_model='', measurement=f'Raw_Slot{mapping.slot_index}_{label}')
            slots.append(ChannelSlot(slot_index=mapping.slot_index, sensor=sensor, statistic=mapping.statistic, windographer_name=mapping.windographer_name, frequency_group=mapping.frequency_group))
        return RecordStream(timestamps=timestamps, values=values, slots=slots, interval_minutes=interval_minutes, source_file=None, records_per_scan=slots_per_scan, bytes_per_record=DATA_RECORD_LEN, data_region_offset=data_start, layout_name=layout.name, layout_confirmed=layout_is_confirmed, timezone_label=layout.timezone_label, windographer_column_order=layout.windographer_column_order)

    def describe_findings(self, data: bytes) -> str:
        return __doc__ or 'See module docstring in decoders/nomad_ndf.py.'