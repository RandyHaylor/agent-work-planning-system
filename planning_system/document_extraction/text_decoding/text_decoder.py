"""Tries the charset sources in order, then charset_normalizer."""
from __future__ import annotations

from typing import Callable

from planning_system.document_extraction.extraction_interface import TextDecoder
from planning_system.document_extraction.text_decoding.charset_sources import (
    bom_charset, header_charset, meta_charset,
)

CharsetGuesser = Callable[[bytes], "str | None"]
_GUESS_SAMPLE_BYTES = 200_000
_FALLBACK = "utf-8"


def charset_normalizer_guess(raw_bytes: bytes) -> str | None:
    """Default guesser: charset_normalizer's best match."""
    from charset_normalizer import from_bytes
    best = from_bytes(raw_bytes[:_GUESS_SAMPLE_BYTES]).best()
    return best.encoding if best else None


class ChainedTextDecoder(TextDecoder):
    def __init__(self, guess_charset: CharsetGuesser = charset_normalizer_guess) -> None:
        self.guess_charset = guess_charset

    def decode(self, raw_bytes: bytes, content_type_header: str | None) -> str:
        charset = (header_charset(content_type_header) or bom_charset(raw_bytes) or meta_charset(raw_bytes)
                   or self.guess_charset(raw_bytes) or _FALLBACK)
        try:
            return raw_bytes.decode(charset, errors="replace")
        except LookupError:
            return raw_bytes.decode(_FALLBACK, errors="replace")
