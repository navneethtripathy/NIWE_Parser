import json
import logging
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd
import shutil
import visualize_outputs
import generate_pdf_reports
BASE = Path(__file__).parent
with open(BASE / 'config.json', 'r') as f:
    config = json.load(f)
input_folder = BASE / config['input_folder']
txt_output = BASE / config['txt_output']
excel_output = BASE / config['excel_output']
logs_folder = BASE / config['logs_folder']
processed_folder = BASE / config.get('processed_folder', 'processed')
visualizations_folder = BASE / config.get('visualizations_folder', 'visualizations')
reports_folder = BASE / config.get('reports_folder', 'reports')
use_site_file = config.get('use_site_file', False)
site_file_path = config.get('site_file_path', '')
txt_output.mkdir(exist_ok=True, parents=True)
excel_output.mkdir(exist_ok=True, parents=True)
logs_folder.mkdir(exist_ok=True, parents=True)
processed_folder.mkdir(exist_ok=True, parents=True)
visualizations_folder.mkdir(exist_ok=True, parents=True)
reports_folder.mkdir(exist_ok=True, parents=True)
log_file = logs_folder / f"conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def find_data_start(txt_path: Path, encoding: str='latin-1') -> int:
    with open(txt_path, encoding=encoding) as fh:
        for idx, line in enumerate(fh):
            if line.startswith('Date'):
                return idx
    return 0
_SENSOR_TYPE_MAP = [('Anem', 'WindSpeed'), ('Vane', 'WindDirection'), ('Baro', 'BarometricPressure'), ('Temp', 'Temperature'), ('Voltmtr', 'BatteryVoltage'), ('Voltage', 'BatteryVoltage')]
_HEIGHT_OMIT_TYPES = {'BarometricPressure', 'Temperature', 'BatteryVoltage'}
_INVALID_SERIALS = {'', '0', 'nil', '--------', '––––'}

def _classify_sensor(description: str, channel_num: int) -> str:
    if 'No SCM Installed' in description:
        return f'UnusedChannel{channel_num}'
    for keyword, label in _SENSOR_TYPE_MAP:
        if keyword.lower() in description.lower():
            return label
    return f'Channel{channel_num}'

def _parse_height(raw: str) -> str | None:
    if not raw or raw.strip().startswith('--'):
        return None
    m = re.search('([\\d.]+)', raw)
    if m:
        val = m.group(1)
        try:
            if float(val) == 0:
                return None
        except ValueError:
            return None
        if '.' in val and float(val) == int(float(val)):
            val = str(int(float(val)))
        return val
    return None

def parse_channel_metadata(txt_path: Path, encoding: str='latin-1') -> dict[int, dict]:
    channels: dict[int, dict] = {}
    current_ch: int | None = None
    current: dict = {}
    with open(txt_path, encoding=encoding) as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith('Date'):
                break
            if stripped.startswith('Channel #'):
                if current_ch is not None:
                    channels[current_ch] = current
                parts = stripped.split('\t')
                current_ch = int(parts[1]) if len(parts) > 1 else None
                current = {}
            elif '\t' in stripped and current_ch is not None:
                key, _, value = stripped.partition('\t')
                key_lower = key.strip().lower()
                if key_lower == 'description':
                    current['description'] = value.strip()
                elif key_lower == 'serial number':
                    current['serial'] = value.strip()
                elif key_lower == 'height':
                    current['height_raw'] = value.strip()
        if current_ch is not None:
            channels[current_ch] = current
    return channels

def build_descriptive_headers(channel_meta: dict[int, dict], original_headers: list[str]) -> list[str]:
    ch_pattern = re.compile('^CH(\\d+)(Avg|SD|Max|Min)$', re.IGNORECASE)
    base_names: dict[int, str] = {}
    for ch_num, meta in sorted(channel_meta.items()):
        desc = meta.get('description', '')
        sensor = _classify_sensor(desc, ch_num)
        height = _parse_height(meta.get('height_raw', ''))
        serial_raw = meta.get('serial', '').strip()
        serial_valid = serial_raw.lower() not in _INVALID_SERIALS
        parts = [sensor]
        if height and sensor not in _HEIGHT_OMIT_TYPES:
            parts.append(f'{height}m')
        if serial_valid:
            parts.append(f'SN{serial_raw}')
        base_names[ch_num] = '_'.join(parts)
    from collections import Counter
    counts = Counter(base_names.values())
    seen: dict[str, int] = {}
    resolved: dict[int, str] = {}
    for ch_num in sorted(base_names):
        base = base_names[ch_num]
        if counts[base] > 1:
            idx = seen.get(base, 0) + 1
            seen[base] = idx
            resolved[ch_num] = f'{base}_{idx}'
        else:
            resolved[ch_num] = base
    new_headers: list[str] = []
    for hdr in original_headers:
        m = ch_pattern.match(hdr.strip())
        if m:
            ch_num = int(m.group(1))
            stat = m.group(2)
            stat_map = {'avg': 'Avg', 'sd': 'SD', 'max': 'Max', 'min': 'Min'}
            stat_label = stat_map.get(stat.lower(), stat)
            base = resolved.get(ch_num, f'CH{ch_num}')
            new_headers.append(f'{base}_{stat_label}')
        else:
            new_headers.append(hdr)
    return new_headers

