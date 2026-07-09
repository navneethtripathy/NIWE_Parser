from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class SensorDefinition:
    channel_index: int
    sensor_type: str
    sensor_model: str
    measurement: str
    serial_number: Optional[str] = None
    unit: Optional[str] = None
    height_m: Optional[float] = None
    calibration_slope: Optional[float] = None
    calibration_offset: Optional[float] = None
    range_or_scale: Optional[float] = None
    raw_record_offset: Optional[int] = None

    @property
    def display_name(self) -> str:
        if 'speed' in self.measurement.lower():
            base = 'WindSpeed'
        elif 'direction' in self.measurement.lower():
            base = 'WindDirection'
        elif 'temperature' in self.measurement.lower():
            base = 'Temperature'
        elif 'insolation' in self.measurement.lower() or 'solar' in self.measurement.lower():
            base = 'SolarRadiation'
        elif 'pressure' in self.measurement.lower():
            base = 'Pressure'
        elif 'humidity' in self.measurement.lower():
            base = 'Humidity'
        elif 'voltage' in self.measurement.lower():
            base = self.sensor_model.replace(' ', '') or 'Voltage'
        else:
            base = self.measurement.replace(' ', '')
        if self.height_m is not None:
            height_str = f'{self.height_m:g}'
            return f'{base}_{height_str}m'
        return base

@dataclass
class LoggerInfo:
    logger_model: Optional[str] = None
    serial_number: Optional[str] = None
    site_name: Optional[str] = None
    site_description: Optional[str] = None
    elevation_m: Optional[float] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    time_zone: Optional[str] = None
    firmware_or_build_ids: List[int] = field(default_factory=list)
    raw_preamble_offset: Optional[int] = None
    raw_preamble_length: Optional[int] = None

@dataclass
class LoggerMetadata:
    logger_info: LoggerInfo
    sensors: List[SensorDefinition] = field(default_factory=list)

    def sensor_by_index(self, channel_index: int) -> Optional[SensorDefinition]:
        for s in self.sensors:
            if s.channel_index == channel_index:
                return s
        return None

    def summary(self) -> str:
        lines = ['=== Logger Info ===', f'  Model         : {self.logger_info.logger_model}', f'  Serial number : {self.logger_info.serial_number}', f'  Site name     : {self.logger_info.site_name}', f'  Elevation     : {self.logger_info.elevation_m} m', '', f'=== Sensors ({len(self.sensors)}) ===']
        for s in self.sensors:
            lines.append(f'  [{s.channel_index:>3}] {s.sensor_type:<12s} {s.sensor_model:<14s} {s.measurement:<14s} height={s.height_m!s:<6} unit={s.unit!s:<6} serial={s.serial_number!s:<8} slope={s.calibration_slope!s} offset={s.calibration_offset!s}')
        return '\n'.join(lines)