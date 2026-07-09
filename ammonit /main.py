import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / 'input'
OUTPUTS_DIR = ROOT / 'outputs'
PROCESSED_DIR = ROOT / 'processed'
VISUALIZATIONS_DIR = ROOT / 'visualizations'
REPORTS_DIR = ROOT / 'reports'

def normalize_name(value: object) -> str:
    if value is None:
        return ''
    text = str(value).lower()
    return re.sub('[^a-z0-9]+', ' ', text).strip()

def has_metric_keyword(column_name: object) -> bool:
    name = normalize_name(column_name)
    if not name:
        return False
    return bool(re.search('\\b(avg|average|mean)\\b', name))

def infer_sensor_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    sensor_columns: Dict[str, List[str]] = {'wind_speed': [], 'wind_direction': [], 'temperature': [], 'battery': [], 'humidity': [], 'pressure': []}
    for column in df.columns:
        name = normalize_name(column)
        if not name:
            continue
        is_stat_column = any((token in name for token in [' max ', ' min ', ' std', ' stddev', ' count ', ' median ']))
        is_avg_like = has_metric_keyword(column)
        if not is_avg_like and is_stat_column:
            continue
        if 'wind' in name and 'direction' not in name and ('speed' in name or 'spd' in name or 'ws' in name or ('anemometer' in name)):
            sensor_columns['wind_speed'].append(column)
        elif 'wind' in name and ('direction' in name or 'dir' in name or 'wd' in name):
            sensor_columns['wind_direction'].append(column)
        elif 'humidity' in name or 'rh' in name or 'relative humidity' in name or ('humid' in name):
            sensor_columns['humidity'].append(column)
        elif 'temperature' in name or 'temp' in name or 'tmp' in name:
            sensor_columns['temperature'].append(column)
        elif 'battery' in name or 'batt' in name or 'battv' in name or ('voltage' in name) or ('volt' in name):
            sensor_columns['battery'].append(column)
        elif 'pressure' in name or 'mbar' in name or 'hpa' in name or ('barometric' in name) or ('air pressure' in name) or ('air_pressure' in name):
            sensor_columns['pressure'].append(column)
    return sensor_columns

def detect_height_from_column(column_name: object) -> Optional[float]:
    if not isinstance(column_name, str):
        return None
    match = re.search('(\\d+(?:\\.\\d+)?)', column_name)
    if match:
        return float(match.group(1))
    return None

def parse_logger_file(file_path: Path) -> pd.DataFrame:
    df = pd.read_csv(file_path, low_memory=False)
    date_column = None
    for column in df.columns:
        if 'date' in normalize_name(column) or 'time' in normalize_name(column):
            date_column = column
            break
    if date_column is None and len(df.columns) > 0:
        date_column = df.columns[0]
    if date_column is not None:
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df.dropna(subset=[date_column]).sort_values(date_column).reset_index(drop=True)
        df = df.set_index(date_column)
    for column in df.columns:
        df[column] = pd.to_numeric(df[column], errors='coerce')
    return df

def create_excel_output(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df = df.reset_index()
    output_df.to_excel(output_path, index=False, engine='openpyxl')

def discover_raw_files() -> List[Path]:
    candidates: List[Path] = []
    for path in [ROOT, INPUT_DIR]:
        if not path.exists():
            continue
        for file_path in sorted(path.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in {'.csv', '.txt', '.xls', '.xlsx'}:
                if 'processed' not in str(file_path):
                    candidates.append(file_path)
    return candidates

def prepare_directories() -> None:
    for directory in [INPUT_DIR, OUTPUTS_DIR, PROCESSED_DIR, VISUALIZATIONS_DIR, REPORTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

def move_to_processed(source_path: Path) -> Path:
    destination = PROCESSED_DIR / source_path.name
    if source_path.exists():
        shutil.move(str(source_path), str(destination))
    return destination