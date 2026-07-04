"""
structure_detector.py
----------------------
Heuristics for *automatically* proposing record boundaries and record sizes
in an unknown binary file, building on the primitives in binary_scanner.py.

This module embodies the "infer record size automatically" and "detect
repeating record boundaries" requirements. It is deliberately conservative:
it proposes candidates and a confidence score, but it does NOT silently
assume one is correct. The calling code (or a human) should confirm a
candidate against known reference values before trusting it -- which is
exactly the workflow used to reverse engineer the Nomad NDF format in this
project (see decoders/nomad_ndf.py and the accompanying findings report).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from analysis.binary_scanner import (
    find_tag_offsets,
    stride_histogram,
    column_variability_scan,
    ColumnReport,
)


@dataclass
class RecordCandidate:
    tag: bytes
    tag_offset_in_record: int   # where the tag sits relative to record start
    stride: int                 # proposed fixed record size in bytes
    occurrences: int            # how many times this stride was observed
    confidence: float           # occurrences / total tag occurrences
    first_record_start: int     # first byte offset of a record matching this stride
    column_report: Optional[ColumnReport] = None


def detect_record_candidates(data: bytes, tag: bytes, tag_offset_in_record: int = 0,
                              min_occurrences: int = 3) -> List[RecordCandidate]:
    """Find every occurrence of `tag`, histogram the gaps between consecutive
    occurrences, and return one RecordCandidate per distinct stride seen,
    sorted by confidence (most common stride first).

    `tag_offset_in_record` lets you say "this tag sits N bytes into the
    record" so the proposed record start is computed correctly (e.g. our
    Nomad 0x4422 / 8772-serial tag sits at byte offset 2 or similar within
    an 8/16/24-byte record, not at byte 0).
    """
    offsets = find_tag_offsets(data, tag)
    if len(offsets) < min_occurrences:
        return []

    hist = stride_histogram(offsets, top_n=10)
    total = len(offsets) - 1
    candidates = []
    for stride, count in hist:
        if stride <= 0:
            continue
        first_tag_offset = offsets[0]
        record_start = first_tag_offset - tag_offset_in_record
        candidates.append(RecordCandidate(
            tag=tag,
            tag_offset_in_record=tag_offset_in_record,
            stride=stride,
            occurrences=count,
            confidence=count / total if total else 0.0,
            first_record_start=record_start,
        ))
    return candidates


def confirm_candidate(data: bytes, candidate: RecordCandidate, sample_count: int = 200) -> RecordCandidate:
    """Attach a column-variability report to a candidate by sampling
    `sample_count` consecutive records starting at its proposed record
    start. A good candidate will show a small number of constant "marker"
    columns and the rest varying -- a bad candidate (wrong stride/offset)
    typically shows near-total variability or nonsensical alignment of the
    tag itself.
    """
    candidate.column_report = column_variability_scan(
        data, candidate.first_record_start, candidate.stride, sample_count
    )
    return candidate


def best_candidate(data: bytes, tag: bytes, tag_offset_in_record: int = 0) -> Optional[RecordCandidate]:
    """Convenience wrapper: detect candidates and return the highest-confidence
    one, with its column report attached."""
    candidates = detect_record_candidates(data, tag, tag_offset_in_record)
    if not candidates:
        return None
    top = candidates[0]
    return confirm_candidate(data, top)


def describe_candidate(c: RecordCandidate) -> str:
    lines = [
        f"Record candidate: tag={c.tag.hex()} stride={c.stride} bytes "
        f"occurrences={c.occurrences} confidence={c.confidence:.1%} "
        f"first_record_start=0x{c.first_record_start:X}",
    ]
    if c.column_report:
        lines.append(f"  constant columns ({len(c.column_report.constant_columns)}): {c.column_report.constant_columns}")
        lines.append(f"  varying columns  ({len(c.column_report.varying_columns)}): {c.column_report.varying_columns}")
    return "\n".join(lines)
