"""
metadata_parser.py
--------------------
Dataclasses that hold all metadata extracted from a logger file, plus a
thin generic parsing helper. The dataclasses are intentionally
format-agnostic (any decoder -- Nomad, Campbell, Ammonit, ...) populates the
same shapes, which is what makes the rest of the pipeline (record parsing,
Excel export) reusable across logger brands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SensorDefinition:
    """A single physical sensor / logical channel as declared in the
    logger's metadata block."""
    channel_index: int
    sensor_type: str                 # e.g. "Anemometer", "Wind Vane", "Thermistor", "Other", "DC Voltage"
    sensor_model: str                # e.g. "SWI C3", "SWI PV1", "SWI 10k Probe"
    measurement: str                 # e.g. "Speed", "Direction", "Temperature", "Insolation", "Voltage"
    serial_number: Optional[str] = None
    unit: Optional[str] = None       # e.g. "m/s", "deg", "degC", "W/m2", "V"
    height_m: Optional[float] = None
    calibration_slope: Optional[float] = None
    calibration_offset: Optional[float] = None
    range_or_scale: Optional[float] = None
    raw_record_offset: Optional[int] = None  # byte offset of this sensor's definition record, for traceability

    @property
    def display_name(self) -> str:
        """A short, human/Excel-friendly column name, e.g. 'WindSpeed_80m'."""
        if "speed" in self.measurement.lower():
            base = "WindSpeed"
        elif "direction" in self.measurement.lower():
            base = "WindDirection"
        elif "temperature" in self.measurement.lower():
            base = "Temperature"
        elif "insolation" in self.measurement.lower() or "solar" in self.measurement.lower():
            base = "SolarRadiation"
        elif "pressure" in self.measurement.lower():
            base = "Pressure"
        elif "humidity" in self.measurement.lower():
            base = "Humidity"
        elif "voltage" in self.measurement.lower():
            base = self.sensor_model.replace(" ", "") or "Voltage"
        else:
            base = self.measurement.replace(" ", "")

        if self.height_m is not None:
            height_str = f"{self.height_m:g}"
            return f"{base}_{height_str}m"
        return base


@dataclass
class LoggerInfo:
    """Logger / station-level metadata (not specific to any one sensor)."""
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
    """Top-level container returned by every decoder's `parse_metadata()`."""
    logger_info: LoggerInfo
    sensors: List[SensorDefinition] = field(default_factory=list)

    def sensor_by_index(self, channel_index: int) -> Optional[SensorDefinition]:
        for s in self.sensors:
            if s.channel_index == channel_index:
                return s
        return None

    def summary(self) -> str:
        lines = [
            "=== Logger Info ===",
            f"  Model         : {self.logger_info.logger_model}",
            f"  Serial number : {self.logger_info.serial_number}",
            f"  Site name     : {self.logger_info.site_name}",
            f"  Elevation     : {self.logger_info.elevation_m} m",
            "",
            f"=== Sensors ({len(self.sensors)}) ===",
        ]
        for s in self.sensors:
            lines.append(
                f"  [{s.channel_index:>3}] {s.sensor_type:<12s} {s.sensor_model:<14s} "
                f"{s.measurement:<14s} height={s.height_m!s:<6} unit={s.unit!s:<6} "
                f"serial={s.serial_number!s:<8} slope={s.calibration_slope!s} offset={s.calibration_offset!s}"
            )
        return "\n".join(lines)
