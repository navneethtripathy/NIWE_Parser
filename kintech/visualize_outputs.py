from __future__ import annotations
import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from math import log
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import seaborn as sns
log_mod = logging.getLogger('visualize_outputs')
PLOT_STYLE = {'figure.figsize': (14, 6), 'figure.dpi': 150, 'axes.grid': True, 'axes.grid.which': 'both', 'grid.alpha': 0.3, 'axes.titlesize': 14, 'axes.titleweight': 'bold', 'axes.labelsize': 11, 'legend.fontsize': 9, 'xtick.labelsize': 9, 'ytick.labelsize': 9, 'font.family': 'sans-serif'}
NIWE_COLORS = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
_KINTECH_RE = re.compile('^[A-Za-z]?\\d*_(?P<type>[A-Za-z]+)_(?P<height>[\\d.]+)_(?P<orient>[\\d.]+)_(?P<model>.+?)(?:-(?:STDev|Min|Max|TI30))?$')
_HEIGHT_RE = re.compile('_(\\d+(?:\\.\\d+)?)_')

@dataclass
class SensorGroup:
    wind_speed: List[str] = field(default_factory=list)
    wind_direction: List[str] = field(default_factory=list)
    temperature: List[str] = field(default_factory=list)
    battery: List[str] = field(default_factory=list)
    humidity: List[str] = field(default_factory=list)
    pressure: List[str] = field(default_factory=list)

def detect_sensors(columns: List[str]) -> SensorGroup:
    group = SensorGroup()
    for col in columns:
        if any((col.endswith(suf) for suf in ('-STDev', '-Min', '-Max', '-TI30'))):
            continue
        if col in ('DateTime', 'Timestamp (UTC)'):
            continue
        col_upper = col.upper()
        m = _KINTECH_RE.match(col)
        if m and m.group('type').upper() == 'WS':
            group.wind_speed.append(col)
            continue
        if any((kw in col_upper for kw in ('SPD', 'WIND SPEED', 'ANEMOMETER'))):
            if 'DIR' not in col_upper:
                group.wind_speed.append(col)
                continue
        if m and m.group('type').upper() == 'WD':
            group.wind_direction.append(col)
            continue
        if any((kw in col_upper for kw in ('DIRECTION', 'WIND DIR'))):
            group.wind_direction.append(col)
            continue
        if re.search('\\bDIR\\b', col_upper) and 'DIRECT' not in col_upper:
            group.wind_direction.append(col)
            continue
        if any((kw in col_upper for kw in ('TEMPERATURE', 'TEMP', 'TMP'))):
            group.temperature.append(col)
            continue
        if col_upper == 'BATTERY' or any((kw in col_upper for kw in ('BATT', 'BATTV'))):
            group.battery.append(col)
            continue
        if any((kw in col_upper for kw in ('HUMIDITY', 'RELATIVE HUMIDITY'))):
            group.humidity.append(col)
            continue
        if re.search('\\bRH\\b', col_upper):
            group.humidity.append(col)
            continue
        if m and m.group('type').upper() == 'PR':
            group.pressure.append(col)
            continue
        if any((kw in col_upper for kw in ('PRESSURE', 'MBAR', 'HPA', 'BAROMETRIC'))):
            group.pressure.append(col)
            continue
    return group

def extract_height(col_name: str) -> Optional[float]:
    m = _KINTECH_RE.match(col_name)
    if m:
        try:
            return float(m.group('height'))
        except ValueError:
            pass
    m2 = _HEIGHT_RE.search(col_name)
    if m2:
        try:
            return float(m2.group(1))
        except ValueError:
            pass
    return None

def _short_label(col: str) -> str:
    h = extract_height(col)
    if h is not None:
        h_str = f'{int(h)}m' if float(h).is_integer() else f'{h}m'
    else:
        h_str = None
    m = _KINTECH_RE.match(col)
    if m:
        orient = m.group('orient')
        side = 'N' if float(orient) < 90 else 'S'
        return f'{h_str} {side}' if h_str else col
    if h_str:
        return h_str
    return col

