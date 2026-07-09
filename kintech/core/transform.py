from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from .models import ChannelDef, ParsedFile
log = logging.getLogger(__name__)
AIR_DENSITY_K = 82791.0
AIR_DENSITY_DEFAULT = 1.21
_TYPE_WS = 'WS'
_TYPE_WD = 'WD'
_TYPE_PR = 'PR'
_TYPE_RAD = 'RAD'
_TYPE_V = 'V'
_NAME_RE = re.compile('^[A-Za-z]?\\d*_(?P<type>[A-Za-z]+)_(?P<height>[\\d.]+)_(?P<orient>[\\d.]+)_(?P<model>.+)$')

@dataclass
class ChannelInfo:
    chan: ChannelDef
    sensor_type: Optional[str]
    height_m: Optional[float]
    orientation_deg: Optional[float]
    model: Optional[str]

def _classify(chan: ChannelDef) -> ChannelInfo:
    if chan.column_prefix.lower() == 'battery':
        return ChannelInfo(chan, 'BATT', chan.height_m, chan.orientation_deg, 'Battery')
    m = _NAME_RE.match(chan.name)
    if not m:
        log.debug('Channel name %r did not match the typed-naming convention; will be treated as an unclassified/passthrough channel.', chan.name)
        return ChannelInfo(chan, None, chan.height_m, chan.orientation_deg, None)
    return ChannelInfo(chan, m.group('type').upper(), float(m.group('height')), float(m.group('orient')), m.group('model'))

@dataclass
class OutputTable:
    columns: List[str]
    rows: List[List[object]]
    units: Dict[str, str]
    decimals: Dict[str, int] = None

    def __post_init__(self):
        if self.decimals is None:
            self.decimals = {}

