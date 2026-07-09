from pathlib import Path
from datetime import datetime
import subprocess
import shutil
import sys
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / 'input'
PROCESSED_DIR = BASE_DIR / 'processed'
PROCESSED_DIR.mkdir(exist_ok=True)
today = datetime.now().strftime('%Y-%m-%d')
processed_day = PROCESSED_DIR / today
processed_day.mkdir(exist_ok=True)
if not INPUT_DIR.exists():
    print('Input folder not found.')
    exit()
files = [f for f in INPUT_DIR.iterdir() if f.suffix.lower() == '.ndf']
print(f'Found {len(files)} file(s) to process.')
if not files:
    print('No NDF files found.')
    exit()
success = 0
failed = 0
for file in files:
    print(f'\nProcessing {file.name}')
    try:
        subprocess.run([sys.executable, str(BASE_DIR / 'main.py'), str(file)], check=True)
        destination = processed_day / file.name
        if destination.exists():
            destination = processed_day / f'{file.stem}_{int(datetime.now().timestamp())}{file.suffix}'
        shutil.move(str(file), str(destination))
        print(f'Completed {file.name}')
        print(f'Moved to {destination}')
        success += 1
    except subprocess.CalledProcessError as e:
        print(f'Failed {file.name}')
        print(e)
        failed += 1
print('\n========== SUMMARY ==========')
print(f'Successful: {success}')
print(f'Failed: {failed}')
print('\nGenerating visualizations...')
subprocess.run([sys.executable, str(BASE_DIR / 'visualize_outputs.py')], check=True)
print('\nGenerating PDF reports...')
subprocess.run([sys.executable, str(BASE_DIR / 'generate_pdf_report.py')], check=True)
print('\nPipeline completed successfully.')