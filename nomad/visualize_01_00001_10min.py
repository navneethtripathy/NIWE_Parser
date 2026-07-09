from __future__ import annotations
import re
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
INPUT_PATH = Path('outputs/01-00001_10min.xlsx')
OUTPUT_DIR = Path('outputs/01-00001_10min_visualizations')

def clean_filename(value: str) -> str:
    value = value.strip()
    value = re.sub('[\\\\/:*?\\"<>|]+', '_', value)
    value = re.sub('\\s+', '_', value)
    return value[:200]

def _parse_wind_speed_columns(column_names):
    pattern = re.compile('^Spd\\s+(?P<height>[\\d\\.]+m)\\s+(?P<direction>[A-Z]+)\\s*\\[m/s\\]$', re.I)
    direction_map = {}
    height_map = {}
    for name in column_names:
        match = pattern.match(name)
        if not match:
            continue
        height = match.group('height')
        direction = match.group('direction').upper()
        direction_map.setdefault(direction, []).append(name)
        height_map.setdefault(height, []).append(name)
    return (direction_map, height_map)

def _sort_height_key(value: str) -> float:
    try:
        return float(value.rstrip('m'))
    except ValueError:
        return float('inf')

def _save_combined_wind_speed_plots(df, ts_col, direction_map, height_map):
    if not direction_map and (not height_map):
        return
    if direction_map:
        for direction, columns in sorted(direction_map.items()):
            fig, ax = plt.subplots(figsize=(14, 6))
            sorted_columns = sorted(columns, key=lambda name: _sort_height_key(re.search('Spd\\s+([\\d\\.]+m)', name, re.I).group(1)))
            for column_name in sorted_columns:
                ax.plot(df[ts_col], df[column_name], marker='o', linestyle='-', linewidth=1, markersize=3, label=column_name)
            ax.set_title(f'Wind Speed at Different Heights — Direction {direction}')
            ax.set_xlabel('Timestamp')
            ax.set_ylabel('Wind Speed [m/s]')
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend(fontsize='small', loc='upper left', bbox_to_anchor=(1.01, 1), borderaxespad=0.0)
            fig.tight_layout(rect=[0, 0, 0.85, 1])
            out_path = OUTPUT_DIR / f'wind_speed_{clean_filename(direction)}_different_heights.png'
            fig.savefig(out_path, dpi=150)
            plt.close(fig)
            print(f'Saved: {out_path}')
    if height_map:
        for height, columns in sorted(height_map.items(), key=lambda kv: _sort_height_key(kv[0])):
            fig, ax = plt.subplots(figsize=(14, 6))
            for column_name in sorted(columns):
                direction = re.sub('^Spd\\s+[\\d\\.]+m\\s+', '', column_name, flags=re.I).replace(' [m/s]', '')
                ax.plot(df[ts_col], df[column_name], marker='o', linestyle='-', linewidth=1, markersize=3, label=direction)
            ax.set_title(f'Wind Speed at Same Height {height} — Different Directions')
            ax.set_xlabel('Timestamp')
            ax.set_ylabel('Wind Speed [m/s]')
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.legend(fontsize='small', loc='upper left', bbox_to_anchor=(1.01, 1), borderaxespad=0.0)
            fig.tight_layout(rect=[0, 0, 0.85, 1])
            out_path = OUTPUT_DIR / f'wind_speed_{clean_filename(height)}_different_directions.png'
            fig.savefig(out_path, dpi=150)
            plt.close(fig)
            print(f'Saved: {out_path}')

def _parse_temperature_columns(column_names):
    pattern = re.compile('^Tmp\\s+(?P<height>[\\d\\.]+m)\\s*\\[°C\\]$', re.I)
    temp_map = {}
    for name in column_names:
        match = pattern.match(name)
        if not match:
            continue
        height = match.group('height')
        temp_map[height] = name
    return temp_map

def _save_temperature_comparison_plot(df, ts_col, temp_map):
    if len(temp_map) < 2:
        return
    fig, ax = plt.subplots(figsize=(14, 6))
    for height, column_name in sorted(temp_map.items(), key=lambda kv: _sort_height_key(kv[0])):
        ax.plot(df[ts_col], df[column_name], marker='o', linestyle='-', linewidth=1, markersize=4, label=f'Tmp {height}')
    ax.set_title('Temperature Comparison: 2m vs 5m')
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Temperature [°C]')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(fontsize='small', loc='upper left', bbox_to_anchor=(1.01, 1), borderaxespad=0.0)
    fig.tight_layout(rect=[0, 0, 0.85, 1])
    out_path = OUTPUT_DIR / 'temperature_2m_5m_comparison.png'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f'Saved: {out_path}')

def main() -> int:
    if not INPUT_PATH.exists():
        print(f'ERROR: input workbook not found: {INPUT_PATH}')
        return 1
    df = pd.read_excel(INPUT_PATH, sheet_name='Data', header=14)
    if df.empty:
        print('ERROR: no data read from the workbook.')
        return 2
    ts_col = df.columns[0]
    df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
    if df[ts_col].isna().any():
        print(f'WARNING: {df[ts_col].isna().sum()} invalid timestamp values were parsed.')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for column_name in df.columns[1:]:
        series = df[column_name]
        if series.dropna().empty:
            print(f'Skipping empty column: {column_name}')
            continue
        plt.figure(figsize=(12, 5))
        plt.plot(df[ts_col], series, marker='o', linestyle='-', linewidth=1, markersize=4)
        plt.title(f'{column_name} vs Timestamp')
        plt.xlabel('Timestamp')
        plt.ylabel(column_name)
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        out_path = OUTPUT_DIR / f'{clean_filename(column_name)}.png'
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f'Saved: {out_path}')
    direction_map, height_map = _parse_wind_speed_columns(df.columns[1:])
    if direction_map or height_map:
        _save_combined_wind_speed_plots(df, ts_col, direction_map, height_map)
    else:
        print('No wind speed columns found for combined comparison plots.')
    temp_map = _parse_temperature_columns(df.columns[1:])
    if temp_map:
        _save_temperature_comparison_plot(df, ts_col, temp_map)
    else:
        print('No temperature columns found for temperature comparison plots.')
    print(f'Generated visualizations in {OUTPUT_DIR}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())