def _prepare_datetime(df: pd.DataFrame) -> pd.DataFrame:
    dt_col = None
    for candidate in ('DateTime', 'Timestamp (UTC)', 'Timestamp'):
        if candidate in df.columns:
            dt_col = candidate
            break
    if dt_col is None:
        first = df.columns[0]
        try:
            pd.to_datetime(df[first].iloc[:5])
            dt_col = first
        except Exception:
            return df
    df = df.copy()
    df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
    df = df.set_index(dt_col)
    return df

def _save_timeseries(df: pd.DataFrame, columns: List[str], out_path: Path, title: str, ylabel: str) -> bool:
    valid = [c for c in columns if c in df.columns]
    if not valid:
        return False
    with plt.rc_context(PLOT_STYLE):
        fig, ax = plt.subplots(figsize=(14, 6))
        for i, col in enumerate(valid):
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            if series.empty:
                continue
            color = NIWE_COLORS[i % len(NIWE_COLORS)]
            ax.plot(series.index, series.values, label=_short_label(col), color=color, linewidth=0.7, alpha=0.85)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=12)
        ax.set_xlabel('Date / Time')
        ax.set_ylabel(ylabel)
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate(rotation=45, ha='right')
        plt.tight_layout()
        fig.savefig(out_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
    return True

def plot_wind_speed(df: pd.DataFrame, columns: List[str], out_dir: Path) -> bool:
    return _save_timeseries(df, columns, out_dir / 'wind_speed.png', title='Wind Speed Time Series', ylabel='Wind Speed (m/s)')

def plot_wind_direction(df: pd.DataFrame, columns: List[str], out_dir: Path) -> bool:
    return _save_timeseries(df, columns, out_dir / 'wind_direction.png', title='Wind Direction Time Series', ylabel='Direction (°)')

def plot_temperature(df: pd.DataFrame, columns: List[str], out_dir: Path) -> bool:
    return _save_timeseries(df, columns, out_dir / 'temperature.png', title='Temperature Time Series', ylabel='Temperature (°C)')

def plot_battery(df: pd.DataFrame, columns: List[str], out_dir: Path) -> bool:
    return _save_timeseries(df, columns, out_dir / 'battery_voltage.png', title='Battery Voltage Time Series', ylabel='Voltage (V)')

def plot_humidity(df: pd.DataFrame, columns: List[str], out_dir: Path) -> bool:
    return _save_timeseries(df, columns, out_dir / 'humidity.png', title='Relative Humidity Time Series', ylabel='Humidity (%)')

def plot_pressure(df: pd.DataFrame, columns: List[str], out_dir: Path) -> bool:
    return _save_timeseries(df, columns, out_dir / 'pressure.png', title='Barometric Pressure Time Series', ylabel='Pressure (mbar)')

def plot_wind_rose(df: pd.DataFrame, ws_columns: List[str], wd_columns: List[str], out_dir: Path) -> bool:
    try:
        from windrose import WindroseAxes
    except ImportError:
        log_mod.warning('windrose library not installed — skipping wind rose plot. Install with: pip install windrose')
        return False
    ws_col = next((c for c in ws_columns if c in df.columns), None)
    wd_col = next((c for c in wd_columns if c in df.columns), None)
    if ws_col is None or wd_col is None:
        return False
    ws = pd.to_numeric(df[ws_col], errors='coerce')
    wd = pd.to_numeric(df[wd_col], errors='coerce')
    mask = ws.notna() & wd.notna() & (ws > 0)
    ws = ws[mask].values
    wd = wd[mask].values
    if len(ws) < 10:
        log_mod.warning('Too few valid wind speed/direction data points for wind rose.')
        return False
    with plt.rc_context(PLOT_STYLE):
        fig = plt.figure(figsize=(10, 10))
        ax = WindroseAxes.from_ax(fig=fig)
        ax.bar(wd, ws, normed=True, opening=0.8, edgecolor='white', cmap=plt.cm.viridis, nsector=16)
        ax.set_legend(title='Wind Speed (m/s)', loc='lower right', bbox_to_anchor=(1.15, -0.05))
        ax.set_title(f'Wind Rose — {_short_label(ws_col)} speed, {_short_label(wd_col)} direction', fontsize=13, fontweight='bold', pad=20)
        fig.savefig(out_dir / 'wind_rose.png', dpi=150, bbox_inches='tight')
        plt.close(fig)
    return True

def plot_wind_shear_profile(df: pd.DataFrame, ws_columns: List[str], out_dir: Path) -> Optional[Path]:
    height_speed: Dict[float, List[float]] = {}
    for col in ws_columns:
        if col not in df.columns:
            continue
        h = extract_height(col)
        if h is None or h <= 0:
            continue
        mean_ws = pd.to_numeric(df[col], errors='coerce').mean()
        if pd.isna(mean_ws):
            continue
        height_speed.setdefault(h, []).append(mean_ws)
    if len(height_speed) < 2:
        log_mod.info('Need at least 2 heights for wind shear profile — skipping.')
        return None
    heights = sorted(height_speed.keys())
    means = [np.mean(height_speed[h]) for h in heights]
    with plt.rc_context(PLOT_STYLE):
        fig, ax = plt.subplots(figsize=(8, 10))
        ax.plot(means, heights, 'o-', color='#1f77b4', markersize=10, linewidth=2.5, markerfacecolor='white', markeredgewidth=2.5, markeredgecolor='#1f77b4')
        for h, m_val in zip(heights, means):
            ax.annotate(f'  {m_val:.2f} m/s', (m_val, h), fontsize=10, fontweight='bold', va='center')
        ax.set_xlabel('Mean Wind Speed (m/s)', fontsize=12)
        ax.set_ylabel('Height (m)', fontsize=12)
        ax.set_title('Wind Shear Profile', fontsize=14, fontweight='bold', pad=12)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)
        plt.tight_layout()
        path = out_dir / 'wind_shear_profile.png'
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
    return path

