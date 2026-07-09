from pathlib import Path
from typing import Dict
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from main import REPORTS_DIR

def build_pdf_report(dataset_name: str, report_dir: Path, image_dir: Path) -> Path:
    pdf_path = REPORTS_DIR / f'{dataset_name}_report.pdf'
    report_dir.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    story = []
    story.append(Paragraph('NIWE Data Processing Report', styles['Title']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f'Dataset: {dataset_name}', styles['Heading2']))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph('Summary Information', styles['Heading3']))
    story.append(Spacer(1, 0.1 * inch))
    summary_text = (report_dir / 'summary.txt').read_text(encoding='utf-8') if (report_dir / 'summary.txt').exists() else 'Summary report not available.'
    story.append(Paragraph(summary_text.replace('\n', '<br />'), styles['BodyText']))
    story.append(PageBreak())
    images = [('Wind Speed Plot', image_dir / 'wind_speed.png'), ('Wind Direction Plot', image_dir / 'wind_direction.png'), ('Wind Rose', image_dir / 'wind_rose.png'), ('Wind Shear Profile', image_dir / 'wind_shear_profile.png'), ('Correlation Heatmap', image_dir / 'correlation_heatmap.png')]
    for title, image_path in images:
        if image_path.exists():
            story.append(Paragraph(title, styles['Heading2']))
            story.append(Spacer(1, 0.1 * inch))
            story.append(Image(str(image_path), width=6.5 * inch, height=4 * inch))
            story.append(PageBreak())
    quality_path = report_dir / 'quality_report.txt'
    statistics_path = report_dir / 'statistics_report.txt'
    if quality_path.exists():
        story.append(Paragraph('Quality Report', styles['Heading2']))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(quality_path.read_text(encoding='utf-8').replace('\n', '<br />'), styles['BodyText']))
        story.append(PageBreak())
    if statistics_path.exists():
        story.append(Paragraph('Statistics Report', styles['Heading2']))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(statistics_path.read_text(encoding='utf-8').replace('\n', '<br />'), styles['BodyText']))
    doc.build(story)
    return pdf_path