def txt_to_excel(txt_path: Path, excel_path: Path, encoding: str='latin-1') -> None:
    skip = find_data_start(txt_path, encoding=encoding)
    df = pd.read_csv(txt_path, sep='\t', skiprows=skip, encoding=encoding, skip_blank_lines=True)
    df.dropna(axis=1, how='all', inplace=True)
    channel_meta = parse_channel_metadata(txt_path, encoding=encoding)
    if channel_meta:
        new_headers = build_descriptive_headers(channel_meta, list(df.columns))
        if len(new_headers) != len(df.columns):
            raise ValueError(f'Header count mismatch: {len(new_headers)} headers for {len(df.columns)} data columns')
        df.columns = new_headers
    df.to_excel(excel_path, index=False)

def convert_rwd_via_wine(rwd_files: list[Path], sdr_path: str, out_dir: Path, use_site_file: bool, site_file_path: str) -> list[Path]:
    wine_drive_c = Path(os.path.expanduser('~/.wine/drive_c'))
    raw_data_dir = wine_drive_c / 'NRG' / 'RawData'
    scaled_data_dir = wine_drive_c / 'NRG' / 'ScaledData'
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    scaled_data_dir.mkdir(parents=True, exist_ok=True)
    if use_site_file and site_file_path:
        command_switch = '/s'
        logger.info(f'Using site file mode (/s) with site file: {site_file_path}')
    else:
        command_switch = '/q'
        if not use_site_file:
            logger.info('No .NSF site file configured. Continuing without a site file.')
    produced_txt_files: list[Path] = []
    for rwd_file in rwd_files:
        logger.info(f'  Processing: {rwd_file.name}')
        wine_rwd_path = raw_data_dir / rwd_file.name
        shutil.copy2(str(rwd_file), str(wine_rwd_path))
        logger.debug(f'    Copied {rwd_file.name} → {wine_rwd_path}')
        windows_rwd_path = f'C:\\NRG\\RawData\\{rwd_file.name}'
        cmd = ['wine', sdr_path, command_switch, windows_rwd_path]
        logger.debug(f"    Wine command: {' '.join(cmd)}")
        existing_txt = set(scaled_data_dir.glob('*.txt'))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            logger.debug(f'    SDR exit code: {result.returncode}')
            if result.stdout.strip():
                logger.debug(f'    SDR stdout: {result.stdout.strip()}')
            if result.stderr.strip():
                stderr_lines = result.stderr.strip().split('\n')
                important_lines = [l for l in stderr_lines if not l.startswith('[mvk-') and (not l.startswith('\t')) and l.strip()]
                if important_lines:
                    logger.warning(f'    SDR stderr: {chr(10).join(important_lines)}')
        except subprocess.TimeoutExpired:
            logger.error(f'    SDR timed out processing {rwd_file.name}')
            continue
        except FileNotFoundError:
            logger.error("    'wine' command not found. Please install Wine on your Mac.")
            logger.error('    Install via: brew install --cask wine-stable')
            return produced_txt_files
        new_txt = set(scaled_data_dir.glob('*.txt')) - existing_txt
        if new_txt:
            for txt_file in new_txt:
                dest = out_dir / txt_file.name
                shutil.copy2(str(txt_file), str(dest))
                logger.info(f'    ✓ TXT created: {txt_file.name}')
                produced_txt_files.append(dest)
                try:
                    os.remove(str(txt_file))
                except OSError:
                    pass
        else:
            logger.warning(f'    ✗ No TXT output for {rwd_file.name}')
            logger.warning(f'      RWD input path : {rwd_file}')
            logger.warning(f'      Wine RWD path  : {wine_rwd_path}')
            logger.warning(f'      Windows path   : {windows_rwd_path}')
            logger.warning(f'      SDR path       : {sdr_path}')
            logger.warning(f'      TXT output dir : {scaled_data_dir}')
            logger.warning(f"      Command used   : {' '.join(cmd)}")
            if result.returncode != 0:
                logger.warning(f'      SDR exit code  : {result.returncode}')
            logger.warning('      This may indicate a missing .NSF site file for this logger.')
            logger.warning('      Obtain the .NSF from the logger/project owner, place it in')
            logger.warning("      the SiteFiles folder, and set 'use_site_file': true in config.json.")
    return produced_txt_files