def compute_wind_shear_exponent(df: pd.DataFrame, ws_columns: List[str]) -> Optional[float]:
    height_speed: Dict[float, float] = {}
    for col in ws_columns:
        if col not in df.columns:
            continue
        h = extract_height(col)
        if h is None or h <= 0:
            continue
        mean_ws = pd.to_numeric(df[col], errors='coerce').mean()
        if pd.isna(mean_ws) or mean_ws <= 0:
            continue
        if h in height_speed:
            height_speed[h] = (height_speed[h] + mean_ws) / 2.0
        else:
            height_speed[h] = mean_ws
    if len(height_speed) < 2:
        return None
    heights = sorted(height_speed.keys())
    h1, h2 = (heights[0], heights[-1])
    v1, v2 = (height_speed[h1], height_speed[h2])
    if v1 <= 0 or v2 <= 0 or h1 <= 0 or (h2 <= 0):
        return None
    try:
        alpha = log(v2 / v1) / log(h2 / h1)
    except (ValueError, ZeroDivisionError):
        return None
    return alpha

def plot_correlation_heatmap(df: pd.DataFrame, out_dir: Path) -> bool:
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return False
    short_labels = [_short_label(c) if len(c) > 20 else c for c in numeric_df.columns]
    seen: Dict[str, int] = {}
    unique_labels = []
    for lbl in short_labels:
        if lbl in seen:
            seen[lbl] += 1
            unique_labels.append(f'{lbl}_{seen[lbl]}')
        else:
            seen[lbl] = 0
            unique_labels.append(lbl)
    corr = numeric_df.corr()
    size = max(10, min(20, len(corr) * 0.5))
    with plt.rc_context(PLOT_STYLE):
        fig, ax = plt.subplots(figsize=(size, size * 0.85))
        sns.heatmap(corr, annot=len(corr) <= 20, fmt='.2f' if len(corr) <= 20 else '', cmap='RdBu_r', center=0, square=True, linewidths=0.5, xticklabels=unique_labels, yticklabels=unique_labels, ax=ax)
        ax.set_title('Sensor Correlation Heatmap', fontsize=14, fontweight='bold', pad=12)
        plt.xticks(rotation=45, ha='right', fontsize=8)
        plt.yticks(fontsize=8)
        plt.tight_layout()
        fig.savefig(out_dir / 'correlation_heatmap.png', dpi=150, bbox_inches='tight')
        plt.close(fig)
    return True

