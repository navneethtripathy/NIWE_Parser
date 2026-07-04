#!/usr/bin/env python3
"""
batch_decode.py
===============
End-to-end automation for the Kintech data processing pipeline.

Runs the complete workflow from a single command::

    python3 batch_decode.py

Pipeline stages:

    1. Scan ``input/`` for .wnd files
    2. Parse each file → write CSV to ``output/``
    3. Generate visualizations for all decoded files
    4. Generate text reports (summary, quality, statistics)
    5. Generate PDF reports
    6. Move processed .wnd files to ``processed/``

Usage
-----
    # Full pipeline (default)
    python3 batch_decode.py

    # Skip decode stage (only visualize/report existing outputs)
    python3 batch_decode.py --skip-decode

    # Custom directories
    python3 batch_decode.py --input-dir /data/incoming --output-dir /data/decoded

    # Use windographer output format for decoding
    python3 batch_decode.py --format windographer
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("batch_decode")


def decode_wnd_files(
    input_dir: Path,
    output_dir: Path,
    output_format: str = "raw",
) -> List[Path]:
    """Parse all .wnd files in the input directory and write CSV output.

    Returns a list of successfully parsed input file paths.
    """
    from core.reader import KintechFileReader
    from core.transform import RecordTransformer
    from core.writer import write_output
    from core.exceptions import KintechParseError

    wnd_files = sorted(input_dir.glob("*.wnd"))
    if not wnd_files:
        print(f"  No .wnd files found in {input_dir}")
        return []

    print(f"\n  Found {len(wnd_files)} .wnd file(s) in {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    decoded = []
    for wnd_path in wnd_files:
        try:
            print(f"  Parsing: {wnd_path.name} ... ", end="", flush=True)
            reader = KintechFileReader(wnd_path)
            parsed = reader.parse()

            transformer = RecordTransformer(
                parsed,
                output_style=output_format,
                resample=(output_format == "windographer"),
                interval_minutes=10,
                timestamp_shift_minutes=10 if output_format == "windographer" else 0,
                fill_gaps=(output_format == "windographer"),
            )
            table = transformer.build_table()

            out_path = output_dir / f"{wnd_path.stem}.csv"
            write_output(table, out_path)

            print(f"✓ {len(parsed.records)} records → {out_path.name}")
            decoded.append(wnd_path)

        except KintechParseError as exc:
            print(f"✗ Parse error: {exc}")
            log.error("Parse error for %s: %s", wnd_path.name, exc)
        except Exception as exc:
            print(f"✗ Error: {exc}")
            log.exception("Unexpected error processing %s", wnd_path.name)

    return decoded


def move_to_processed(
    files: List[Path],
    processed_dir: Path,
) -> None:
    """Move successfully processed .wnd files to the processed directory."""
    if not files:
        return

    processed_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        dest = processed_dir / f.name
        if dest.exists():
            stem = f.stem
            suffix = f.suffix
            counter = 1
            while dest.exists():
                dest = processed_dir / f"{stem}_{counter}{suffix}"
                counter += 1
        try:
            shutil.move(str(f), str(dest))
            print(f"  Moved {f.name} → processed/")
        except Exception as exc:
            print(f"  ✗ Could not move {f.name}: {exc}")
            log.error("Failed to move %s: %s", f.name, exc)


# ─── CLI ────────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="batch_decode.py",
        description=(
            "End-to-end Kintech data processing pipeline: decode → visualize → report → PDF."
        ),
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
        "--processed-dir", type=Path, default=Path("processed"),
        help="Directory to move processed .wnd files (default: ./processed).",
    )
    parser.add_argument(
        "--viz-dir", type=Path, default=Path("visualizations"),
        help="Directory for visualizations (default: ./visualizations).",
    )
    parser.add_argument(
        "--report-dir", type=Path, default=Path("reports"),
        help="Directory for reports and PDFs (default: ./reports).",
    )
    parser.add_argument(
        "--format", choices=["raw", "windographer"], default="raw",
        help="Output column layout for decoding (default: raw).",
    )
    parser.add_argument(
        "--skip-decode", action="store_true",
        help="Skip decoding stage — only run visualization/reporting on existing outputs.",
    )
    parser.add_argument(
        "--no-move", action="store_true",
        help="Don't move .wnd files to processed/ after decoding.",
    )
    parser.add_argument(
        "--no-pdf", action="store_true",
        help="Skip PDF report generation.",
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

    start = time.time()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Kintech Data Processing Pipeline                       ║")
    print("║     Decode → Visualize → Report → PDF                      ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  Input          : {str(args.input_dir):<42} ║")
    print(f"║  Output         : {str(args.output_dir):<42} ║")
    print(f"║  Visualizations : {str(args.viz_dir):<42} ║")
    print(f"║  Reports        : {str(args.report_dir):<42} ║")
    print(f"║  Processed      : {str(args.processed_dir):<42} ║")
    print(f"║  Format         : {args.format:<42} ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Ensure directories exist
    for d in [args.input_dir, args.output_dir, args.viz_dir, args.report_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Decode ─────────────────────────────────────────────────
    decoded_files = []
    if not args.skip_decode:
        print("\n┌─ Stage 1: Decoding .wnd files ─────────────────────────────┐")
        decoded_files = decode_wnd_files(
            args.input_dir, args.output_dir, args.format
        )
        if decoded_files:
            print(f"  Decoded {len(decoded_files)} file(s) successfully.")
        else:
            print("  No new files decoded (input/ may be empty).")
        print("└────────────────────────────────────────────────────────────┘")
    else:
        print("\n  ⏭  Skipping decode stage (--skip-decode)")

    # ── Stage 2: Visualizations + Text Reports ──────────────────────────
    print("\n┌─ Stage 2: Generating Visualizations & Reports ─────────────┐")
    from visualize_outputs import process_all
    results = process_all(args.output_dir, args.viz_dir, args.report_dir)
    print(f"\n  Processed {len(results)} dataset(s).")
    print("└────────────────────────────────────────────────────────────┘")

    # ── Stage 3: PDF Reports ────────────────────────────────────────────
    if not args.no_pdf:
        print("\n┌─ Stage 3: Generating PDF Reports ──────────────────────────┐")
        from generate_pdf_reports import generate_pdf
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
        print("└────────────────────────────────────────────────────────────┘")
    else:
        print("\n  ⏭  Skipping PDF generation (--no-pdf)")

    # ── Stage 4: Move processed files ───────────────────────────────────
    if decoded_files and not args.no_move:
        print("\n┌─ Stage 4: Moving processed files ──────────────────────────┐")
        move_to_processed(decoded_files, args.processed_dir)
        print("└────────────────────────────────────────────────────────────┘")

    elapsed = time.time() - start
    print(f"\n{'═' * 62}")
    print(f"  Pipeline complete in {elapsed:.1f}s")
    print(f"  Datasets processed : {len(results)}")
    total_plots = sum(len(r.plots_created) for r in results)
    print(f"  Plots generated    : {total_plots}")
    print(f"  Visualizations     → {args.viz_dir}/")
    print(f"  Reports            → {args.report_dir}/")
    print(f"{'═' * 62}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