sdr_path = config['sdr_path']
if not os.path.exists(sdr_path):
    logger.error(f'SDR.exe not found at: {sdr_path}')
    logger.error("Please install NRG SDR or update 'sdr_path' in config.json")
    sys.exit(1)
if not input_folder.exists():
    logger.error(f'Input folder not found: {input_folder}')
    sys.exit(1)
rwd_files = list(input_folder.glob('*.RWD')) + list(input_folder.glob('*.rwd'))
if not rwd_files:
    logger.warning(f'No RWD files found in: {input_folder}')
    sys.exit(0)
logger.info(f'Found {len(rwd_files)} RWD file(s) in {input_folder}')
logger.info('Starting RWD to TXT conversion via SDR ...')
logger.debug(f'  Platform       : {platform.system()}')
logger.debug(f'  SDR path       : {sdr_path}')
logger.debug(f'  Input folder   : {input_folder}')
logger.debug(f'  TXT output     : {txt_output}')
logger.debug(f'  Use site file  : {use_site_file}')
if platform.system() == 'Darwin':
    logger.info('Detected macOS — using Wine to run SDR.exe')
    try:
        wine_version = subprocess.run(['wine', '--version'], capture_output=True, text=True, timeout=10)
        logger.debug(f'  Wine version: {wine_version.stdout.strip()}')
    except FileNotFoundError:
        logger.error('Wine is not installed. Please install it:')
        logger.error('  brew install --cask wine-stable')
        sys.exit(1)
    produced_txt = convert_rwd_via_wine(rwd_files, sdr_path, txt_output, use_site_file, site_file_path)
    logger.info(f'RWD to TXT conversion complete. {len(produced_txt)} file(s) produced.')
else:
    import nrgpy
    rwd_dir_str = str(input_folder) + os.sep
    try:
        converter = nrgpy.local_rwd(rwd_dir=rwd_dir_str, out_dir=str(txt_output), sdr_path=sdr_path, use_site_file=use_site_file)
        converter.convert()
        logger.info('RWD to TXT conversion complete.')
    except Exception as e:
        logger.exception(f'Conversion failed: {e}')
        sys.exit(1)
txt_files = list(txt_output.glob('*.txt'))
if not txt_files:
    logger.warning('No TXT files produced by SDR.')
    logger.warning('Possible causes:')
    logger.warning('  1. SDR requires a .NSF site file for this logger serial number.')
    logger.warning('  2. The .RWD files may be corrupted or from an unsupported logger.')
    logger.warning('To fix: obtain the .NSF file from the logger/project owner,')
    logger.warning("  set 'use_site_file': true and 'site_file_path': '/path/to/file.nsf' in config.json.")
    logger.info('Pipeline finishing gracefully without TXT files.')
    sys.exit(0)
logger.info(f'Converting {len(txt_files)} TXT file(s) to Excel ...')
success_count = 0
fail_count = 0
for txt_file in sorted(txt_files):
    excel_file = excel_output / f'{txt_file.stem}.xlsx'
    try:
        txt_to_excel(txt_file, excel_file)
        logger.info(f'  Excel created: {excel_file.name}')
        dataset_name = excel_file.stem
        dataset_viz_dir = visualizations_folder / dataset_name
        metrics = visualize_outputs.process_visualizations(excel_file, dataset_viz_dir)
        logger.info(f'  Visualizations generated for {dataset_name}')
        generate_pdf_reports.process_reports(dataset_name, metrics, dataset_viz_dir, reports_folder)
        logger.info(f'  Reports generated for {dataset_name}')
        raw_rwd = input_folder / f'{dataset_name}.RWD'
        if not raw_rwd.exists():
            raw_rwd = input_folder / f'{dataset_name}.rwd'
        if raw_rwd.exists():
            shutil.move(str(raw_rwd), str(processed_folder / raw_rwd.name))
            logger.info(f'  Moved {raw_rwd.name} to processed folder')
        success_count += 1
    except Exception as e:
        logger.error(f'  Failed to convert {txt_file.name}: {e}')
        fail_count += 1
logger.info('------------------------------------------')
logger.info(f'Excel files created : {success_count}')
if fail_count:
    logger.warning(f'Failures            : {fail_count}')
logger.info(f'Output folder       : {excel_output}')
logger.info(f'Log saved to        : {log_file}')
logger.info('Done.')