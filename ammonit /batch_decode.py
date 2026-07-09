import shutil
from pathlib import Path
import numpy as np
import pandas as pd
from main import INPUT_DIR, OUTPUTS_DIR, PROCESSED_DIR, REPORTS_DIR, VISUALIZATIONS_DIR, create_excel_output, discover_raw_files, move_to_processed, parse_logger_file, prepare_directories, has_metric_keyword
from visualize_outputs import create_visualizations_for_excel
from generate_pdf_reports import build_pdf_report

def write_text_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def build_reports(df, dataset_name: str, output_dir: Path) -> None:
    report_dir = REPORTS_DIR / dataset_name
    report_dir.mkdir(parents=True, exist_ok=True)
    wind_speed_columns = [column for column in df.columns if ('speed' in str(column).lower() or 'spd' in str(column).lower() or 'ws' in str(column).lower() or ('anemometer' in str(column).lower())) and 'direction' not in str(column).lower() and has_metric_keyword(column)]
    wind_direction_columns = [column for column in df.columns if ('direction' in str(column).lower() or 'dir' in str(column).lower() or 'wd' in str(column).lower()) and has_metric_keyword(column)]
    temperature_columns = [column for column in df.columns if ('temperature' in str(column).lower() or 'temp' in str(column).lower() or 'tmp' in str(column).lower()) and has_metric_keyword(column)]
    battery_columns = [column for column in df.columns if ('battery' in str(column).lower() or 'batt' in str(column).lower() or 'voltage' in str(column).lower() or ('volt' in str(column).lower())) and has_metric_keyword(column)]
    humidity_columns = [column for column in df.columns if ('humidity' in str(column).lower() or 'rh' in str(column).lower() or 'humid' in str(column).lower()) and has_metric_keyword(column)]
    pressure_columns = [column for column in df.columns if ('pressure' in str(column).lower() or 'mbar' in str(column).lower() or 'hpa' in str(column).lower() or ('barometric' in str(column).lower()) or ('air pressure' in str(column).lower()) or ('air_pressure' in str(column).lower())) and has_metric_keyword(column)]
    start_time = df.index[0] if len(df.index) else 'N/A'
    end_time = df.index[-1] if len(df.index) else 'N/A'
    wind_speed_heights = {}
    for column in wind_speed_columns:
        height = None
        if '100' in str(column):
            height = 100
        elif '80' in str(column):
            height = 80
        elif '50' in str(column):
            height = 50
        elif '10' in str(column):
            height = 10
        else:
            height = None
        if height is None:
            continue
        series = pd.to_numeric(df[column], errors='coerce').dropna()
        if not series.empty:
            wind_speed_heights.setdefault(height, []).append(float(series.mean()))
    alpha_value = 'N/A'
    if len(wind_speed_heights) >= 2:
        heights = sorted(wind_speed_heights)
        if len(heights) >= 2 and wind_speed_heights[heights[0]] and wind_speed_heights[heights[1]]:
            v1 = float(np.mean(wind_speed_heights[heights[0]]))
            v2 = float(np.mean(wind_speed_heights[heights[1]]))
            if v1 > 0 and v2 > 0 and (heights[0] > 0) and (heights[1] > 0):
                alpha_value = f'{np.log(v2 / v1) / np.log(heights[1] / heights[0]):.4f}'
    summary_lines = [dataset_name, '', f'Rows: {len(df)}', f'Columns: {len(df.columns)}', '', f'Start Time: {start_time}', f'End Time: {end_time}', '', f'Wind Shear Exponent (α): {alpha_value}', '', f"Wind Speed Channels: {(', '.join(wind_speed_columns) if wind_speed_columns else 'None')}", f"Wind Direction Channels: {(', '.join(wind_direction_columns) if wind_direction_columns else 'None')}", f"Temperature Channels: {(', '.join(temperature_columns) if temperature_columns else 'None')}", f"Battery Channels: {(', '.join(battery_columns) if battery_columns else 'None')}", f"Humidity Channels: {(', '.join(humidity_columns) if humidity_columns else 'None')}", f"Pressure Channels: {(', '.join(pressure_columns) if pressure_columns else 'None')}"]
    write_text_report(report_dir / 'summary.txt', '\n'.join(summary_lines))
    missing_values = df.isna().sum()
    total_cells = df.size
    data_availability = (1 - missing_values.sum() / total_cells) * 100 if total_cells else 0
    duplicate_timestamps = int(df.index.duplicated().sum())
    quality_lines = [f'Rows: {len(df)}', f'Columns: {len(df.columns)}', '', f'Missing Values: {int(missing_values.sum())}', f'Total Cells: {int(total_cells)}', f'Data Availability %: {data_availability:.2f}', f'Duplicate Timestamps: {duplicate_timestamps}', '', 'Missing Values By Column']
    quality_lines.extend([f'{column}: {int(value)}' for column, value in missing_values.items()])
    write_text_report(report_dir / 'quality_report.txt', '\n'.join(quality_lines))
    statistics_lines = ['Statistics Report']
    for column in wind_speed_columns:
        series = pd.to_numeric(df[column], errors='coerce').dropna()
        if series.empty:
            continue
        statistics_lines.extend(['', f'Channel: {column}', f'Mean: {series.mean():.4f}', f'Median: {series.median():.4f}', f'Minimum: {series.min():.4f}', f'Maximum: {series.max():.4f}', f'Standard Deviation: {series.std():.4f}'])
    write_text_report(report_dir / 'statistics_report.txt', '\n'.join(statistics_lines))

def process_file(raw_path: Path) -> None:
    prepare_directories()
    dataset_name = raw_path.stem
    input_path = INPUT_DIR / raw_path.name
    if raw_path.parent != INPUT_DIR and raw_path.parent != PROCESSED_DIR:
        shutil.copy2(raw_path, input_path)
    elif raw_path.parent == INPUT_DIR and (not input_path.exists()):
        shutil.copy2(raw_path, input_path)
    parsed_df = parse_logger_file(input_path if input_path.exists() else raw_path)
    output_path = OUTPUTS_DIR / f'{dataset_name}.xlsx'
    create_excel_output(parsed_df, output_path)
    image_dir = create_visualizations_for_excel(output_path)
    build_reports(parsed_df, dataset_name, REPORTS_DIR / dataset_name)
    build_pdf_report(dataset_name, REPORTS_DIR / dataset_name, image_dir)
    move_to_processed(input_path)

def main() -> None:
    prepare_directories()
    raw_files = discover_raw_files()
    if not raw_files:
        print('No raw logger files were found.')
        return
    for raw_file in raw_files:
        if raw_file.is_dir():
            continue
        if raw_file.parent == PROCESSED_DIR:
            continue
        print(f'Processing {raw_file}')
        process_file(raw_file)
if __name__ == '__main__':
    main()