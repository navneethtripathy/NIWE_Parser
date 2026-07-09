import logging
import re
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from windrose import WindroseAxes
logger = logging.getLogger(__name__)
REGEX_WS = re.compile('Spd|Wind Speed|WS|Anemometer|WindSpeed', re.IGNORECASE)
REGEX_WD = re.compile('Dir|Direction|WD|WindDirection|Vane', re.IGNORECASE)
REGEX_TEMP = re.compile('Tmp|Temperature|Temp', re.IGNORECASE)
REGEX_BATT = re.compile('Batt|Battery|BattV|Voltage|Voltmtr', re.IGNORECASE)
REGEX_HUM = re.compile('Humidity|RH|Relative Humidity', re.IGNORECASE)
REGEX_PRES = re.compile('Pressure|mbar|hPa|Barometric|Baro', re.IGNORECASE)

def _find_columns(df: pd.DataFrame, regex: re.Pattern) -> list[str]:
    return [c for c in df.columns if regex.search(c) and 'Date' not in c]

def _extract_height(col_name: str) -> float | None:
    m = re.search('_(\\d+(?:\\.\\d+)?)m_', col_name)
    if m:
        return float(m.group(1))
    m2 = re.search('(\\d+(?:\\.\\d+)?)m', col_name, re.IGNORECASE)
    if m2:
        return float(m2.group(1))
    return None

def _setup_time_series(df: pd.DataFrame):
    if df.index.name != 'Date':
        date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]
        if date_cols:
            try:
                df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                df.set_index(date_cols[0], inplace=True)
            except Exception as e:
                logger.warning(f'Could not set datetime index: {e}')

def plot_time_series(df: pd.DataFrame, cols: list[str], output_path: Path, title: str, ylabel: str):
    if not cols:
        return
    plt.figure(figsize=(12, 6))
    for col in cols:
        plt.plot(df.index, df[col], label=col, alpha=0.7)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel('Datetime')
    plt.ylabel(ylabel)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize='small')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

def plot_wind_rose(df: pd.DataFrame, ws_cols: list[str], wd_cols: list[str], output_path: Path):
    if not ws_cols or not wd_cols:
        return
    ws_col = ws_cols[0]
    wd_col = wd_cols[0]
    valid_data = df[[ws_col, wd_col]].dropna()
    if valid_data.empty:
        return
    ax = WindroseAxes.from_ax()
    ax.bar(valid_data[wd_col], valid_data[ws_col], normed=True, opening=0.8, edgecolor='white')
    ax.set_legend(title='Wind Speed', loc='best')
    plt.title(f'Wind Rose ({ws_col} & {wd_col})', pad=20, fontsize=14, fontweight='bold')
    plt.savefig(output_path, dpi=150)
    plt.close()

def plot_wind_shear(df: pd.DataFrame, ws_cols: list[str], output_path: Path) -> float | None:
    avg_cols = [c for c in ws_cols if 'Avg' in c]
    if not avg_cols:
        avg_cols = ws_cols
    height_means = {}
    for col in avg_cols:
        h = _extract_height(col)
        if h is not None:
            mean_val = df[col].mean()
            if not pd.isna(mean_val):
                if h not in height_means:
                    height_means[h] = []
                height_means[h].append(mean_val)
    if len(height_means) < 2:
        return None
    final_heights = []
    final_speeds = []
    for h in sorted(height_means.keys()):
        final_heights.append(h)
        final_speeds.append(np.mean(height_means[h]))
    H1, H2 = (final_heights[0], final_heights[-1])
    V1, V2 = (final_speeds[0], final_speeds[-1])
    alpha = None
    if H1 > 0 and V1 > 0 and (H2 > H1):
        alpha = np.log(V2 / V1) / np.log(H2 / H1)
    plt.figure(figsize=(6, 8))
    plt.plot(final_speeds, final_heights, marker='o', linestyle='-', color='b')
    for s, h in zip(final_speeds, final_heights):
        plt.text(s, h, f'  {h}m', va='center', color='black', fontweight='bold')
    plt.title(f'Wind Shear Profile\n$\\alpha$ = {alpha:.3f}' if alpha else 'Wind Shear Profile', fontsize=14, fontweight='bold')
    plt.xlabel('Mean Wind Speed (m/s)')
    plt.ylabel('Height (m)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return alpha

def plot_correlation_heatmap(df: pd.DataFrame, output_path: Path):
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return
    plt.figure(figsize=(14, 12))
    corr = numeric_df.corr()
    corr.dropna(how='all', axis=0, inplace=True)
    corr.dropna(how='all', axis=1, inplace=True)
    sns.heatmap(corr, annot=False, cmap='coolwarm', center=0, cbar_kws={'label': 'Correlation'})
    plt.title('Correlation Heatmap', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()

def process_visualizations(excel_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(excel_path)
    _setup_time_series(df)
    ws_cols = _find_columns(df, REGEX_WS)
    wd_cols = _find_columns(df, REGEX_WD)
    temp_cols = _find_columns(df, REGEX_TEMP)
    batt_cols = _find_columns(df, REGEX_BATT)
    hum_cols = _find_columns(df, REGEX_HUM)
    pres_cols = _find_columns(df, REGEX_PRES)
    if ws_cols:
        plot_time_series(df, ws_cols, output_dir / 'wind_speed.png', 'Wind Speed Overview', 'Speed (m/s)')
    if wd_cols:
        plot_time_series(df, wd_cols, output_dir / 'wind_direction.png', 'Wind Direction Overview', 'Direction (deg)')
    if temp_cols:
        plot_time_series(df, temp_cols, output_dir / 'temperature.png', 'Temperature Overview', 'Temperature')
    if batt_cols:
        plot_time_series(df, batt_cols, output_dir / 'battery_voltage.png', 'Battery Voltage Overview', 'Voltage (V)')
    if hum_cols:
        plot_time_series(df, hum_cols, output_dir / 'humidity.png', 'Humidity Overview', 'Relative Humidity (%)')
    if pres_cols:
        plot_time_series(df, pres_cols, output_dir / 'pressure.png', 'Barometric Pressure Overview', 'Pressure')
    if ws_cols and wd_cols:
        plot_wind_rose(df, ws_cols, wd_cols, output_dir / 'wind_rose.png')
    alpha = None
    if ws_cols:
        alpha = plot_wind_shear(df, ws_cols, output_dir / 'wind_shear_profile.png')
    plot_correlation_heatmap(df, output_dir / 'correlation_heatmap.png')
    metrics = {'rows': len(df), 'columns': len(df.columns), 'start_time': str(df.index.min()) if not df.index.empty else 'N/A', 'end_time': str(df.index.max()) if not df.index.empty else 'N/A', 'alpha': alpha, 'ws_cols': ws_cols, 'wd_cols': wd_cols, 'temp_cols': temp_cols, 'batt_cols': batt_cols, 'hum_cols': hum_cols, 'pres_cols': pres_cols, 'missing_by_col': df.isnull().sum().to_dict(), 'total_cells': df.size, 'total_missing': df.isnull().sum().sum(), 'duplicate_timestamps': df.index.duplicated().sum() if df.index.name else 0, 'stats': df[ws_cols].describe().to_dict() if ws_cols else {}}
    return metrics