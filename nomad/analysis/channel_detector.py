from __future__ import annotations
import struct
from dataclasses import dataclass, field
from typing import List, Optional
from analysis.binary_scanner import PrintableRun, find_printable_strings

@dataclass
class FloatFieldGuess:
    offset: int
    value: float
    plausible: bool

@dataclass
class ChannelBlockGuess:
    text_offset: int
    text: str
    preceding_floats: List[FloatFieldGuess] = field(default_factory=list)
    record_start_guess: Optional[int] = None
    record_length_guess: Optional[int] = None

def _try_float32(data: bytes, offset: int) -> Optional[float]:
    if offset < 0 or offset + 4 > len(data):
        return None
    try:
        return struct.unpack('<f', data[offset:offset + 4])[0]
    except struct.error:
        return None

def _plausible_metadata_float(v: float) -> bool:
    if v != v:
        return False
    if v in (float('inf'), float('-inf')):
        return False
    return -10000.0 <= v <= 10000.0

def find_channel_text_blocks(data: bytes, min_length: int=6) -> List[PrintableRun]:
    runs = find_printable_strings(data, min_length=min_length)
    return [r for r in runs if ' ' in r.text.strip()]

def guess_preceding_floats(data: bytes, text_run: PrintableRun, max_floats: int=6) -> List[FloatFieldGuess]:
    guesses = []
    for i in range(max_floats, 0, -1):
        off = text_run.offset - i * 4
        v = _try_float32(data, off)
        if v is None:
            continue
        guesses.append(FloatFieldGuess(offset=off, value=v, plausible=_plausible_metadata_float(v)))
    return guesses

def detect_channel_table(data: bytes, min_length: int=6) -> List[ChannelBlockGuess]:
    text_blocks = find_channel_text_blocks(data, min_length=min_length)
    guesses = []
    for run in text_blocks:
        floats = guess_preceding_floats(data, run)
        guesses.append(ChannelBlockGuess(text_offset=run.offset, text=run.text, preceding_floats=floats))
    for i in range(len(guesses) - 1):
        gap = guesses[i + 1].text_offset - guesses[i].text_offset
        guesses[i].record_length_guess = gap
    return guesses

def describe_channel_guess(g: ChannelBlockGuess) -> str:
    lines = [f'0x{g.text_offset:06X}  text={g.text!r}']
    for f in g.preceding_floats:
        flag = 'OK' if f.plausible else '??'
        lines.append(f'    [{flag}] float32 @0x{f.offset:06X} = {f.value}')
    if g.record_length_guess:
        lines.append(f'    (gap to next candidate block: {g.record_length_guess} bytes)')
    return '\n'.join(lines)