def generate_summary_report(df: pd.DataFrame, dataset_name: str, sensors: SensorGroup, alpha: Optional[float], report_dir: Path) -> str:
    dt_col = None
    for candidate in ('DateTime', 'Timestamp (UTC)', 'Timestamp'):
        if candidate in df.columns:
            dt_col = candidate
            break
    if dt_col and dt_col in df.columns:
        dt_series = pd.to_datetime(df[dt_col], errors='coerce').dropna()
        start = dt_series.min() if not dt_series.empty else 'N/A'
        end = dt_series.max() if not dt_series.empty else 'N/A'
    elif hasattr(df.index, 'min'):
        try:
            start = df.index.min()
            end = df.index.max()
        except Exception:
            start = end = 'N/A'
    else:
        start = end = 'N/A'
    lines = ['=' * 60, 'SUMMARY REPORT', '=' * 60, '', f'Dataset Name       : {dataset_name}', '', f'Rows               : {len(df)}', f'Columns            : {len(df.columns)}', '', f'Start Time         : {start}', f'End Time           : {end}', '', f'Wind Shear Exponent (α) : {alpha:.4f}' if alpha is not None else 'Wind Shear Exponent (α) : N/A (insufficient heights)', '', '─' * 40, 'Detected Sensor Channels', '─' * 40, '', f'Wind Speed     ({len(sensors.wind_speed)}):']
    for c in sensors.wind_speed:
        lines.append(f'    {c}')
    lines.append(f'\nWind Direction ({len(sensors.wind_direction)}):')
    for c in sensors.wind_direction:
        lines.append(f'    {c}')
    lines.append(f'\nTemperature    ({len(sensors.temperature)}):')
    for c in sensors.temperature:
        lines.append(f'    {c}')
    lines.append(f'\nBattery        ({len(sensors.battery)}):')
    for c in sensors.battery:
        lines.append(f'    {c}')
    lines.append(f'\nHumidity       ({len(sensors.humidity)}):')
    for c in sensors.humidity:
        lines.append(f'    {c}')
    lines.append(f'\nPressure       ({len(sensors.pressure)}):')
    for c in sensors.pressure:
        lines.append(f'    {c}')
    content = '\n'.join(lines) + '\n'
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'summary.txt').write_text(content, encoding='utf-8')
    return content

def generate_quality_report(df_raw: pd.DataFrame, dataset_name: str, report_dir: Path) -> str:
    total_rows = len(df_raw)
    total_cols = len(df_raw.columns)
    total_cells = total_rows * total_cols
    missing_total = int(df_raw.isnull().sum().sum())
    availability = (total_cells - missing_total) / total_cells * 100 if total_cells > 0 else 0.0
    dt_col = None
    for candidate in ('DateTime', 'Timestamp (UTC)', 'Timestamp'):
        if candidate in df_raw.columns:
            dt_col = candidate
            break
    dup_count = 0
    if dt_col:
        dup_count = int(df_raw[dt_col].duplicated().sum())
    lines = ['=' * 60, 'DATA QUALITY REPORT', '=' * 60, '', f'Dataset            : {dataset_name}', '', f'Rows               : {total_rows}', f'Columns            : {total_cols}', '', f'Missing Values     : {missing_total}', f'Total Cells        : {total_cells}', f'Data Availability  : {availability:.2f}%', '', f'Duplicate Timestamps : {dup_count}', '', '─' * 40, 'Missing Values By Column', '─' * 40]
    missing_by_col = df_raw.isnull().sum()
    for col in df_raw.columns:
        miss = int(missing_by_col[col])
        pct = miss / total_rows * 100 if total_rows > 0 else 0.0
        lines.append(f'    {col:50s}  {miss:6d}  ({pct:5.1f}%)')
    content = '\n'.join(lines) + '\n'
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'quality_report.txt').write_text(content, encoding='utf-8')
    return content

