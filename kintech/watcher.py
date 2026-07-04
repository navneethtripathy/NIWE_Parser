#!/usr/bin/env python3
"""
watcher.py
==========
Folder watcher for automatic Kintech .wnd file decoding.

Monitors a designated input folder for new .wnd files and automatically
parses them using the Kintech parser pipeline, writing decoded CSV output
to the output folder. Processed files are moved to a "processed/" subfolder
so they are not re-parsed.

Usage
-----
    # Watch the default 'input/' folder (creates it if missing):
    python watcher.py

    # Watch a custom folder with 8 concurrent worker threads:
    python watcher.py --watch-dir /path/to/incoming --workers 8

    # Process all existing .wnd files once and exit (no watching):
    python watcher.py --once

    # Use polling mode (no watchdog dependency needed):
    python watcher.py --poll --interval 5

Options
-------
    --watch-dir DIR      Folder to watch for .wnd files (default: ./input)
    --output-dir DIR     Folder to write decoded CSVs (default: ./output)
    --processed-dir DIR  Folder to move processed files (default: ./processed)
    --format FMT         Output format: raw or windographer (default: raw)
    --once               Process existing files and exit, don't watch
    --poll               Use polling instead of watchdog (no extra deps)
    --interval SECS      Polling interval in seconds (default: 3)
    --no-move            Don't move files after processing (leave in place)
    --workers INT        Number of concurrent workers (default: auto-detected)
    --debug              Enable verbose logging
"""
import argparse
import logging
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

from core.reader import KintechFileReader
from core.transform import RecordTransformer
from core.writer import write_output
from core.exceptions import KintechParseError

log = logging.getLogger("watcher")

# Global locks and tracking
_processed_lock = threading.Lock()
_processed_set: set[str] = set()


def parse_file(input_path: Path, output_dir: Path, output_format: str) -> Path | None:
    """Parse a single .wnd file and write the CSV output.

    Returns the output path on success, None on failure.
    """
    try:
        log.info("Parsing: %s", input_path.name)
        reader = KintechFileReader(input_path)
        parsed = reader.parse()

        transformer = RecordTransformer(
            parsed,
            output_style=output_format,
            resample=True,
            interval_minutes=10,
            timestamp_shift_minutes=10,
            fill_gaps=True,
        )
        table = transformer.build_table()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{input_path.stem}.csv"
        write_output(table, out_path)

        print(f"  ✓ Decoded {input_path.name} → {out_path}  "
              f"({len(parsed.records)} records, {len(table.rows)} output rows)")
        return out_path

    except KintechParseError as exc:
        print(f"  ✗ Parse error for {input_path.name}: {exc}")
        log.error("Parse error: %s — %s", input_path.name, exc)
        return None
    except Exception as exc:
        print(f"  ✗ Unexpected error for {input_path.name}: {exc}")
        log.exception("Unexpected error processing %s", input_path.name)
        return None


def handle_file_thread(
    file_path: Path,
    output_dir: Path,
    processed_dir: Path | None,
    output_format: str,
) -> None:
    """Worker function to process a single file concurrently."""
    # Wait briefly for the file to be fully written (copy in progress)
    _wait_for_stable(file_path)

    result = parse_file(file_path, output_dir, output_format)
    if result is not None:
        if processed_dir is not None:
            processed_dir.mkdir(parents=True, exist_ok=True)
            dest = processed_dir / file_path.name

            # Acquire lock to safely calculate non-colliding filename and move
            with _processed_lock:
                if dest.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    counter = 1
                    while dest.exists():
                        dest = processed_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                try:
                    shutil.move(str(file_path), str(dest))
                    log.info("Moved %s → %s", file_path.name, dest)
                except Exception as exc:
                    log.error("Failed to move %s to %s: %s", file_path.name, dest, exc)


def _wait_for_stable(path: Path, checks: int = 3, wait: float = 0.5) -> None:
    """Wait until the file size stops changing (file copy finished)."""
    prev_size = -1
    stable = 0
    for _ in range(checks * 4):  # max total wait = checks * 4 * wait
        if not path.exists():
            return
        size = path.stat().st_size
        if size == prev_size and size > 0:
            stable += 1
            if stable >= checks:
                return
        else:
            stable = 0
        prev_size = size
        time.sleep(wait)


def scan_existing(
    watch_dir: Path,
    output_dir: Path,
    processed_dir: Path | None,
    fmt: str,
    executor: ThreadPoolExecutor,
) -> int:
    """Process all .wnd files already present in the watch directory concurrently."""
    files = sorted(watch_dir.glob("*.wnd"))
    if not files:
        print(f"No .wnd files found in {watch_dir}")
        return 0

    print(f"Found {len(files)} .wnd file(s) in {watch_dir}. Processing concurrently...")
    futures = []
    for f in files:
        resolved = str(f.resolve())
        with _processed_lock:
            if resolved in _processed_set:
                continue
            _processed_set.add(resolved)
        futures.append(
            executor.submit(handle_file_thread, f, output_dir, processed_dir, fmt)
        )

    # Wait for all of them to complete processing
    wait(futures)
    return len(files)


# ─── Polling mode (no dependencies) ────────────────────────────────────────────

