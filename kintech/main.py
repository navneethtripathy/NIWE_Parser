#!/usr/bin/env python3
"""
main.py
=======
Lightweight entry point for the Kintech data processing pipeline.

Orchestrates the full decode → visualize → report → PDF workflow,
or can be used to run individual pipeline stages.

Usage
-----
    # Full pipeline (same as batch_decode.py)
    python3 main.py

    # Only generate visualizations and reports from existing outputs
    python3 main.py --visualize-only

    # Only generate PDFs from existing visualizations
    python3 main.py --pdf-only

    # Process a single file
    python3 main.py --file output/ID150008.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Kintech data processing pipeline entry point.",
    )
    parser.add_argument(
        "--file", type=Path, default=None,
        help="Process a single CSV/XLSX file (visualization + reports only).",
    )
    parser.add_argument(
        "--visualize-only", action="store_true",
        help="Only generate visualizations and reports from existing outputs.",
    )
    parser.add_argument(
        "--pdf-only", action="store_true",
        help="Only generate PDF reports from existing visualizations.",
    )
    parser.add_argument(
        "--input-dir", type=Path, default=Path("input"),
        help="Directory containing raw .wnd files (default: ./input).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Directory for decoded CSV output (default: ./output).",
    )
    parser.add_argument(
        "--viz-dir", type=Path, default=Path("visualizations"),
        help="Directory for visualizations (default: ./visualizations).",
    )
    parser.add_argument(
        "--report-dir", type=Path, default=Path("reports"),
        help="Directory for reports (default: ./reports).",
    )
    parser.add_argument(
        "--format", choices=["raw", "windographer"], default="raw",
        help="Output column layout for decoding (default: raw).",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    # ── Single-file mode ────────────────────────────────────────────────
    if args.file:
        if not args.file.exists():
            print(f"File not found: {args.file}")
            return 1

        from visualize_outputs import process_file
        from generate_pdf_reports import generate_pdf

        result = process_file(args.file, args.viz_dir, args.report_dir)

        generate_pdf(
            dataset_name=result.dataset_name,
            viz_dir=result.viz_dir,
            report_dir=result.report_dir,
            output_pdf_dir=args.report_dir,
            alpha=result.alpha,
            summary_text=result.summary_text,
            quality_text=result.quality_text,
            statistics_text=result.statistics_text,
        )
        return 0

    # ── PDF-only mode ───────────────────────────────────────────────────
    if args.pdf_only:
        from generate_pdf_reports import generate_all_pdfs

        pdfs = generate_all_pdfs(args.viz_dir, args.report_dir, args.report_dir)
        print(f"\nGenerated {len(pdfs)} PDF report(s).")
        return 0

    # ── Visualize-only mode ─────────────────────────────────────────────
    if args.visualize_only:
        from visualize_outputs import process_all
        from generate_pdf_reports import generate_pdf

        results = process_all(args.output_dir, args.viz_dir, args.report_dir)
        for result in results:
            generate_pdf(
                dataset_name=result.dataset_name,
                viz_dir=result.viz_dir,
                report_dir=result.report_dir,
                output_pdf_dir=args.report_dir,
                alpha=result.alpha,
                summary_text=result.summary_text,
                quality_text=result.quality_text,
                statistics_text=result.statistics_text,
            )
        return 0

    # ── Full pipeline mode ──────────────────────────────────────────────
    from batch_decode import main as batch_main

    batch_args = []
    if args.input_dir != Path("input"):
        batch_args.extend(["--input-dir", str(args.input_dir)])
    if args.output_dir != Path("output"):
        batch_args.extend(["--output-dir", str(args.output_dir)])
    if args.viz_dir != Path("visualizations"):
        batch_args.extend(["--viz-dir", str(args.viz_dir)])
    if args.report_dir != Path("reports"):
        batch_args.extend(["--report-dir", str(args.report_dir)])
    if args.format != "raw":
        batch_args.extend(["--format", args.format])
    if args.debug:
        batch_args.append("--debug")

    return batch_main(batch_args)


if __name__ == "__main__":
    sys.exit(main())
