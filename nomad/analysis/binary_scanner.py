"""
binary_scanner.py
------------------
Format-agnostic tools for the first pass of reverse engineering an unknown
binary data logger file:

    * hex dumping
    * locating printable ASCII text runs (these are gold for finding site
      names, sensor names, units, serial numbers embedded in headers)
    * frequency analysis of repeated byte sequences (helps find magic
      numbers / record-type tags)
    * column-wise byte variability scan across a hypothesized fixed-size
      record (the single most useful tool for confirming a record layout --
      "which byte offsets are constant across N consecutive records, and
      which vary")

None of this is Nomad-specific. It is meant to be reused against any new,
undocumented logger format dropped into the project.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence


PRINTABLE_RANGE = (0x20, 0x7E)


@dataclass
class PrintableRun:
    offset: int
    length: int
    text: str

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"PrintableRun(offset=0x{self.offset:X}, length={self.length}, text={self.text!r})"


@dataclass
class ColumnReport:
    """Result of a column-wise variability scan over a fixed-size record."""
    stride: int
    record_count: int
    constant_columns: List[int] = field(default_factory=list)
    varying_columns: List[int] = field(default_factory=list)
    # column -> sorted list of distinct byte values seen (capped for display)
    column_value_preview: dict = field(default_factory=dict)


def hex_dump(data: bytes, offset: int = 0, length: Optional[int] = None, width: int = 16) -> str:
    """Return a classic hex+ASCII dump string, similar to `od -A x -t x1z` / `xxd`."""
    end = len(data) if length is None else min(len(data), offset + length)
    lines = []
    for i in range(offset, end, width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if PRINTABLE_RANGE[0] <= b <= PRINTABLE_RANGE[1] else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<{width * 3}}  {ascii_part}")
    return "\n".join(lines)


def find_printable_strings(data: bytes, min_length: int = 4) -> List[PrintableRun]:
    """Find all maximal runs of printable ASCII characters of at least `min_length`.

    These runs are typically where embedded metadata (site names, sensor
    descriptions, units, serial numbers) live in an otherwise binary file.
    """
    pattern = re.compile(rb"[\x20-\x7e]{%d,}" % min_length)
    runs = []
    for m in pattern.finditer(data):
        runs.append(PrintableRun(offset=m.start(), length=len(m.group()), text=m.group().decode("ascii")))
    return runs


def find_repeating_byte_sequences(data: bytes, seq_len: int = 2, top_n: int = 20,
                                   region: Optional[slice] = None) -> List[tuple]:
    """Frequency-count every byte sequence of length `seq_len` in the file (or a region).

    Highly frequent short sequences are good candidates for record-type tags
    or markers (e.g. a constant 2-byte "record type" field repeated once per
    fixed-size record).
    """
    chunk = data if region is None else data[region]
    counts: Counter = Counter()
    for i in range(0, len(chunk) - seq_len + 1):
        counts[chunk[i:i + seq_len]] += 1
    return counts.most_common(top_n)


def find_tag_offsets(data: bytes, tag: bytes) -> List[int]:
    """Return every offset at which `tag` occurs in `data`."""
    offsets = []
    start = 0
    while True:
        idx = data.find(tag, start)
        if idx == -1:
            break
        offsets.append(idx)
        start = idx + 1
    return offsets


def stride_histogram(offsets: Sequence[int], top_n: int = 10) -> List[tuple]:
    """Given a list of offsets (e.g. where a tag occurs), histogram the
    gaps between consecutive offsets. A dominant gap value is very strong
    evidence of a fixed record size."""
    diffs = [offsets[i + 1] - offsets[i] for i in range(len(offsets) - 1)]
    return Counter(diffs).most_common(top_n)


def column_variability_scan(data: bytes, start: int, stride: int, count: int) -> ColumnReport:
    """The key structural-confirmation tool.

    Given a hypothesized record start offset, fixed record size (`stride`),
    and a count of consecutive records to sample, report for each byte
    column within the record whether it is constant or varies across all
    sampled records. Constant columns are candidate tags/markers/padding;
    varying columns are candidate data fields (counters, sequence numbers,
    sensor values, etc).
    """
    records = [data[start + i * stride: start + i * stride + stride] for i in range(count)]
    records = [r for r in records if len(r) == stride]
    report = ColumnReport(stride=stride, record_count=len(records))

    for col in range(stride):
        values = sorted(set(r[col] for r in records))
        if len(values) == 1:
            report.constant_columns.append(col)
        else:
            report.varying_columns.append(col)
        report.column_value_preview[col] = values[:8]

    return report


def find_record_stride(data: bytes, tag: bytes, region: Optional[slice] = None) -> Optional[int]:
    """Convenience helper: find the dominant repeat distance for a tag,
    which is the most likely record stride if this tag occurs once per
    record."""
    search_data = data if region is None else data[region]
    base = 0 if region is None else region.start or 0
    offsets = find_tag_offsets(search_data, tag)
    if len(offsets) < 2:
        return None
    hist = stride_histogram(offsets, top_n=1)
    return hist[0][0] if hist else None


def generate_file_map(data: bytes, printable_min_length: int = 4) -> str:
    """Produce a human-readable structural overview report: file size,
    printable text regions found, and the most frequent 2-byte sequences
    (candidate tags). This is the Phase-1 'file map' deliverable.
    """
    lines = [f"File size: {len(data)} bytes (0x{len(data):X})", ""]

    lines.append("=== Printable text runs (>= %d chars) ===" % printable_min_length)
    runs = find_printable_strings(data, min_length=printable_min_length)
    lines.append(f"Found {len(runs)} printable run(s).")
    for r in runs[:200]:
        lines.append(f"  0x{r.offset:06X}  len={r.length:<4d}  {r.text!r}")
    if len(runs) > 200:
        lines.append(f"  ... and {len(runs) - 200} more")
    lines.append("")

    lines.append("=== Most common 2-byte sequences (candidate tags) ===")
    for seq, cnt in find_repeating_byte_sequences(data, seq_len=2, top_n=15):
        lines.append(f"  {seq.hex()}  count={cnt}")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - manual CLI usage
    import sys
    path = Path(sys.argv[1])
    raw = path.read_bytes()
    print(generate_file_map(raw))
