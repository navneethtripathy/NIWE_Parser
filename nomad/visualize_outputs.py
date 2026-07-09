from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from windrose import WindroseAxes
import numpy as np
import seaborn as sns
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / 'outputs'
VIS_DIR = BASE_DIR / 'visualizations'
VIS_DIR.mkdir(exist_ok=True)

def setup_time_axis():
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b'))
    plt.xticks(rotation=45)
    plt.tight_layout()
for excel_file in OUTPUT_DIR.glob('*.xlsx'):
    print(f'\nProcessing {excel_file.name}')
    try:
        df = pd.read_excel(excel_file, header=14)
        timestamp_col = df.columns[0]
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors='coerce')
        dataset_folder = VIS_DIR / excel_file.stem
        dataset_folder.mkdir(exist_ok=True)
        speed_cols = [str(c) for c in df.columns if 'Spd' in str(c) and 'SD' not in str(c) and ('Gust' not in str(c)) and ('Time' not in str(c))]
        if speed_cols:
            plt.figure(figsize=(14, 7))
            for col in speed_cols:
                plt.plot(df[timestamp_col], df[col], label=col)
            plt.title('Wind Speed')
            plt.xlabel('Time')
            plt.ylabel('Wind Speed (m/s)')
            plt.legend()
            setup_time_axis()
            plt.savefig(dataset_folder / 'wind_speed.png', bbox_inches='tight')
            plt.close()
        try:
            shear_heights = []
            shear_speeds = []
            for col in speed_cols:
                try:
                    height_text = col.split('Spd')[1].split('m')[0].strip()
                    height = float(height_text)
                    mean_speed = pd.to_numeric(df[col], errors='coerce').mean()
                    shear_heights.append(height)
                    shear_speeds.append(mean_speed)
                except Exception:
                    continue
            if len(shear_heights) >= 2:
                shear_data = sorted(zip(shear_heights, shear_speeds), key=lambda x: x[0])
                heights = [x[0] for x in shear_data]
                speeds = [x[1] for x in shear_data]
                wind_shear_alpha = None
                try:
                    if len(heights) >= 2:
                        v1 = speeds[0]
                        v2 = speeds[-1]
                        h1 = heights[0]
                        h2 = heights[-1]
                        wind_shear_alpha = np.log(v2 / v1) / np.log(h2 / h1)
                except Exception:
                    wind_shear_alpha = None
                plt.figure(figsize=(8, 6))
                plt.plot(speeds, heights, marker='o', linewidth=2)
                plt.title('Wind Shear Profile')
                plt.xlabel('Mean Wind Speed (m/s)')
                plt.ylabel('Height (m)')
                plt.grid(True)
                plt.savefig(dataset_folder / 'wind_shear_profile.png', bbox_inches='tight')
                plt.close()
        except Exception as e:
            print(f'Wind shear profile failed for {excel_file.name}: {e}')
        direction_cols = [str(c) for c in df.columns if 'Dir' in str(c) and 'SD' not in str(c)]
        if direction_cols:
            plt.figure(figsize=(14, 7))
            for col in direction_cols:
                plt.plot(df[timestamp_col], df[col], label=col)
            plt.title('Wind Direction')
            plt.xlabel('Time')
            plt.ylabel('Direction (°)')
            plt.legend()
            setup_time_axis()
            plt.savefig(dataset_folder / 'wind_direction.png', bbox_inches='tight')
            plt.close()
        if speed_cols and direction_cols:
            try:
                speed_col = speed_cols[0]
                direction_col = direction_cols[0]
                speed_data = pd.to_numeric(df[speed_col], errors='coerce')
                direction_data = pd.to_numeric(df[direction_col], errors='coerce')
                mask = speed_data.notna() & direction_data.notna()
                speed_data = speed_data[mask]
                direction_data = direction_data[mask]
                fig = plt.figure(figsize=(8, 8))
                ax = WindroseAxes.from_ax()
                ax.bar(direction_data, speed_data, normed=True, opening=0.8, edgecolor='white')
                ax.set_title(f'Wind Rose\n{speed_col}', pad=20)
                ax.set_legend(title='Wind Speed (m/s)')
                plt.savefig(dataset_folder / 'wind_rose.png', bbox_inches='tight')
                plt.close()
            except Exception as e:
                print(f'Wind rose failed for {excel_file.name}: {e}')
        temp_cols = [str(c) for c in df.columns if 'Tmp' in str(c)]
        if temp_cols:
            plt.figure(figsize=(14, 7))
            for col in temp_cols:
                plt.plot(df[timestamp_col], df[col], label=col)
            plt.title('Temperature')
            plt.xlabel('Time')
            plt.ylabel('Temperature (°C)')
            plt.legend()
            setup_time_axis()
            plt.savefig(dataset_folder / 'temperature.png', bbox_inches='tight')
            plt.close()
        battery_cols = [str(c) for c in df.columns if 'BattV' in str(c)]
        if battery_cols:
            plt.figure(figsize=(14, 7))
            for col in battery_cols:
                plt.plot(df[timestamp_col], df[col], label=col)
            plt.title('Battery Voltage')
            plt.xlabel('Time')
            plt.ylabel('Voltage (V)')
            plt.legend()
            setup_time_axis()
            plt.savefig(dataset_folder / 'battery_voltage.png', bbox_inches='tight')
            plt.close()
        humidity_cols = [str(c) for c in df.columns if 'Humidity' in str(c)]
        if humidity_cols:
            plt.figure(figsize=(14, 7))
            for col in humidity_cols:
                plt.plot(df[timestamp_col], df[col], label=col)
            plt.title('Humidity')
            plt.xlabel('Time')
            plt.ylabel('Humidity (%)')
            plt.legend()
            setup_time_axis()
            plt.savefig(dataset_folder / 'humidity.png', bbox_inches='tight')
            plt.close()
        pressure_cols = [str(c) for c in df.columns if 'mbar' in str(c)]
        if pressure_cols:
            plt.figure(figsize=(14, 7))
            for col in pressure_cols:
                plt.plot(df[timestamp_col], df[col], label=col)
            plt.title('Pressure')
            plt.xlabel('Time')
            plt.ylabel('Pressure (mbar)')
            plt.legend()
            setup_time_axis()
            plt.savefig(dataset_folder / 'pressure.png', bbox_inches='tight')
            plt.close()
        print(f'Created visualizations for {excel_file.stem}')
        try:
            numeric_df = df.select_dtypes(include=['number'])
            if len(numeric_df.columns) >= 2:
                corr_matrix = numeric_df.corr().round(2)
                plt.figure(figsize=(18, 14))
                sns.heatmap(corr_matrix, cmap='coolwarm', center=0, xticklabels=True, yticklabels=True)
                plt.title('Correlation Heatmap')
                plt.tight_layout()
                plt.savefig(dataset_folder / 'correlation_heatmap.png', bbox_inches='tight')
                plt.close()
        except Exception as e:
            print(f'Correlation heatmap failed for {excel_file.name}: {e}')
        summary_file = dataset_folder / 'summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f'Dataset: {excel_file.stem}\n')
            f.write('=' * 60 + '\n\n')
            f.write(f'Rows: {len(df)}\n')
            f.write(f'Columns: {len(df.columns)}\n\n')
            f.write(f'Start Time: {df[timestamp_col].min()}\n')
            f.write(f'End Time: {df[timestamp_col].max()}\n\n')
            if wind_shear_alpha is not None:
                f.write('Wind Shear Analysis\n')
                f.write('-------------------\n')
                f.write(f'Wind Shear Exponent (α): {wind_shear_alpha:.4f}\n\n')
            f.write('Wind Speed Channels\n')
            f.write('-------------------\n')
            for col in speed_cols:
                f.write(f'{col}\n')
            f.write('\nWind Direction Channels\n')
            f.write('-----------------------\n')
            for col in direction_cols:
                f.write(f'{col}\n')
            f.write('\nTemperature Channels\n')
            f.write('--------------------\n')
            for col in temp_cols:
                f.write(f'{col}\n')
            f.write('\nBattery Channels\n')
            f.write('----------------\n')
            for col in battery_cols:
                f.write(f'{col}\n')
            f.write('\nHumidity Channels\n')
            f.write('-----------------\n')
            for col in humidity_cols:
                f.write(f'{col}\n')
            f.write('\nPressure Channels\n')
            f.write('-----------------\n')
            for col in pressure_cols:
                f.write(f'{col}\n')
        quality_file = dataset_folder / 'quality_report.txt'
        missing_values = df.isna().sum().sum()
        total_cells = df.shape[0] * df.shape[1]
        availability = (total_cells - missing_values) / total_cells * 100 if total_cells > 0 else 0
        duplicate_timestamps = df[timestamp_col].duplicated().sum() if timestamp_col in df.columns else 0
        with open(quality_file, 'w') as f:
            f.write(f'Dataset: {excel_file.stem}\n')
            f.write('=' * 60 + '\n\n')
            f.write(f'Rows: {len(df)}\n')
            f.write(f'Columns: {len(df.columns)}\n\n')
            f.write(f'Start Time: {df[timestamp_col].min()}\n')
            f.write(f'End Time: {df[timestamp_col].max()}\n\n')
            f.write('Data Quality Summary\n')
            f.write('--------------------\n')
            f.write(f'Missing Values: {missing_values}\n')
            f.write(f'Total Cells: {total_cells}\n')
            f.write(f'Data Availability: {availability:.2f}%\n')
            f.write(f'Duplicate Timestamps: {duplicate_timestamps}\n\n')
            f.write('Missing Values By Column\n')
            f.write('------------------------\n')
            for col in df.columns:
                missing = df[col].isna().sum()
                f.write(f'{col}: {missing}\n')
        stats_file = dataset_folder / 'statistics_report.txt'
        with open(stats_file, 'w') as f:
            f.write(f'Dataset: {excel_file.stem}\n')
            f.write('=' * 60 + '\n\n')
            for col in speed_cols:
                values = pd.to_numeric(df[col], errors='coerce')
                f.write(f'{col}\n')
                f.write('-' * len(col) + '\n')
                f.write(f'Mean   : {values.mean():.3f}\n')
                f.write(f'Median : {values.median():.3f}\n')
                f.write(f'Min    : {values.min():.3f}\n')
                f.write(f'Max    : {values.max():.3f}\n')
                f.write(f'Std Dev: {values.std():.3f}\n\n')
    except Exception as e:
        print(f'Failed: {excel_file.name}')
        print(e)
print('\nVisualization generation completed.')