def generate_statistics_report(df: pd.DataFrame, ws_columns: List[str], dataset_name: str, report_dir: Path) -> str:
    lines = ['=' * 60, 'WIND SPEED STATISTICS REPORT', '=' * 60, '', f'Dataset : {dataset_name}', '']
    valid_ws = [c for c in ws_columns if c in df.columns]
    if not valid_ws:
        lines.append('No wind speed channels detected.')
    else:
        for col in valid_ws:
            series = pd.to_numeric(df[col], errors='coerce').dropna()
            h = extract_height(col)
            h_str = f' ({int(h)}m)' if h is not None and float(h).is_integer() else f' ({h}m)' if h else ''
            lines.append(f'─── {col}{h_str} ───')
            if series.empty:
                lines.append('    No valid data\n')
                continue
            lines.append(f'    Mean               : {series.mean():.3f} m/s')
            lines.append(f'    Median             : {series.median():.3f} m/s')
            lines.append(f'    Minimum            : {series.min():.3f} m/s')
            lines.append(f'    Maximum            : {series.max():.3f} m/s')
            lines.append(f'    Standard Deviation : {series.std():.3f} m/s')
            lines.append('')
    content = '\n'.join(lines) + '\n'
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / 'statistics_report.txt').write_text(content, encoding='utf-8')
    return content

@dataclass
class VisualizationResult:
    dataset_name: str
    viz_dir: Path
    report_dir: Path
    alpha: Optional[float] = None
    summary_text: str = ''
    quality_text: str = ''
    statistics_text: str = ''
    plots_created: List[str] = field(default_factory=list)
    sensors: Optional[SensorGroup] = None

