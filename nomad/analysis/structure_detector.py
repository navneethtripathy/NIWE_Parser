from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from analysis.binary_scanner import find_tag_offsets, stride_histogram, column_variability_scan, ColumnReport

@dataclass
class RecordCandidate:
    tag: bytes
    tag_offset_in_record: int
    stride: int
    occurrences: int
    confidence: float
    first_record_start: int
    column_report: Optional[ColumnReport] = None

def detect_record_candidates(data: bytes, tag: bytes, tag_offset_in_record: int=0, min_occurrences: int=3) -> List[RecordCandidate]:
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
        candidates.append(RecordCandidate(tag=tag, tag_offset_in_record=tag_offset_in_record, stride=stride, occurrences=count, confidence=count / total if total else 0.0, first_record_start=record_start))
    return candidates

def confirm_candidate(data: bytes, candidate: RecordCandidate, sample_count: int=200) -> RecordCandidate:
    candidate.column_report = column_variability_scan(data, candidate.first_record_start, candidate.stride, sample_count)
    return candidate

def best_candidate(data: bytes, tag: bytes, tag_offset_in_record: int=0) -> Optional[RecordCandidate]:
    candidates = detect_record_candidates(data, tag, tag_offset_in_record)
    if not candidates:
        return None
    top = candidates[0]
    return confirm_candidate(data, top)

def describe_candidate(c: RecordCandidate) -> str:
    lines = [f'Record candidate: tag={c.tag.hex()} stride={c.stride} bytes occurrences={c.occurrences} confidence={c.confidence:.1%} first_record_start=0x{c.first_record_start:X}']
    if c.column_report:
        lines.append(f'  constant columns ({len(c.column_report.constant_columns)}): {c.column_report.constant_columns}')
        lines.append(f'  varying columns  ({len(c.column_report.varying_columns)}): {c.column_report.varying_columns}')
    return '\n'.join(lines)