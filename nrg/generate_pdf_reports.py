import json
import logging
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
logger = logging.getLogger(__name__)

def create_text_reports(dataset_name: str, metrics: dict, reports_dir: Path):
    summary_path = reports_dir / 'summary.txt'
    quality_path = reports_dir / 'quality_report.txt'
    stats_path = reports_dir / 'statistics_report.txt'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f'Dataset Name: {dataset_name}\n')
        f.write('=' * 40 + '\n')
        f.write(f"Rows: {metrics['rows']}\n")
        f.write(f"Columns: {metrics['columns']}\n\n")
        f.write(f"Start Time: {metrics['start_time']}\n")
        f.write(f"End Time: {metrics['end_time']}\n\n")
        alpha_str = f"{metrics['alpha']:.3f}" if metrics['alpha'] is not None else 'N/A'
        f.write(f'Wind Shear Exponent (alpha): {alpha_str}\n\n')
        f.write('Channels Found:\n')
        f.write(f"- Wind Speed Channels: {len(metrics['ws_cols'])}\n")
        f.write(f"- Wind Direction Channels: {len(metrics['wd_cols'])}\n")
        f.write(f"- Temperature Channels: {len(metrics['temp_cols'])}\n")
        f.write(f"- Battery Channels: {len(metrics['batt_cols'])}\n")
        f.write(f"- Humidity Channels: {len(metrics['hum_cols'])}\n")
        f.write(f"- Pressure Channels: {len(metrics['pres_cols'])}\n")
    with open(quality_path, 'w', encoding='utf-8') as f:
        f.write('Data Quality Report\n')
        f.write('=' * 40 + '\n')
        f.write(f"Rows: {metrics['rows']}\n")
        f.write(f"Columns: {metrics['columns']}\n")
        f.write(f"Total Cells: {metrics['total_cells']}\n")
        f.write(f"Missing Values: {metrics['total_missing']}\n")
        avail = 100.0 * (1 - metrics['total_missing'] / max(metrics['total_cells'], 1))
        f.write(f'Data Availability: {avail:.2f}%\n')
        f.write(f"Duplicate Timestamps: {metrics['duplicate_timestamps']}\n\n")
        f.write('Missing Values By Column:\n')
        for col, missing in metrics['missing_by_col'].items():
            if missing > 0:
                f.write(f'  {col}: {missing}\n')
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write('Statistics Report\n')
        f.write('=' * 40 + '\n')
        stats = metrics.get('stats', {})
        for col, s_dict in stats.items():
            f.write(f'\n{col}:\n')
            f.write(f"  Mean: {s_dict.get('mean', 'N/A'):.3f}\n")
            f.write(f"  Median: {s_dict.get('50%', 'N/A'):.3f}\n")
            f.write(f"  Minimum: {s_dict.get('min', 'N/A'):.3f}\n")
            f.write(f"  Maximum: {s_dict.get('max', 'N/A'):.3f}\n")
            f.write(f"  Standard Deviation: {s_dict.get('std', 'N/A'):.3f}\n")
    return (summary_path, quality_path, stats_path)

def generate_pdf(dataset_name: str, metrics: dict, viz_dir: Path, reports_dir: Path):
    pdf_path = reports_dir / f'{dataset_name}_report.pdf'
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    h1_style = styles['Heading1']
    h2_style = styles['Heading2']
    normal_style = styles['Normal']
    code_style = styles['Code']
    story = []
    story.append(Paragraph('NIWE Data Processing Report', title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f'Dataset Name: {dataset_name}', h1_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph('Summary Information', h2_style))
    story.append(Paragraph(f"Start Time: {metrics['start_time']}", normal_style))
    story.append(Paragraph(f"End Time: {metrics['end_time']}", normal_style))
    story.append(Paragraph(f"Rows: {metrics['rows']} | Columns: {metrics['columns']}", normal_style))
    story.append(Spacer(1, 10))
    alpha_str = f"{metrics['alpha']:.3f}" if metrics['alpha'] is not None else 'N/A'
    story.append(Paragraph(f'<b>Wind Shear Exponent (α):</b> {alpha_str}', normal_style))
    avail = 100.0 * (1 - metrics['total_missing'] / max(metrics['total_cells'], 1))
    story.append(Paragraph(f'<b>Data Availability:</b> {avail:.2f}%', normal_style))
    story.append(PageBreak())

    def add_plot_page(img_name: str, title: str):
        img_path = viz_dir / img_name
        if img_path.exists():
            story.append(Paragraph(title, h1_style))
            story.append(Spacer(1, 10))
            story.append(Image(str(img_path), width=450, height=350))
            story.append(PageBreak())
    add_plot_page('wind_speed.png', 'Wind Speed Plot')
    add_plot_page('wind_direction.png', 'Wind Direction Plot')
    add_plot_page('wind_rose.png', 'Wind Rose')
    add_plot_page('wind_shear_profile.png', 'Wind Shear Profile')
    add_plot_page('correlation_heatmap.png', 'Correlation Heatmap')

    def append_text_file(txt_name: str, title: str):
        txt_path = reports_dir / txt_name
        if txt_path.exists():
            story.append(Paragraph(title, h1_style))
            story.append(Spacer(1, 10))
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            for line in content.split('\n'):
                if not line.strip():
                    story.append(Spacer(1, 5))
                else:
                    story.append(Paragraph(line.replace(' ', '&nbsp;'), code_style))
            story.append(PageBreak())
    append_text_file('quality_report.txt', 'Data Quality Report')
    append_text_file('statistics_report.txt', 'Statistics Report')
    doc.build(story)
    logger.info(f'Generated PDF report: {pdf_path}')

def process_reports(dataset_name: str, metrics: dict, viz_dir: Path, reports_dir: Path):
    ds_reports_dir = reports_dir / dataset_name
    ds_reports_dir.mkdir(parents=True, exist_ok=True)
    create_text_reports(dataset_name, metrics, ds_reports_dir)
    generate_pdf(dataset_name, metrics, viz_dir, ds_reports_dir)