def process_file(file_path: Path, viz_base: Path=Path('visualizations'), report_base: Path=Path('reports')) -> VisualizationResult:
    dataset_name = file_path.stem
    viz_dir = viz_base / dataset_name
    report_dir = report_base / dataset_name
    viz_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{'═' * 60}")
    print(f'  Processing: {file_path.name}')
    print(f"{'═' * 60}")
    if file_path.suffix.lower() == '.xlsx':
        df_raw = pd.read_excel(file_path)
    else:
        df_raw = pd.read_csv(file_path)
    sensors = detect_sensors(list(df_raw.columns))
    print(f'  Wind Speed channels  : {len(sensors.wind_speed)}')
    print(f'  Wind Direction       : {len(sensors.wind_direction)}')
    print(f'  Temperature          : {len(sensors.temperature)}')
    print(f'  Battery              : {len(sensors.battery)}')
    print(f'  Humidity             : {len(sensors.humidity)}')
    print(f'  Pressure             : {len(sensors.pressure)}')
    df_ts = _prepare_datetime(df_raw)
    result = VisualizationResult(dataset_name=dataset_name, viz_dir=viz_dir, report_dir=report_dir, sensors=sensors)
    if plot_wind_speed(df_ts, sensors.wind_speed, viz_dir):
        result.plots_created.append('wind_speed.png')
        print('  ✓ wind_speed.png')
    if plot_wind_direction(df_ts, sensors.wind_direction, viz_dir):
        result.plots_created.append('wind_direction.png')
        print('  ✓ wind_direction.png')
    if plot_temperature(df_ts, sensors.temperature, viz_dir):
        result.plots_created.append('temperature.png')
        print('  ✓ temperature.png')
    if plot_battery(df_ts, sensors.battery, viz_dir):
        result.plots_created.append('battery_voltage.png')
        print('  ✓ battery_voltage.png')
    if plot_humidity(df_ts, sensors.humidity, viz_dir):
        result.plots_created.append('humidity.png')
        print('  ✓ humidity.png')
    if plot_pressure(df_ts, sensors.pressure, viz_dir):
        result.plots_created.append('pressure.png')
        print('  ✓ pressure.png')
    if plot_wind_rose(df_ts, sensors.wind_speed, sensors.wind_direction, viz_dir):
        result.plots_created.append('wind_rose.png')
        print('  ✓ wind_rose.png')
    if plot_wind_shear_profile(df_ts, sensors.wind_speed, viz_dir):
        result.plots_created.append('wind_shear_profile.png')
        print('  ✓ wind_shear_profile.png')
    if plot_correlation_heatmap(df_ts, viz_dir):
        result.plots_created.append('correlation_heatmap.png')
        print('  ✓ correlation_heatmap.png')
    alpha = compute_wind_shear_exponent(df_ts, sensors.wind_speed)
    result.alpha = alpha
    if alpha is not None:
        print(f'  ✓ Wind Shear Exponent α = {alpha:.4f}')
    else:
        print('  ⚠ Wind Shear Exponent: insufficient heights')
    result.summary_text = generate_summary_report(df_raw, dataset_name, sensors, alpha, report_dir)
    print('  ✓ summary.txt')
    result.quality_text = generate_quality_report(df_raw, dataset_name, report_dir)
    print('  ✓ quality_report.txt')
    result.statistics_text = generate_statistics_report(df_ts, sensors.wind_speed, dataset_name, report_dir)
    print('  ✓ statistics_report.txt')
    print(f'\n  Plots created: {len(result.plots_created)}/9')
    print(f'  Visualizations → {viz_dir}')
    print(f'  Reports        → {report_dir}')
    return result

def process_all(output_dir: Path=Path('output'), viz_base: Path=Path('visualizations'), report_base: Path=Path('reports')) -> List[VisualizationResult]:
    files = sorted(list(output_dir.glob('*.csv')) + list(output_dir.glob('*.xlsx')))
    if not files:
        print(f'No CSV or XLSX files found in {output_dir}')
        return []
    print(f'\nFound {len(files)} dataset(s) in {output_dir}')
    results = []
    for f in files:
        try:
            result = process_file(f, viz_base, report_base)
            results.append(result)
        except Exception as exc:
            print(f'  ✗ Error processing {f.name}: {exc}')
            log_mod.exception('Error processing %s', f)
    return results

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='visualize_outputs.py', description='Generate visualizations and reports from decoded Kintech logger data.')
    parser.add_argument('--file', type=Path, default=None, help='Process a single CSV/XLSX file instead of scanning output/.')
    BASE_DIR = Path(__file__).resolve().parent
    parser.add_argument('--output-dir', type=Path, default=BASE_DIR / 'output', help='Directory containing decoded CSV/XLSX files (default: ./output).')
    parser.add_argument('--viz-dir', type=Path, default=BASE_DIR / 'visualizations', help='Directory for visualization output (default: ./visualizations).')
    parser.add_argument('--report-dir', type=Path, default=BASE_DIR / 'reports', help='Directory for text reports (default: ./reports).')
    parser.add_argument('--debug', action='store_true', help='Enable verbose debug logging.')
    return parser

def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=level, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
    if args.file:
        if not args.file.exists():
            print(f'File not found: {args.file}')
            return 1
        process_file(args.file, args.viz_dir, args.report_dir)
    else:
        process_all(args.output_dir, args.viz_dir, args.report_dir)
    return 0
if __name__ == '__main__':
    sys.exit(main())