def watch_polling(
    watch_dir: Path,
    output_dir: Path,
    processed_dir: Path | None,
    fmt: str,
    interval: float,
    executor: ThreadPoolExecutor,
) -> None:
    """Simple polling-based watcher. Checks for new .wnd files every `interval` seconds."""
    print(f"\n👁  Watching {watch_dir} for .wnd files (polling every {interval}s)")
    print("   Press Ctrl+C to stop.\n")

    known: set[str] = set()
    # Seed with already-processed files
    with _processed_lock:
        known.update(_processed_set)

    try:
        while True:
            for f in watch_dir.glob("*.wnd"):
                resolved = str(f.resolve())
                with _processed_lock:
                    if resolved not in known and resolved not in _processed_set:
                        known.add(resolved)
                        _processed_set.add(resolved)
                        executor.submit(handle_file_thread, f, output_dir, processed_dir, fmt)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n⏹  Watcher stopped.")


# ─── Watchdog mode (realtime, needs `pip install watchdog`) ─────────────────────

def watch_realtime(
    watch_dir: Path,
    output_dir: Path,
    processed_dir: Path | None,
    fmt: str,
    executor: ThreadPoolExecutor,
) -> None:
    """Realtime filesystem watcher using the watchdog library."""
    try:
        # pyrefly: ignore [missing-import]
        from watchdog.observers import Observer
        # pyrefly: ignore [missing-import]
        from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
    except ImportError:
        print("⚠  watchdog is not installed. Falling back to polling mode.")
        print("   Install it with: pip install watchdog")
        watch_polling(watch_dir, output_dir, processed_dir, fmt, interval=3, executor=executor)
        return

    class WndHandler(FileSystemEventHandler):
        def on_created(self, event):
            if isinstance(event, FileCreatedEvent):
                path = Path(event.src_path)
                if path.suffix.lower() == ".wnd":
                    resolved = str(path.resolve())
                    with _processed_lock:
                        if resolved not in _processed_set:
                            _processed_set.add(resolved)
                            executor.submit(handle_file_thread, path, output_dir, processed_dir, fmt)

        def on_moved(self, event):
            if isinstance(event, FileMovedEvent):
                path = Path(event.dest_path)
                if path.suffix.lower() == ".wnd":
                    resolved = str(path.resolve())
                    with _processed_lock:
                        if resolved not in _processed_set:
                            _processed_set.add(resolved)
                            executor.submit(handle_file_thread, path, output_dir, processed_dir, fmt)

    observer = Observer()
    observer.schedule(WndHandler(), str(watch_dir), recursive=False)
    observer.start()

    print(f"\n👁  Watching {watch_dir} for .wnd files (realtime)")
    print("   Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹  Stopping watcher...")
        observer.stop()
    observer.join()
    print("   Watcher stopped.")


# ─── CLI ────────────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watcher.py",
        description=(
            "Watch a folder for Kintech .wnd files and automatically decode them to CSV."
        ),
    )
    parser.add_argument(
        "--watch-dir", type=Path, default=Path("input"),
        help="Folder to watch for incoming .wnd files (default: ./input)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Folder to write decoded CSV output (default: ./output)",
    )
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("processed"),
        help="Folder to move processed .wnd files (default: ./processed)",
    )
    parser.add_argument(
        "--format", choices=["raw", "windographer"], default="raw",
        help="Output column layout (default: raw)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Process existing files and exit immediately (no watching)",
    )
    parser.add_argument(
        "--poll", action="store_true",
        help="Use polling instead of watchdog (no extra dependencies needed)",
    )
    parser.add_argument(
        "--interval", type=float, default=3,
        help="Polling interval in seconds (default: 3)",
    )
    parser.add_argument(
        "--no-move", action="store_true",
        help="Don't move files to processed/ after decoding (leave in place)",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Number of concurrent worker threads (default: auto-detected)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose debug logging",
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

    watch_dir: Path = args.watch_dir
    output_dir: Path = args.output_dir
    processed_dir: Path | None = None if args.no_move else args.processed_dir

    # Create watch directory if it doesn't exist
    watch_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize ThreadPoolExecutor
    # max_workers=None defaults to min(32, os.cpu_count() + 4)
    executor = ThreadPoolExecutor(max_workers=args.workers)

    print("╔══════════════════════════════════════════════════════════╗")
    print("║       Kintech .wnd Auto-Decoder (Concurrent)            ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Watch folder   : {str(watch_dir):<38} ║")
    print(f"║  Output folder  : {str(output_dir):<38} ║")
    if processed_dir:
        print(f"║  Processed to   : {str(processed_dir):<38} ║")
    else:
        print(f"║  Processed to   : {'(files left in place)':<38} ║")
    print(f"║  Output format  : {args.format:<38} ║")
    print(f"║  Max Workers    : {str(executor._max_workers):<38} ║")
    print(f"║  Mode           : {'one-shot' if args.once else ('polling' if args.poll else 'realtime'):<38} ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Always process existing files first
    scan_existing(watch_dir, output_dir, processed_dir, args.format, executor)

    if args.once:
        executor.shutdown(wait=True)
        print("\nDone (--once mode).")
        return 0

    # Start watching
    try:
        if args.poll:
            watch_polling(watch_dir, output_dir, processed_dir, args.format, args.interval, executor)
        else:
            watch_realtime(watch_dir, output_dir, processed_dir, args.format, executor)
    finally:
        executor.shutdown(wait=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
