"""
excel_exporter.py
--------------------
Exports a decoded RecordStream (and its associated LoggerMetadata) to .xlsx workbooks.

Detects if the deployment has multiple frequency groups (e.g. 10min standard data
and 1min unpacked sub-samples) and generates separate files for each.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict
from datetime import timedelta

import pandas as pd
import openpyxl

from parsers.metadata_parser import LoggerMetadata
from parsers.record_parser import RecordStream, ChannelSlot


def _generate_metadata_lines(metadata: LoggerMetadata, stream: Optional[RecordStream] = None,
                              timezone_label: Optional[str] = None) -> list:
    """Build the 13-line metadata header block that Windographer places at
    the top of its text/Excel exports."""
    info = metadata.logger_info
    tz = timezone_label or info.time_zone or "UTC"
    lines = [
        f"Site name: {info.site_name or ''}",
        f"Site description: Serial number: {info.serial_number or ''}",
        f"Latitude: {info.latitude or ''}",
        f"Longitude: {info.longitude or ''}",
        f"Elevation: {int(info.elevation_m) if info.elevation_m else 0} m",
        f"Time zone: {tz}",
        f"Logger Model: {info.logger_model or ''}",
        f"Serial Number: {info.serial_number or ''}",
        "",
        "Included flags: <Unflagged data>",
        "Excluded flags: ",
        "",
        "Time stamps indicate the beginning of the time step.",
        ""
    ]
    return lines


def _write_excel(df: pd.DataFrame, path: Path, ts_col_name: str, meta_lines: list):
    """Formats timestamps, writes the dataframe to excel, and prepends metadata."""
    # Format timestamps
    df[ts_col_name] = pd.to_datetime(df[ts_col_name]).dt.strftime('%Y-%m-%d %H:%M')

    # Save to Excel
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data", startrow=14)

    # Post-process to add metadata at the top
    wb = openpyxl.load_workbook(path)
    ws = wb["Data"]

    for i, line in enumerate(meta_lines, start=1):
        ws.cell(row=i, column=1, value=line)

    wb.save(path)


def export_workbook(stream: RecordStream, metadata: LoggerMetadata, base_output_path: Path,
                     timezone_label: Optional[str] = None) -> List[Path]:
    """Write .xlsx files matching the Windographer raw export layout.
    
    Generates multiple files if the stream contains multiple frequency groups.
    Returns a list of generated file paths.
    """
    base_path = Path(base_output_path)
    base_path.parent.mkdir(parents=True, exist_ok=True)

    tz = timezone_label or "UTC"
    ts_col_name = f"Timestamp ({tz})"
    meta_lines = _generate_metadata_lines(metadata, stream, timezone_label)

    # Filter exportable slots (must have a windographer_name)
    exportable_slots = [s for s in stream.slots if getattr(s, 'windographer_name', None) is not None]
    if not exportable_slots:
        exportable_slots = stream.slots  # fallback

    # Group slots by frequency
    freq_groups: Dict[str, List[ChannelSlot]] = {}
    for slot in exportable_slots:
        freq = getattr(slot, 'frequency_group', '10min')
        freq_groups.setdefault(freq, []).append(slot)

    written_paths = []

    # Process 10-minute standard data
    if "10min" in freq_groups:
        slots_10m = freq_groups["10min"]
        result_dict = {ts_col_name: list(stream.timestamps)}
        for slot in slots_10m:
            col_name = getattr(slot, 'windographer_name', None) or slot.column_name
            result_dict[col_name] = [row[slot.slot_index] for row in stream.values]
        
        df_10m = pd.DataFrame(result_dict)

        # Reorder columns to match Windographer export order if specified
        col_order = getattr(stream, 'windographer_column_order', None)
        if col_order:
            ordered_cols = [ts_col_name] + [c for c in col_order if c in df_10m.columns]
            df_10m = df_10m[ordered_cols]

        out_path = base_path.with_name(f"{base_path.stem}_10min{base_path.suffix}")
        _write_excel(df_10m, out_path, ts_col_name, meta_lines)
        written_paths.append(out_path)

    # Process 1-minute unpacked data
    if "1min" in freq_groups:
        slots_1m = freq_groups["1min"]
        # We assume they all map to the exact same column name (e.g. VectorStdDev), 
        # and there are exactly 10 of them representing minutes 0 through 9 of the 10-minute scan.
        col_name = getattr(slots_1m[0], 'windographer_name', None) or slots_1m[0].column_name
        
        unpacked_ts = []
        unpacked_vals = []

        # Sort slots by index just to be safe (they should be 0-9)
        slots_1m_sorted = sorted(slots_1m, key=lambda s: s.slot_index)

        for i, row_ts in enumerate(stream.timestamps):
            row_vals = stream.values[i]
            for min_offset, slot in enumerate(slots_1m_sorted):
                unpacked_ts.append(row_ts + timedelta(minutes=min_offset))
                unpacked_vals.append(row_vals[slot.slot_index])
        
        df_1m = pd.DataFrame({
            ts_col_name: unpacked_ts,
            col_name: unpacked_vals
        })

        out_path = base_path.with_name(f"{base_path.stem}_1min{base_path.suffix}")
        _write_excel(df_1m, out_path, ts_col_name, meta_lines)
        written_paths.append(out_path)

    return written_paths
