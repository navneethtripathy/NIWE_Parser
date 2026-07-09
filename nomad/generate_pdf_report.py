from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Preformatted
from reportlab.lib.styles import getSampleStyleSheet
BASE_DIR = Path(__file__).resolve().parent
VIS_DIR = BASE_DIR / 'visualizations'
REPORTS_DIR = BASE_DIR / 'reports'
REPORTS_DIR.mkdir(exist_ok=True)
styles = getSampleStyleSheet()

def read_text_file(path):
    if not path.exists():
        return 'File not found.'
    return path.read_text(errors='ignore')
for dataset_folder in VIS_DIR.iterdir():
    if not dataset_folder.is_dir():
        continue
    dataset_name = dataset_folder.name
    pdf_path = REPORTS_DIR / f'{dataset_name}_report.pdf'
    doc = SimpleDocTemplate(str(pdf_path))
    elements = []
    elements.append(Paragraph('NIWE Nomad Data Processing Report', styles['Title']))
    elements.append(Paragraph(f'Dataset: {dataset_name}', styles['Heading2']))
    elements.append(Spacer(1, 20))
    summary_text = read_text_file(dataset_folder / 'summary.txt')
    elements.append(Preformatted(summary_text, styles['Code']))
    elements.append(PageBreak())
    image_files = [('Wind Speed', 'wind_speed.png'), ('Wind Direction', 'wind_direction.png'), ('Wind Rose', 'wind_rose.png'), ('Wind Shear Profile', 'wind_shear_profile.png'), ('Correlation Heatmap', 'correlation_heatmap.png'), ('Temperature', 'temperature.png'), ('Battery Voltage', 'battery_voltage.png'), ('Humidity', 'humidity.png'), ('Pressure', 'pressure.png')]
    for title, filename in image_files:
        image_path = dataset_folder / filename
        if image_path.exists():
            elements.append(Paragraph(title, styles['Heading1']))
            elements.append(Image(str(image_path), width=500, height=350))
            elements.append(PageBreak())
    quality_file = dataset_folder / 'quality_report.txt'
    if quality_file.exists():
        elements.append(Paragraph('Quality Report', styles['Heading1']))
        elements.append(Preformatted(read_text_file(quality_file), styles['Code']))
        elements.append(PageBreak())
    stats_file = dataset_folder / 'statistics_report.txt'
    if stats_file.exists():
        elements.append(Paragraph('Statistics Report', styles['Heading1']))
        elements.append(Preformatted(read_text_file(stats_file), styles['Code']))
    doc.build(elements)
    print(f'Created: {pdf_path}')
print('\nAll PDF reports generated.')