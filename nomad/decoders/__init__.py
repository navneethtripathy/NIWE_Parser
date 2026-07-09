from __future__ import annotations
from typing import List, Optional
from decoders.base_decoder import BaseLoggerDecoder
from decoders.nomad_ndf import NomadNDFDecoder
DECODER_REGISTRY: List[BaseLoggerDecoder] = [NomadNDFDecoder()]

def detect_decoder(data: bytes) -> Optional[BaseLoggerDecoder]:
    for decoder in DECODER_REGISTRY:
        try:
            if decoder.sniff(data):
                return decoder
        except Exception:
            continue
    return None

def get_decoder_by_name(format_name: str) -> Optional[BaseLoggerDecoder]:
    for decoder in DECODER_REGISTRY:
        if decoder.format_name == format_name:
            return decoder
    return None