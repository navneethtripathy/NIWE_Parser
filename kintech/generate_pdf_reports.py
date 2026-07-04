#!/usr/bin/env python3
"""
generate_pdf_reports.py
=======================
PDF report generator for NIWE wind-resource-assessment deliverables.

Takes visualization results from ``visualize_outputs.py`` and produces a
multi-page PDF report using ReportLab, including:

  - Page 1: Title page with summary information
  - Pages 2–6: Embedded visualization plots
  - Final pages: Quality and statistics text reports

Usage
-----
    # Generate PDFs for all processed datasets
    python generate_pdf_reports.py

    # Generate PDF for a specific dataset
    python generate_pdf_reports.py --dataset ID150008_20210324_075740
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("generate_pdf_reports")


def _ensure_reportlab():
    """Import ReportLab with a helpful error if missing."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm, cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
            PageBreak, Table, TableStyle, Preformatted,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        return True
    except ImportError:
        print("ERROR: reportlab is not installed.")
        print("Install with: pip install reportlab")
        return False


def generate_pdf(
    dataset_name: str,
    viz_dir: Path,
    report_dir: Path,
    output_pdf_dir: Path,
    alpha: Optional[float] = None,
    summary_text: str = "",
    quality_text: str = "",
    statistics_text: str = "",
) -> Optional[Path]:
    """Generate a multi-page PDF report for a single dataset.

    Parameters
    ----------
    dataset_name : str
        Name of the dataset (used in titles and filename).
    viz_dir : Path
        Directory containing generated plot PNGs.
    report_dir : Path
        Directory containing text reports.
    output_pdf_dir : Path
        Directory where the PDF will be saved.
    alpha : float or None
        Wind shear exponent value.
    summary_text : str
        Content of summary.txt (used on title page).
    quality_text : str
        Content of quality_report.txt (appended at end).
    statistics_text : str
        Content of statistics_report.txt (appended at end).

    Returns
    -------
    Path or None
        Path to the generated PDF, or None on failure.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm, cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
            PageBreak, Table, TableStyle, Preformatted,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        print("ERROR: reportlab is not installed. Install with: pip install reportlab")
        return None

    output_pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_pdf_dir / f"{dataset_name}_report.pdf"

    page_w, page_h = A4
    margin = 2 * cm

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "NIWETitle",
        parent=styles["Title"],
        fontSize=24,
        leading=30,
        textColor=HexColor("#1a237e"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    subtitle_style = ParagraphStyle(
        "NIWESubtitle",
        parent=styles["Heading2"],
        fontSize=16,
        leading=22,
        textColor=HexColor("#283593"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "NIWEHeading",
        parent=styles["Heading1"],
        fontSize=18,
        leading=24,
        textColor=HexColor("#1a237e"),
        spaceAfter=12,
        spaceBefore=6,
    )

    body_style = ParagraphStyle(
        "NIWEBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )

    mono_style = ParagraphStyle(
        "NIWEMono",
        parent=styles["Code"],
        fontSize=8,
        leading=10,
        spaceAfter=4,
        fontName="Courier",
    )

    usable_width = page_w - 2 * margin

    elements = []

    # ─── PAGE 1: Title / Summary ────────────────────────────────────────

    elements.append(Spacer(1, 2 * cm))
    elements.append(Paragraph("NIWE Data Processing Report", title_style))
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(f"Dataset: {dataset_name}", subtitle_style))
    elements.append(Spacer(1, 1.5 * cm))

    # Summary table
    summary_lines = summary_text.strip().split("\n") if summary_text else []
    summary_data = []
    for line in summary_lines:
        line = line.strip()
        if not line or line.startswith("=") or line.startswith("─"):
            continue
        if ":" in line and not line.startswith("SUMMARY") and not line.startswith("Detected"):
            key, _, val = line.partition(":")
            summary_data.append([key.strip(), val.strip()])

    if summary_data:
        elements.append(Paragraph("Summary Information", heading_style))
        t = Table(summary_data, colWidths=[usable_width * 0.45, usable_width * 0.55])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#e8eaf6")),
            ("TEXTCOLOR", (0, 0), (-1, -1), HexColor("#1a237e")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (0, 0), (0, -1), "RIGHT"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#9fa8da")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [HexColor("#f5f5f5"), HexColor("#ffffff")]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 1 * cm))

    # Wind shear exponent highlight
    if alpha is not None:
        elements.append(Paragraph("Wind Shear Exponent", heading_style))
        alpha_data = [
            ["Wind Shear Exponent (α)", f"{alpha:.4f}"],
            ["Typical Range", "0.10 – 0.30"],
            ["Status", "Within Range ✓" if 0.10 <= alpha <= 0.30 else "Outside Typical Range ⚠"],
        ]
        t = Table(alpha_data, colWidths=[usable_width * 0.45, usable_width * 0.55])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), HexColor("#e8f5e9")),
            ("TEXTCOLOR", (0, 0), (-1, -1), HexColor("#1b5e20")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#81c784")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)

    # ─── PAGE 2: Wind Speed Plot ────────────────────────────────────────
    plot_pages = [
        ("Wind Speed Analysis", "wind_speed.png"),
        ("Wind Direction Analysis", "wind_direction.png"),
        ("Wind Rose", "wind_rose.png"),
        ("Wind Shear Profile", "wind_shear_profile.png"),
        ("Correlation Heatmap", "correlation_heatmap.png"),
    ]

    for page_title, plot_filename in plot_pages:
        plot_path = viz_dir / plot_filename
        if not plot_path.exists():
            continue
        elements.append(PageBreak())
        elements.append(Paragraph(page_title, heading_style))
        elements.append(Spacer(1, 0.5 * cm))

        # Scale image to fit page width while preserving aspect ratio
        try:
            from PIL import Image as PILImage
            with PILImage.open(plot_path) as img:
                img_w, img_h = img.size
            aspect = img_h / img_w
        except Exception:
            aspect = 0.5

        img_display_w = usable_width
        img_display_h = img_display_w * aspect
        max_h = page_h - 4 * margin
        if img_display_h > max_h:
            img_display_h = max_h
            img_display_w = img_display_h / aspect

        elements.append(
            RLImage(str(plot_path), width=img_display_w, height=img_display_h)
        )

    # ─── FINAL PAGES: Text reports ──────────────────────────────────────

    # Quality Report
    if quality_text:
        elements.append(PageBreak())
        elements.append(Paragraph("Data Quality Report", heading_style))
        elements.append(Spacer(1, 0.5 * cm))
        # Process text to fit in PDF
        for line in quality_text.strip().split("\n"):
            line = line.rstrip()
            if line.startswith("="):
                continue
            if line.startswith("─"):
                elements.append(Spacer(1, 4))
                continue
            if line.startswith("DATA QUALITY"):
                continue
            # Escape XML chars for ReportLab
            line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if line.strip():
                elements.append(Preformatted(line, mono_style))
            else:
                elements.append(Spacer(1, 4))

    # Statistics Report
    if statistics_text:
        elements.append(PageBreak())
        elements.append(Paragraph("Wind Speed Statistics", heading_style))
        elements.append(Spacer(1, 0.5 * cm))
        for line in statistics_text.strip().split("\n"):
            line = line.rstrip()
            if line.startswith("="):
                continue
            if line.startswith("WIND SPEED STATISTICS"):
                continue
            line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if line.strip():
                if line.startswith("───"):
                    elements.append(Spacer(1, 8))
                    elements.append(Paragraph(
                        line.replace("─", "").strip(),
                        ParagraphStyle("SensorHeading", parent=body_style,
                                       fontSize=11, fontName="Helvetica-Bold",
                                       textColor=HexColor("#1a237e"),
                                       spaceBefore=8, spaceAfter=4)
                    ))
                else:
                    elements.append(Preformatted(line, mono_style))
            else:
                elements.append(Spacer(1, 4))

    # Build PDF
    try:
        doc.build(elements)
        print(f"  ✓ PDF report → {pdf_path}")
        return pdf_path
    except Exception as exc:
        print(f"  ✗ PDF generation error: {exc}")
        log.exception("PDF generation failed for %s", dataset_name)
        return None


def generate_all_pdfs(
    viz_base: Path = Path("visualizations"),
    report_base: Path = Path("reports"),
    output_pdf_dir: Path = Path("reports"),
) -> List[Path]:
    """Generate PDFs for all datasets that have visualizations."""
    if not _ensure_reportlab():
        return []

    pdf_paths = []
    if not viz_base.exists():
        print(f"No visualizations directory found at {viz_base}")
        return []

    dataset_dirs = sorted([d for d in viz_base.iterdir() if d.is_dir()])
    if not dataset_dirs:
        print(f"No dataset subdirectories found in {viz_base}")
        return []

    for viz_dir in dataset_dirs:
        dataset_name = viz_dir.name
        report_dir = report_base / dataset_name

        # Load text reports if they exist
        summary_text = ""
        quality_text = ""
        statistics_text = ""
        alpha = None

        summary_path = report_dir / "summary.txt"
        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            # Extract alpha from summary
            for line in summary_text.split("\n"):
                if "Wind Shear Exponent" in line and ":" in line:
                    val_str = line.split(":")[-1].strip()
                    try:
                        alpha = float(val_str)
                    except ValueError:
                        pass

        quality_path = report_dir / "quality_report.txt"
        if quality_path.exists():
            quality_text = quality_path.read_text(encoding="utf-8")

        stats_path = report_dir / "statistics_report.txt"
        if stats_path.exists():
            statistics_text = stats_path.read_text(encoding="utf-8")

        pdf_path = generate_pdf(
            dataset_name=dataset_name,
            viz_dir=viz_dir,
            report_dir=report_dir,
            output_pdf_dir=output_pdf_dir,
            alpha=alpha,
            summary_text=summary_text,
            quality_text=quality_text,
            statistics_text=statistics_text,
        )
        if pdf_path:
            pdf_paths.append(pdf_path)

    return pdf_paths


# ─── CLI ────────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_pdf_reports.py",
        description="Generate PDF reports from Kintech visualization results.",
    )
    parser.add_argument(
        "--dataset", type=str, default=None,
        help="Generate PDF for a specific dataset name only.",
    )
    parser.add_argument(
        "--viz-dir", type=Path, default=Path("visualizations"),
        help="Base directory for visualizations (default: ./visualizations).",
    )
    parser.add_argument(
        "--report-dir", type=Path, default=Path("reports"),
        help="Base directory for text reports (default: ./reports).",
    )
    parser.add_argument(
        "--pdf-dir", type=Path, default=Path("reports"),
        help="Output directory for PDF reports (default: ./reports).",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not _ensure_reportlab():
        return 1

    if args.dataset:
        viz_dir = args.viz_dir / args.dataset
        report_dir = args.report_dir / args.dataset
        if not viz_dir.exists():
            print(f"Visualization directory not found: {viz_dir}")
            return 1

        # Load text reports
        summary_text = ""
        quality_text = ""
        statistics_text = ""
        alpha = None

        summary_path = report_dir / "summary.txt"
        if summary_path.exists():
            summary_text = summary_path.read_text(encoding="utf-8")
            for line in summary_text.split("\n"):
                if "Wind Shear Exponent" in line and ":" in line:
                    val_str = line.split(":")[-1].strip()
                    try:
                        alpha = float(val_str)
                    except ValueError:
                        pass

        quality_path = report_dir / "quality_report.txt"
        if quality_path.exists():
            quality_text = quality_path.read_text(encoding="utf-8")
        stats_path = report_dir / "statistics_report.txt"
        if stats_path.exists():
            statistics_text = stats_path.read_text(encoding="utf-8")

        generate_pdf(
            dataset_name=args.dataset,
            viz_dir=viz_dir,
            report_dir=report_dir,
            output_pdf_dir=args.pdf_dir,
            alpha=alpha,
            summary_text=summary_text,
            quality_text=quality_text,
            statistics_text=statistics_text,
        )
    else:
        generate_all_pdfs(args.viz_dir, args.report_dir, args.pdf_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
