import os
from pathlib import Path
from typing import Dict, List
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from windrose import WindroseAxes
from main import OUTPUTS_DIR, REPORTS_DIR, VISUALIZATIONS_DIR, detect_height_from_column, infer_sensor_columns

def create_visualizations_for_excel(excel_path: Path) -> Path:
    dataset_name = excel_path.stem
    output_dir = VISUALIZATIONS_DIR / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(excel_path)
    if 'Date/time' in df.columns:
        df['Date/time'] = pd.to_datetime(df['Date/time'], errors='coerce')
        df = df.dropna(subset=['Date/time']).sort_values('Date/time')
    elif df.columns[0].lower().startswith('date'):
        df[df.columns[0]] = pd.to_datetime(df[df.columns[0]], errors='coerce')
        df = df.dropna(subset=[df.columns[0]]).sort_values(df.columns[0])
    if 'Date/time' in df.columns:
        df = df.set_index('Date/time')
    elif len(df.columns) > 0:
        df = df.set_index(df.columns[0])
    sensor_columns = infer_sensor_columns(df)
    if sensor_columns['wind_speed']:
        wind_speed_columns = [column for column in sensor_columns['wind_speed'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not wind_speed_columns:
            wind_speed_columns = sensor_columns['wind_speed']
        wind_speed_df = df[wind_speed_columns].copy()
        wind_speed_df.columns = [str(col) for col in wind_speed_df.columns]
        plt.figure(figsize=(12, 6))
        for column in wind_speed_df.columns:
            plt.plot(wind_speed_df.index, wind_speed_df[column], label=column, linewidth=1.6)
        plt.xticks(rotation=30)
        plt.title('Wind Speed')
        plt.xlabel('Time')
        plt.ylabel('Wind Speed')
        plt.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_dir / 'wind_speed.png', dpi=300)
        plt.close()
    if sensor_columns['wind_direction']:
        direction_columns = [column for column in sensor_columns['wind_direction'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not direction_columns:
            direction_columns = sensor_columns['wind_direction']
        direction_df = df[direction_columns].copy()
        plt.figure(figsize=(12, 6))
        for column in direction_df.columns:
            plt.plot(direction_df.index, direction_df[column], label=column, linewidth=1.6)
        plt.xticks(rotation=30)
        plt.title('Wind Direction')
        plt.xlabel('Time')
        plt.ylabel('Direction (deg)')
        plt.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_dir / 'wind_direction.png', dpi=300)
        plt.close()
    if sensor_columns['temperature']:
        temp_columns = [column for column in sensor_columns['temperature'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not temp_columns:
            temp_columns = sensor_columns['temperature']
        temp_df = df[temp_columns].copy()
        plt.figure(figsize=(12, 6))
        for column in temp_df.columns:
            plt.plot(temp_df.index, temp_df[column], label=column, linewidth=1.6)
        plt.xticks(rotation=30)
        plt.title('Temperature')
        plt.xlabel('Time')
        plt.ylabel('Temperature')
        plt.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_dir / 'temperature.png', dpi=300)
        plt.close()
    if sensor_columns['battery']:
        batt_columns = [column for column in sensor_columns['battery'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not batt_columns:
            batt_columns = sensor_columns['battery']
        batt_df = df[batt_columns].copy()
        plt.figure(figsize=(12, 6))
        for column in batt_df.columns:
            plt.plot(batt_df.index, batt_df[column], label=column, linewidth=1.6)
        plt.xticks(rotation=30)
        plt.title('Battery Voltage')
        plt.xlabel('Time')
        plt.ylabel('Voltage')
        plt.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_dir / 'battery_voltage.png', dpi=300)
        plt.close()
    if sensor_columns['humidity']:
        hum_columns = [column for column in sensor_columns['humidity'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not hum_columns:
            hum_columns = sensor_columns['humidity']
        hum_df = df[hum_columns].copy()
        plt.figure(figsize=(12, 6))
        for column in hum_df.columns:
            plt.plot(hum_df.index, hum_df[column], label=column, linewidth=1.6)
        plt.xticks(rotation=30)
        plt.title('Humidity')
        plt.xlabel('Time')
        plt.ylabel('Humidity')
        plt.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_dir / 'humidity.png', dpi=300)
        plt.close()
    if sensor_columns['pressure']:
        pressure_columns = [column for column in sensor_columns['pressure'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not pressure_columns:
            pressure_columns = sensor_columns['pressure']
        pressure_df = df[pressure_columns].copy()
        plt.figure(figsize=(12, 6))
        for column in pressure_df.columns:
            plt.plot(pressure_df.index, pressure_df[column], label=column, linewidth=1.6)
        plt.xticks(rotation=30)
        plt.title('Pressure')
        plt.xlabel('Time')
        plt.ylabel('Pressure')
        plt.legend(loc='best')
        plt.tight_layout()
        plt.savefig(output_dir / 'pressure.png', dpi=300)
        plt.close()
    if sensor_columns['wind_speed'] and sensor_columns['wind_direction']:
        wind_speed_candidates = [column for column in sensor_columns['wind_speed'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        direction_candidates = [column for column in sensor_columns['wind_direction'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not wind_speed_candidates:
            wind_speed_candidates = sensor_columns['wind_speed']
        if not direction_candidates:
            direction_candidates = sensor_columns['wind_direction']
        wind_speed_series = pd.to_numeric(df[wind_speed_candidates[0]], errors='coerce')
        direction_series = pd.to_numeric(df[direction_candidates[0]], errors='coerce')
        clean = pd.DataFrame({'speed': wind_speed_series, 'direction': direction_series}).dropna()
        if not clean.empty:
            fig = plt.figure(figsize=(8, 8))
            ax = WindroseAxes.from_ax(fig=fig)
            ax.bar(clean['direction'], clean['speed'], bins=6, cmap=plt.cm.Blues, edgecolor='white')
            ax.set_legend(title='Speed')
            plt.title('Wind Rose')
            plt.tight_layout()
            fig.savefig(output_dir / 'wind_rose.png', dpi=300)
            plt.close(fig)
    if sensor_columns['wind_speed']:
        height_map: Dict[float, List[float]] = {}
        wind_speed_candidates = [column for column in sensor_columns['wind_speed'] if 'avg' in str(column).lower() or 'average' in str(column).lower() or 'mean' in str(column).lower()]
        if not wind_speed_candidates:
            wind_speed_candidates = sensor_columns['wind_speed']
        for column in wind_speed_candidates:
            height = detect_height_from_column(column)
            if height is None:
                continue
            series = pd.to_numeric(df[column], errors='coerce')
            if not series.dropna().empty:
                height_map.setdefault(height, []).append(float(series.mean()))
        if height_map:
            heights = sorted(height_map)
            means = [float(np.mean(height_map[h])) for h in heights]
            plt.figure(figsize=(8, 5))
            plt.plot(means, heights, marker='o', linestyle='-', color='tab:blue')
            for x, y in zip(means, heights):
                plt.annotate(f'{int(y)}m', (x, y), xytext=(4, 0), textcoords='offset points')
            plt.gca().invert_yaxis()
            plt.title('Wind Shear Profile')
            plt.xlabel('Mean Wind Speed')
            plt.ylabel('Height')
            plt.tight_layout()
            plt.savefig(output_dir / 'wind_shear_profile.png', dpi=300)
            plt.close()
    numeric_df = df.select_dtypes(include=[np.number]).copy()
    if numeric_df.shape[1] > 1:
        corr = numeric_df.corr(numeric_only=True)
        plt.figure(figsize=(10, 8))
        sns.heatmap(corr, cmap='coolwarm', square=True)
        plt.title('Correlation Heatmap')
        plt.tight_layout()
        plt.savefig(output_dir / 'correlation_heatmap.png', dpi=300)
        plt.close()
    return output_dir