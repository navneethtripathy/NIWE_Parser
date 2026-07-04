#!/usr/bin/env python3
"""
kintech_parser.py
==================
Command-line entry point for the Kintech Atlas data logger parser.

Reverse-engineered from Kintech Engineering "Atlas Output Data File" (.wnd)
format v2.0.0.342, cross-validated against Windographer-exported reference
files for site Narendra-IWSKA8 (logger S/N 9571112094).

Usage
-----
    python kintech_parser.py <input_file> <output_file> [options]

Examples
--------
    python kintech_parser.py logger.wnd output.csv
    python kintech_parser.py logger.wnd output.xlsx
    python kintech_parser.py logger.wnd output.txt --format windographer
    python kintech_parser.py logger.wnd output.csv --debug
    python kintech_parser.py logger.wnd output.csv --interval 10 --no-resample

See README.md for full documentation and REVERSE_ENGINEERING_REPORT.md for
the format specification this parser implements.
"""
import argparse
import logging
import sys
from pathlib import Path

from core.reader import KintechFileReader
from core.transform import RecordTransformer
from core.writer import write_output
from core.exceptions import KintechParseError


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kintech_parser.py",
        description="Parse Kintech data logger raw files (.wnd / Atlas format) "
        "into readable CSV/TXT/Excel output.",
    )
    parser.add_argument(
        "input_file",
        help="Path to the raw Kintech logger file (.wnd)"
    )
    parser.add_argument(
        "--format",
        choices=["raw", "windographer"],
        default="raw",
        help=(
            "Output column layout. 'raw' emits every channel/statistic exactly as "
            "stored in the logger file. 'windographer' reproduces the layout, "
            "derived columns (Gust, TI, WPD, Air Density) and timestamp convention "
            "used by Windographer exports (default)."
        ),
    )
    parser.add_argument(
        "--no-resample",
        action="store_true",
        help=(
            "Keep the native logger sampling interval (e.g. 5 min) instead of "
            "resampling to --interval minutes the way Windographer exports do."
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Target resampling interval in minutes for windographer-style output (default: 10).",
    )
    parser.add_argument(
        "--timestamp-shift",
        type=int,
        default=None,
        help=(
            "Minutes to subtract from each kept timestamp (Windographer convention: "
            "timestamps mark the START of the interval that just ended). "
            "Defaults to --interval when resampling, 0 otherwise."
        ),
    )
    parser.add_argument(
        "--no-fill-gaps",
        action="store_true",
        help="Do not insert blank rows for missing timestamps in the resampled grid.",
    )
    parser.add_argument(
        "--sheet-name", default="Data", help="Worksheet name when writing .xlsx output."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging of every parsing/transform step.",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress all logging except errors."
    )
    return parser


def configure_logging(debug: bool, quiet: bool) -> None:
    level = logging.ERROR if quiet else (logging.DEBUG if debug else logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    configure_logging(args.debug, args.quiet)
    log = logging.getLogger("kintech_parser")

    in_path = Path(args.input_file)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / f"{in_path.stem}.csv"
    
    if not in_path.exists():
        log.error("Input file not found: %s", in_path)
        return 2

    try:
        log.info("Reading raw Kintech file: %s", in_path)
        reader = KintechFileReader(in_path)
        parsed = reader.parse()
        log.info(
            "Parsed header OK. Site=%s LoggerSN=%s Channels=%d DataRows=%d",
            parsed.metadata.site_name,
            parsed.metadata.logger_serial,
            len(parsed.channels),
            len(parsed.records),
        )

        timestamp_shift = args.timestamp_shift
        if timestamp_shift is None:
            timestamp_shift = args.interval if not args.no_resample else 0
        
        print(f"Output style: {args.format}")
        
        transformer = RecordTransformer(
            parsed,
            output_style=args.format,
            resample=not args.no_resample,
            interval_minutes=args.interval,
            timestamp_shift_minutes=timestamp_shift,
            fill_gaps=not args.no_fill_gaps,
        )
        table = transformer.build_table()
        log.info("Built output table: %d rows x %d columns", len(table.rows), len(table.columns))

        write_output(table, out_path, sheet_name=args.sheet_name)
        log.info("Wrote output file: %s", out_path)

        if not args.debug and not args.quiet:
            print(f"✓ Parsed {len(parsed.records)} records")
            print(f"✓ Output written to {out_path}")

    except KintechParseError as exc:
        log.error("Parse error: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level CLI guard
        log.exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