class RecordTransformer:

    def __init__(self, parsed: ParsedFile, output_style: str='windographer', resample: bool=True, interval_minutes: int=10, timestamp_shift_minutes: int=10, fill_gaps: bool=True):
        self.parsed = parsed
        self.output_style = output_style
        self.resample = resample
        self.interval_minutes = interval_minutes
        self.timestamp_shift_minutes = timestamp_shift_minutes
        self.fill_gaps = fill_gaps
        self.channel_infos = [_classify(c) for c in parsed.channels]

    def build_table(self) -> OutputTable:
        if self.output_style == 'raw':
            return self._build_raw_table()
        if self.output_style == 'windographer':
            return self._build_windographer_table()
        raise ValueError(f'Unknown output_style: {self.output_style!r}')

    def _build_raw_table(self) -> OutputTable:
        columns = self.parsed.actual_columns
        rows = []
        for rec in sorted(self.parsed.records, key=lambda r: r.timestamp):
            row = []
            for col in columns:
                if col == 'DateTime':
                    row.append(rec.timestamp.strftime('%Y-%m-%d %H:%M'))
                else:
                    row.append(rec.values.get(col))
            rows.append(row)
        print('Actual columns:', len(self.parsed.actual_columns))
        print('First 10:', self.parsed.actual_columns[:10])
        print('Records:', len(self.parsed.records))
        return OutputTable(columns=columns, rows=rows, units={})

    def _build_windographer_table(self) -> OutputTable:
        records_by_ts = {r.timestamp: r for r in self.parsed.records}
        if self.resample and self.parsed.records:
            kept_timestamps = self._resampled_grid(records_by_ts)
        else:
            kept_timestamps = sorted(records_by_ts.keys())
        speed_groups, direction_infos, pressure_info, other_infos = self._group_channels()
        columns, units, decimals = self._build_windographer_columns(speed_groups, direction_infos, pressure_info, other_infos)
        rows: List[List[object]] = []
        shift = timedelta(minutes=self.timestamp_shift_minutes)
        for ts in kept_timestamps:
            rec = records_by_ts.get(ts)
            out_ts = ts - shift
            if rec is None:
                if not self.fill_gaps:
                    continue
                rows.append(self._blank_row(out_ts, columns, pressure_info))
                continue
            rows.append(self._build_one_row(out_ts, rec, columns, speed_groups, direction_infos, pressure_info, other_infos))
        return OutputTable(columns=columns, rows=rows, units=units, decimals=decimals)

    def _resampled_grid(self, records_by_ts: Dict[datetime, object]) -> List[datetime]:
        all_ts = sorted(records_by_ts.keys())
        first, last = (all_ts[0], all_ts[-1])
        step = timedelta(minutes=self.interval_minutes)
        base_minute = first.minute // self.interval_minutes * self.interval_minutes
        grid_start = first.replace(minute=base_minute, second=0, microsecond=0)
        if grid_start < first:
            pass
        grid = []
        t = grid_start
        while t <= last:
            grid.append(t)
            t += step
        return grid

    def _group_channels(self):
        speed_infos = [i for i in self.channel_infos if i.sensor_type == _TYPE_WS]
        direction_infos = [i for i in self.channel_infos if i.sensor_type == _TYPE_WD]
        pressure_infos = [i for i in self.channel_infos if i.sensor_type == _TYPE_PR]
        batt_infos = [i for i in self.channel_infos if i.sensor_type == 'BATT']
        radiometer_infos = [i for i in self.channel_infos if i.sensor_type == _TYPE_RAD]
        handled_names = {i.chan.name for i in speed_infos + direction_infos + pressure_infos + batt_infos + radiometer_infos[:1]}
        pressure_info = pressure_infos[0] if pressure_infos else None
        if len(pressure_infos) > 1:
            log.warning('Multiple pressure channels found (%s); using %s for the Air Density / Pres columns and emitting the rest as raw passthrough columns.', [i.chan.name for i in pressure_infos], pressure_info.chan.name)
            for extra in pressure_infos[1:]:
                handled_names.discard(extra.chan.name)
        speed_groups = []
        for s in speed_infos:
            best_dir = None
            if direction_infos and s.height_m is not None:
                best_dir = min((d for d in direction_infos if d.height_m is not None), key=lambda d: abs(d.height_m - s.height_m), default=None)
            speed_groups.append((s, best_dir))
        other_infos = [i for i in self.channel_infos if i.chan.name not in handled_names]
        return (speed_groups, direction_infos, pressure_info, other_infos)

    @staticmethod
    def _is_primary_ti30_channel(info: 'ChannelInfo', speed_groups) -> bool:
        if not info.chan.has_ti30:
            return False
        ti30_infos = [s for s, _d in speed_groups if s.chan.has_ti30]
        if not ti30_infos:
            return False
        primary = min(ti30_infos, key=lambda s: s.orientation_deg or 0.0)
        return info is primary

    @staticmethod
    def _label_for_speed(info: ChannelInfo) -> str:
        height = info.height_m
        side = 'N' if (info.orientation_deg or 0) < 90 else 'S'
        return f'Spd {_fmt_height(height)} {side}'

    @staticmethod
    def _label_for_direction(info: ChannelInfo) -> str:
        side = 'N' if (info.orientation_deg or 0) < 90 else 'S'
        return f'Dir {_fmt_height(info.height_m)} {side}'

    def _build_windographer_columns(self, speed_groups, direction_infos, pressure_info, other_infos) -> Tuple[List[str], Dict[str, str], Dict[str, int]]:
        columns = ['Timestamp (UTC)']
        units: Dict[str, str] = {}
        decimals: Dict[str, int] = {}
        for s, _d in speed_groups:
            label = self._label_for_speed(s)
            for suffix, u in ((' [m/s]', s.chan.units), (' SD [m/s]', s.chan.units), (' Gust [m/s]', s.chan.units)):
                columns.append(label + suffix)
                units[label + suffix] = u
                decimals[label + suffix] = 3
        for d in direction_infos:
            label = self._label_for_direction(d)
            for suffix in (' [°]', ' SD [°]'):
                columns.append(label + suffix)
                units[label + suffix] = d.chan.units
                decimals[label + suffix] = 1
        if pressure_info:
            columns.append('DNI [W/m²]')
        if not pressure_info:
            if 'DNI [W/m²]' not in columns:
                columns.append('DNI [W/m²]')
        decimals['DNI [W/m²]'] = 1
        if pressure_info:
            pres_label = f'Pres {_fmt_height(pressure_info.height_m)} [mbar]'
            columns.append(pres_label)
            units[pres_label] = pressure_info.chan.units
            decimals[pres_label] = 1
        columns.append('BattV [V]')
        units['BattV [V]'] = 'V'
        decimals['BattV [V]'] = 3
        if pressure_info:
            ad_label = f'Air Density {_fmt_height(pressure_info.height_m)} [kg/m³]'
            columns.append(ad_label)
            units[ad_label] = 'kg/m³'
            decimals[ad_label] = 3
        ti_letter_idx = 0
        for s, _d in speed_groups:
            is_primary = self._is_primary_ti30_channel(s, speed_groups)
            if is_primary:
                label = f"TI {_fmt_height(s.height_m)} {chr(ord('A') + ti_letter_idx)}"
                columns.append(label)
                decimals[label] = 4
                ti_letter_idx += 1
            else:
                ratio_label = f'{self._label_for_speed(s)} TI'
                columns.append(ratio_label)
                decimals[ratio_label] = 4
                if s.chan.has_ti30:
                    ti30_label = f"TI {_fmt_height(s.height_m)} {chr(ord('A') + ti_letter_idx)}"
                    columns.append(ti30_label)
                    decimals[ti30_label] = 4
                    ti_letter_idx += 1
        for s, _d in speed_groups:
            label = f'{self._label_for_speed(s)} WPD [W/m²]'
            columns.append(label)
            units[label] = 'W/m²'
        primary_ti30 = next((s for s, _d in speed_groups if self._is_primary_ti30_channel(s, speed_groups)), None)
        if primary_ti30 is not None:
            stdev_col = f'{primary_ti30.chan.name}-STDev'
            label = f'{stdev_col} [{primary_ti30.chan.units}]' if primary_ti30.chan.units else stdev_col
            columns.append(label)
            units[label] = primary_ti30.chan.units
        for o in other_infos:
            for col in o.chan.stat_columns:
                if col.endswith('-Min') or col.endswith('-Max'):
                    continue
                label = f'{col} [{o.chan.units}]' if o.chan.units else col
                columns.append(label)
                units[label] = o.chan.units
        return (columns, units, decimals)
        return (columns, units)

    def _blank_row(self, out_ts: datetime, columns: List[str], pressure_info) -> List[object]:
        row = [out_ts.strftime('%Y-%m-%d %H:%M')] + [None] * (len(columns) - 1)
        if pressure_info:
            for i, col in enumerate(columns):
                if col.startswith('Air Density'):
                    row[i] = AIR_DENSITY_DEFAULT
        return row

    def _build_one_row(self, out_ts, rec, columns, speed_groups, direction_infos, pressure_info, other_infos) -> List[object]:
        v = rec.values
        cell: Dict[str, object] = {'Timestamp (UTC)': out_ts.strftime('%Y-%m-%d %H:%M')}
        rho = None
        if pressure_info:
            p_mbar = v.get(pressure_info.chan.name)
            if p_mbar is not None:
                rho = p_mbar * 100.0 / AIR_DENSITY_K
        for s, _d in speed_groups:
            label = self._label_for_speed(s)
            avg = v.get(s.chan.name)
            mx = v.get(f'{s.chan.name}-Max')
            sd_raw = v.get(f'{s.chan.name}-STDev')
            cell[f'{label} [m/s]'] = _round_fixed(avg, 3)
            cell[f'{label} Gust [m/s]'] = _round_fixed(mx, 3)
            if self._is_primary_ti30_channel(s, speed_groups) and avg is not None:
                ti30 = v.get(f'{s.chan.name}-TI30')
                cell[f'{label} SD [m/s]'] = _round_fixed(avg * ti30, 3) if ti30 is not None else _round_fixed(sd_raw, 3)
            else:
                cell[f'{label} SD [m/s]'] = _round_fixed(sd_raw, 3)
        for d in direction_infos:
            label = self._label_for_direction(d)
            cell[f'{label} [°]'] = _round_fixed(v.get(d.chan.name), 1)
            cell[f'{label} SD [°]'] = _round_fixed(v.get(f'{d.chan.name}-STDev'), 1)
        dni_channel = next((i for i in self.channel_infos if i.sensor_type == _TYPE_RAD), None)
        if dni_channel:
            cell['DNI [W/m²]'] = _round_fixed(v.get(dni_channel.chan.name), 1)
        elif 'DNI [W/m²]' in columns:
            cell['DNI [W/m²]'] = None
        if pressure_info:
            cell[f'Pres {_fmt_height(pressure_info.height_m)} [mbar]'] = _round_fixed(v.get(pressure_info.chan.name), 1)
        batt = next((i for i in self.channel_infos if i.sensor_type == 'BATT'), None)
        cell['BattV [V]'] = _round_fixed(v.get(batt.chan.name), 3) if batt else None
        if pressure_info:
            ad_label = f'Air Density {_fmt_height(pressure_info.height_m)} [kg/m³]'
            cell[ad_label] = _round_fixed(rho, 3) if rho is not None else None
        ti_letter_idx = 0
        for s, _d in speed_groups:
            is_primary = self._is_primary_ti30_channel(s, speed_groups)
            avg = v.get(s.chan.name)
            sd = v.get(f'{s.chan.name}-STDev')
            if is_primary:
                label = f"TI {_fmt_height(s.height_m)} {chr(ord('A') + ti_letter_idx)}"
                cell[label] = _round_fixed(v.get(f'{s.chan.name}-TI30'), 4)
                ti_letter_idx += 1
            else:
                ratio_label = f'{self._label_for_speed(s)} TI'
                cell[ratio_label] = _round_fixed(sd / avg, 4) if avg not in (None, 0) and sd is not None else None
                if s.chan.has_ti30:
                    ti30_label = f"TI {_fmt_height(s.height_m)} {chr(ord('A') + ti_letter_idx)}"
                    cell[ti30_label] = _round_fixed(v.get(f'{s.chan.name}-TI30'), 4)
                    ti_letter_idx += 1
        for s, _d in speed_groups:
            label = f'{self._label_for_speed(s)} WPD [W/m²]'
            avg = v.get(s.chan.name)
            if rho is not None and avg is not None:
                cell[label] = _sigfig_round(0.5 * rho * avg ** 3, 5)
            else:
                cell[label] = None
        primary_ti30 = next((s for s, _d in speed_groups if self._is_primary_ti30_channel(s, speed_groups)), None)
        if primary_ti30 is not None:
            stdev_col = f'{primary_ti30.chan.name}-STDev'
            label = f'{stdev_col} [{primary_ti30.chan.units}]' if primary_ti30.chan.units else stdev_col
            raw_val = v.get(stdev_col)
            cell[label] = _sigfig_round(raw_val, 5) if raw_val is not None else None
        for o in other_infos:
            for col in o.chan.stat_columns:
                if col.endswith('-Min') or col.endswith('-Max'):
                    continue
                label = f'{col} [{o.chan.units}]' if o.chan.units else col
                raw_val = v.get(col)
                cell[label] = _sigfig_round(raw_val, 5) if raw_val is not None else None
        return [cell.get(c) for c in columns]

def _round_fixed(x: Optional[float], decimals: int) -> Optional[float]:
    if x is None:
        return None
    from decimal import ROUND_HALF_UP, Decimal
    quant = Decimal('1') if decimals == 0 else Decimal('1.' + '0' * decimals)
    return float(Decimal(str(x)).quantize(quant, rounding=ROUND_HALF_UP))

def _fmt_height(h: Optional[float]) -> str:
    if h is None:
        return '?m'
    if float(h).is_integer():
        return f'{int(h)}m'
    return f'{h}m'

def _sigfig_round(x: Optional[float], sig: int) -> Optional[float]:
    if x is None:
        return None
    if x == 0:
        return 0.0
    from math import floor, log10
    d = sig - int(floor(log10(abs(x)))) - 1
    return round(x, d)