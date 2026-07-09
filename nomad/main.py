from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path
from analysis.binary_scanner import generate_file_map
from decoders import DECODER_REGISTRY, detect_decoder, get_decoder_by_name
from exporters.excel_exporter import export_workbook

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Universal data logger decoder -> Excel exporter')
    parser.add_argument('input_file', type=Path, help='Path to the raw logger file')
    parser.add_argument('--format', type=str, default=None, help="Force a specific decoder by name (e.g. 'nomad_ndf'). If omitted, auto-detect via sniff().")
    parser.add_argument('--output', type=Path, default=None, help='Output .xlsx path. Defaults to outputs/<input_stem>.xlsx')
    parser.add_argument('--start-time', type=str, default=None, help="Override the series start time, e.g. '2012-03-13 03:10' (only used by decoders that cannot recover a timestamp from the file itself -- see decoder findings report).")
    parser.add_argument('--interval-minutes', type=int, default=None, help='Override the sampling interval in minutes.')
    parser.add_argument('--analyze-only', action='store_true', help='Run only the Phase-1 binary structure scan and print a file map; do not attempt to decode or export.')
    parser.add_argument('--findings', action='store_true', help="Print the decoder's reverse-engineering findings report and exit.")
    return parser.parse_args(argv)

def decode_file(input_file, output_file=None, forced_format=None, start_time=None, interval_minutes=None):
    data = Path(input_file).read_bytes()
    decoder = get_decoder_by_name(forced_format) if forced_format else detect_decoder(data)
    if decoder is None:
        raise RuntimeError('No decoder recognized this file')
    metadata = decoder.parse_metadata(data)
    stream = decoder.parse_records(data, metadata, start_time=start_time, interval_minutes=interval_minutes)
    BASE_DIR = Path(__file__).resolve().parent
    output_path = output_file or BASE_DIR / 'outputs' / f'{Path(input_file).stem}.xlsx'
    export_workbook(stream, metadata, output_path, timezone_label=getattr(stream, 'timezone_label', None))
    return output_path

def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.input_file.exists():
        print(f'ERROR: input file not found: {args.input_file}', file=sys.stderr)
        return 1
    data = args.input_file.read_bytes()
    if args.analyze_only:
        print(generate_file_map(data))
        return 0
    decoder = get_decoder_by_name(args.format) if args.format else detect_decoder(data)
    if decoder is None:
        print('ERROR: no registered decoder recognized this file.', file=sys.stderr)
        print('Registered decoders:', [d.format_name for d in DECODER_REGISTRY], file=sys.stderr)
        print("Try --analyze-only to inspect the file's structure manually, or write a new decoder plugin (see decoders/base_decoder.py).", file=sys.stderr)
        return 2
    print(f'Detected format: {decoder.format_name}')
    if args.findings:
        print(decoder.describe_findings(data))
        return 0
    metadata = decoder.parse_metadata(data)
    print(metadata.summary())
    print()
    start_time = datetime.strptime(args.start_time, '%Y-%m-%d %H:%M') if args.start_time else None
    stream = decoder.parse_records(data, metadata, start_time=start_time, interval_minutes=args.interval_minutes)
    print(f'Detected interval: {stream.interval_minutes} minutes')
    print(f'Decoded {stream.num_scans} scans x {len(stream.slots)} channels ({stream.timestamps[0]} -> {stream.timestamps[-1]})')
    if getattr(stream, 'layout_confirmed', None) is False:
        print()
        print("WARNING: this file's sensor configuration did not match any previously")
        print('confirmed deployment layout. A best-effort, UNCONFIRMED slot mapping')
        print('(derived only from per-channel stub-record counts) was used instead.')
        print('Statistic labels (Avg/SD/Gust/etc.) for multi-slot channels may be')
        print('WRONG -- validate against a reference export before trusting this output.')
        print(f'Layout used: {stream.layout_name}')
        print()
    BASE_DIR = Path(__file__).resolve().parent
    output_path = args.output or BASE_DIR / 'outputs' / f"{args.input_file.stem or 'decoded'}.xlsx"
    written_paths = export_workbook(stream, metadata, output_path, timezone_label=getattr(stream, 'timezone_label', None))
    for p in written_paths:
        print(f'Wrote workbook: {p}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())